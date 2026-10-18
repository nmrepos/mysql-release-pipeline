#!/usr/bin/env python3
"""Time every query in queries.py and capture its EXPLAIN plan.

Each query runs once to warm the buffer pool, then --runs more times; the median is
reported so one noisy run does not decide the result.

    python scripts/benchmark.py --label baseline --out reports/baseline.json
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from db import connect
from queries import QUERIES


def explain(cur, sql):
    cur.execute("EXPLAIN " + sql)
    columns = [d[0] for d in cur.description]
    return [
        {k: row[columns.index(k)] for k in ("table", "type", "key", "rows", "filtered", "Extra")}
        for row in cur.fetchall()
    ]


def time_query(cur, sql, runs):
    cur.execute(sql)
    cur.fetchall()
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        timings.append((time.perf_counter() - start) * 1000)
    return timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--runs", type=int, default=7)
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT MAX(version) FROM flyway_schema_history WHERE success = 1")
    schema_version = cur.fetchone()[0]

    results = []
    print(f"Benchmark '{args.label}' at schema version {schema_version} ({args.runs} runs each)")
    for q in QUERIES:
        timings = time_query(cur, q["sql"], args.runs)
        plan = explain(cur, q["sql"])
        median = statistics.median(timings)
        results.append({
            "name": q["name"],
            "median_ms": round(median, 2),
            "min_ms": round(min(timings), 2),
            "max_ms": round(max(timings), 2),
            "plan": plan,
        })
        first = plan[0]
        print(f"  {q['name']:<26} {median:8.2f} ms   type={first['type']} key={first['key']} "
              f"rows={first['rows']} extra={first['Extra']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"label": args.label, "schema_version": schema_version, "runs": args.runs,
                               "results": results}, indent=2, default=str))
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
