from check_migrations import check_history, check_names


def test_valid_sequence_passes():
    assert check_names(["V1__create.sql", "V2__add_index.sql", "V3__add_col.sql"]) == []


def test_bad_name_is_rejected():
    errors = check_names(["V1__create.sql", "v2-add-index.sql"])
    assert any("v2-add-index.sql" in e for e in errors)


def test_duplicate_version_is_rejected():
    errors = check_names(["V1__create.sql", "V2__a.sql", "V2__b.sql"])
    assert any("version 2" in e for e in errors)


def test_gap_in_versions_is_rejected():
    errors = check_names(["V1__create.sql", "V3__skip.sql"])
    assert any("continuous" in e for e in errors)


def test_new_migration_is_allowed():
    assert check_history(["A\tdb/migrations/V5__new.sql"]) == []


def test_editing_released_migration_is_rejected():
    errors = check_history(["M\tdb/migrations/V3__add_reporting_indexes.sql"])
    assert len(errors) == 1 and "modified" in errors[0]


def test_deleting_or_renaming_released_migration_is_rejected():
    errors = check_history(["D\tdb/migrations/V1__x.sql", "R100\tdb/migrations/V2__a.sql\tdb/migrations/V2__b.sql"])
    assert len(errors) == 2
