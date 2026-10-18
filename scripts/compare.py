#!/usr/bin/env python3
"""Release gate: compare two benchmark files and fail on regressions.

A critical query fails the gate when either
  * it is more than --tolerance (default 50%) slower than the baseline AND more than
    --min-delta-ms (default 10 ms) slower, so run-to-run noise never fails a build, or
  * its median is over its budget_ms from queries.py.

    python scripts/compare.py reports/baseline.json reports/release.json --markdown reports/summary.md
"""
import argparse
import json
import sys
from pathlib import Path

from queries import QUERIES


def evaluate(before, after, tolerance=0.5, min_delta_ms=10.0, queries=QUERIES):
    """Return one row per query with its verdict. Pure function, unit tested."""
    meta = {q["name"]: q for q in queries}
    before_by_name = {r["name"]: r for r in before["results"]}
    rows = []
    for result in after["results"]:
        name = result["name"]
        q = meta[name]
        old = before_by_name[name]["median_ms"]
        new = result["median_ms"]
        regressed = new > old * (1 + tolerance) and new - old > min_delta_ms
        over_budget = new > q["budget_ms"]
        if q["critical"] and over_budget:
            verdict = "FAIL (over budget)"
        elif q["critical"] and regressed:
            verdict = "FAIL (regression)"
        elif regressed or over_budget:
            verdict = "WARN"
        else:
            verdict = "ok"
        rows.append({
            "name": name,
            "before_ms": old,
            "after_ms": new,
            "speedup": round(old / new, 1) if new else None,
            "budget_ms": q["budget_ms"],
            "before_plan": before_by_name[name]["plan"][0],
            "after_plan": result["plan"][0],
            "verdict": verdict,
        })
    return rows


def to_markdown(before, after, rows):
    lines = [
        f"### Query benchmark: `{before['label']}` (v{before['schema_version']}) "
        f"vs `{after['label']}` (v{after['schema_version']})",
        "",
        "| Query | Before (ms) | After (ms) | Speedup | Plan before | Plan after | Verdict |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for r in rows:
        bp, ap = r["before_plan"], r["after_plan"]
        lines.append(
            f"| {r['name']} | {r['before_ms']} | {r['after_ms']} | {r['speedup']}x "
            f"| {bp['type']} / {bp['key'] or '-'} / {bp['rows']} rows "
            f"| {ap['type']} / {ap['key'] or '-'} / {ap['rows']} rows | {r['verdict']} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--tolerance", type=float, default=0.5)
    parser.add_argument("--min-delta-ms", type=float, default=10.0)
    parser.add_argument("--markdown")
    args = parser.parse_args()

    before = json.loads(Path(args.before).read_text())
    after = json.loads(Path(args.after).read_text())
    rows = evaluate(before, after, args.tolerance, args.min_delta_ms)
    md = to_markdown(before, after, rows)
    print(md)
    if args.markdown:
        Path(args.markdown).write_text(md)

    failures = [r["name"] for r in rows if r["verdict"].startswith("FAIL")]
    if failures:
        print(f"Release gate FAILED: {', '.join(failures)}", file=sys.stderr)
        sys.exit(1)
    print("Release gate passed.")


if __name__ == "__main__":
    main()
