#!/usr/bin/env python3
"""Pre-merge guard for db/migrations. Runs without a database.

1. Every file is named V<n>__<snake_case>.sql.
2. Versions are unique and continuous (1, 2, 3, ...).
3. With --base <git ref>: no migration that already exists on the base branch was
   modified, renamed or deleted. Flyway would refuse it later with a checksum
   mismatch on every environment that already ran it; the fix is a new migration.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

NAME = re.compile(r"^V(\d+)__[a-z0-9_]+\.sql$")
MIGRATIONS_DIR = "db/migrations"


def check_names(filenames):
    errors, versions = [], []
    for name in filenames:
        m = NAME.match(name)
        if not m:
            errors.append(f"{name}: must look like V<number>__snake_case_description.sql")
            continue
        versions.append(int(m.group(1)))
    for v in sorted({v for v in versions if versions.count(v) > 1}):
        errors.append(f"version {v} is used by more than one file")
    expected = list(range(1, len(set(versions)) + 1))
    if sorted(set(versions)) != expected:
        errors.append(f"versions must be continuous from 1, found {sorted(set(versions))}")
    return errors


def check_history(diff_lines):
    """diff_lines: output of `git diff --name-status <base> -- db/migrations`."""
    errors = []
    for line in diff_lines:
        if not line.strip():
            continue
        status, *paths = line.split("\t")
        if status[0] in "MDR":
            errors.append(f"{paths[0]}: already released, so it must not be "
                          f"{ {'M': 'modified', 'D': 'deleted', 'R': 'renamed'}[status[0]] }. "
                          f"Add a new V<next>__ migration instead.")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="git ref to compare against, e.g. origin/main")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    names = sorted(p.name for p in (root / MIGRATIONS_DIR).iterdir() if p.is_file())
    errors = check_names(names)
    if args.base:
        diff = subprocess.run(["git", "diff", "--name-status", args.base, "--", MIGRATIONS_DIR],
                              cwd=root, check=True, capture_output=True, text=True).stdout
        errors += check_history(diff.splitlines())

    for e in errors:
        print(f"ERROR {e}")
    if errors:
        sys.exit(1)
    print(f"{len(names)} migrations OK" + (f" (no released migration changed since {args.base})" if args.base else ""))


if __name__ == "__main__":
    main()
