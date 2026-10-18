# Runbook

## Flyway: "Migration checksum mismatch"

```
ERROR: Validate failed: Migrations have failed validation
Migration checksum mismatch for migration version 3
-> Applied to database : 95693927
-> Resolved locally    : 658498570
```

**Meaning:** someone edited a migration file that has already been applied. Flyway
stores a checksum of each applied file in `flyway_schema_history` and refuses to
continue when the file on disk no longer matches.

**Fix:** revert the edit (`git checkout <base> -- db/migrations/V3__...sql`) and put the
change in a **new** migration, `V5__...`. Only use `flyway repair` if the edit
changed nothing that matters (e.g. a comment) and the team agrees, because it rewrites the
recorded checksum.

**Prevention:** `scripts/check_migrations.py --base origin/main` fails a pull request that
modifies, deletes or renames a released migration, before it is merged.

## A migration fails halfway in production

MySQL DDL (`CREATE`, `ALTER`, `DROP`) **auto-commits**, so a migration with several
statements cannot be rolled back as a unit. If statement 2 of 3 fails, statement 1 is
already applied.

1. Stop the release; don't re-run blindly.
2. `scripts/flyway.sh info` and query `flyway_schema_history`: the failed version has
   `success = 0`.
3. Compare the real schema with the migration (`SHOW CREATE TABLE ...`) to see which
   statements ran.
4. Either finish or undo the partial change by hand, then `flyway repair` to remove the
   failed row and re-run, **or** restore the backup taken before the release.
5. Prevention: keep one DDL statement per migration where possible, and make
   statements re-runnable when it makes sense.

## Rolling back a schema change

Plan the rollback before the release, not during the incident:
- **Backward-compatible (expand/contract) changes.** V4 is an example: new columns are
  `NOT NULL DEFAULT ...`, so the previous application version keeps working. Rolling
  back the *application* needs no schema change.
- To rename or remove a column: release 1 adds the new column and writes both, release 2
  moves reads to the new column, release 3 drops the old one. Each step can be rolled back.
- For changes that destroy data (`DROP COLUMN`, type narrowing), take a backup
  (`mysqldump --single-transaction`, or a snapshot) right before the release.
- Rolling back means a new forward migration that reverses the change, not
  deleting rows from `flyway_schema_history`.

## "After a release, a report that took 2 ms now takes 25 ms"

This is exactly what `make drill` does: V5 drops `idx_orders_purchase_ts_amount`.

1. **What changed?** `scripts/flyway.sh info` shows the new migration(s); read them.
2. **EXPLAIN the slow query** and compare it with the plan saved in the last good release's
   `reports/release.json`:
   ```
   before: type=range key=idx_orders_purchase_ts_amount rows=3422  Using index
   after:  type=ALL   key=NULL                          rows=119814 Using filesort
   ```
3. **Cause:** the index the report relied on was dropped.
4. **Fix forward** with a new migration (`drills/fix/V6__...` recreates the index). Do not
   edit or delete V5; it has already run.
5. **Prove it:** re-run the same benchmark. The gate goes from
   `FAIL (regression) 2.74 → 25.68 ms` back to `ok`.
6. Write a short root-cause note: what changed, why the plan changed, the fix, and how the
   pipeline now catches it.

In CI, step 6 of the pipeline (the performance gate) blocks that release before it ships.
