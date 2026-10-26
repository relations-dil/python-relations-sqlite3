# Changelog

All notable changes to python-relations-sqlite3 are recorded here, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Changed
- `make new` works on the ticket branch you're on: it writes VERSION and the changelog section there and commits, makes no branch of its own, and refuses on main, since we branch from the ticket. `B=` and `BRANCH_PREFIX` are gone (relations-dil/python-relations#98).

## [0.6.13] - 2026-10-26

### Added
- Requires relations-sql 0.6.11 and relations-sqlite 0.6.5, so a str field with a `length` is enforced with a `CHECK (length(column) <= length)` constraint (relations-dil/python-relations-sqlite#15).
- Jenkins releases on a merge to `main`: a `release` stage (only on `main`) runs `make release`, which does nothing for a version that is already released and otherwise does the test release, the release and the tag. It pushes the tag with the `github` credential, as Leroy Jenkins, one build at a time, with a two hour timeout (relations-dil/python-relations#80). The package builds run in a copy with only the files they use mounted read-only, so nothing root-owned is left in the workspace, and `make tag` stops on a failure instead of ignoring it. The release scripts work with the older git on the Jenkins host.
- `make help` lists every target with what it does (each target has a `## description` after it), and is what a bare `make` runs.
- Release tooling, the same as relations-dil's (relations-dil/python-relations#77): `make new` starts a release, `make version` sets the version, `make release-check` says where a release is up to and what would stop it, `make release` does what's left (checks, TestPyPI and a clean install from it, PyPI, the tag), `make dist-check` builds and checks the distributions, and `make test-release` tests the scripts against a throwaway repo and fake indexes. The work is in `scripts/`.

### Changed
- `make release-check` and `make release` don't run `build`, `test`, `lint` and `setup` again: the Jenkins stages have just run them before the release stage, so it was the same work twice. Run them yourself before checking by hand, as `make release-check` is only the checks and `dist-check` now (relations-dil/python-relations#90).
- Every `docker run` in the `Makefile` uses `--rm`, and a replaced database container is removed with its volume (`docker rm --force -v`), so builds and test runs leave no stopped containers or volumes behind.
- `testpypi` and `pypi` run in the current `python` image with `build` and `twine` installed on the fly, so the custom `gaf3/pypi` image is no longer used.

Shipping as 0.6.10, with relations-dil 0.6.16.

### Added
- A `VERSION` file as the one place the version is set: the `Makefile` reads it and mounts it, `testpypi` and `pypi` pass it as `BUILD_VERSION`, and `setup.py` reads `BUILD_VERSION` or the file.

### Changed
- A key stored in a dict field (`child_inject` in relations-dil 0.6.16) is queried by its path in that field, instead of a column that doesn't exist: new `retrieve_record` hands the record to `retrieve_field`, which looks an injected field up in the field it's stored in (as the extracted column if it's been extracted), and `sort` does the same. Counting, retrieving, updating and deleting by the key work, and mass updates through it are refused.

## [0.6.12] - 2026-10-14

### Changed
- A duplicate (SQLite's `UNIQUE constraint failed`, which a repeated primary key also is) raises `relations.UniqueError` from create and update, with the driver's `sqlite3.IntegrityError` as its cause, through the new `Source.write`. Any other integrity error is left as it is.
- "none retrieved" and "more than one retrieved" are `relations.NotFoundError` and `relations.MultipleError` (same messages, still `ModelError`s). Needs relations-dil 0.6.19 (relations-dil/python-relations#78).

## [0.6.11] - 2026-10-14

### Changed
- Needs relations-dil 0.6.18 and relations-sqlite 0.6.4: a string id (caller supplied, a non-int id) is created, read, updated, deleted and tied with its primary key. The source needed no change, the work is in relations-dil, relations-sql and relations-sqlite.

## [0.6.9] - 2026-06-08

- Searching many-to-many ties by sibling attributes now de-duplicates results: counts use `COUNT(DISTINCT id)` and retrieves use `SELECT DISTINCT` on the model's columns when the query joins ties.
- Pinned `relations-dil` 0.6.15 and `relations-sql` 0.6.9.

## [0.6.8] - 2026-06-06

- Added many-to-many support: `Source` now includes the `relations_sql.SOURCE` mixin, so tie criteria resolve inside the SELECT query via `collate_ties_query`.
- Creates, updates and deletes now write and remove tie rows (`create_ties`, `delete_ties`), including updates and deletes done by query, and retrieves load ties.
- Fields without a `store` are left out of inserts.

## [0.6.7] - 2022-11-25

- Declared `relations-dil` and `relations-sqlite` as install requirements in `setup.py` and `requirements.txt` instead of git installs.

## [0.6.6] - 2022-08-07

- Added PyPI publishing: `PYPI.md` long description, `LICENSE.txt` and `testpypi` and `pypi` Make targets.
- Removed the git-based dependency installs from the Dockerfile and setup step.

## [0.6.5] - 2022-03-14

- Bumped dependency pins to `relations` 0.6.9, `relations-sql` 0.6.5 and `relations-sqlite` 0.6.0, with updated tests for migrations.

## [0.6.4] - 2022-03-13

- Bumped the `relations`, `relations-sql` and `relations-sqlite` requirements; no library code changed.

## [0.6.3] - 2022-02-18

- Renamed labels to titles: `labels` became `titles` and `labels_query` became `titles_query`, searching `model._titles` and `field.titles` and returning `relations.Titles`.

## [0.6.2] - 2021-11-21

- Renamed the package to `python-relations-sqlite3` and moved dependency references to the `relations-dil` organization in preparation for PyPI.

## [0.6.1] - 2021-11-13

- Renamed Source methods to the shorter names of the updated `relations` API, such as `init`, `define`, `create`, `count`, `retrieve`, `labels`, `update`, `delete`, `retrieve_field` and `update_record`.
- `definition_convert` and `migration_convert` became `definition` and `migration`.

## [0.6.0] - 2021-11-12

- Rebuilt the Source on `relations_sql` and `relations_sqlite`: queries are made with `SELECT`, `INSERT`, `UPDATE` and `DELETE` expression classes instead of hand-built strings, and `execute` accepts SQL expressions.
- Model DDL is generated by the dialect `TABLE` class, and the hand-written table and index naming, `encode` and `decode` code was removed.
- `SCHEMA` and `STORE` replace `TABLE` for model naming, and integer id fields become auto-increment by default.

## [0.5.7] - 2021-08-27

- Added support for set fields: values are sorted for `in`, `ne`, `has`, `any` and `all`, and sets and lists compare as JSON in equality and range operators.
- Fixed comparisons of non-scalar values against JSON paths.

## [0.5.6] - 2021-08-22

- Added `has`, `any` and `all` operators for list fields, including list values at JSON paths, using `json_each` and `json_array_length`.

## [0.5.5] - 2021-08-16

- Renamed the migration tracking table to `_relations_migration` with a `stamp` column, replacing `_relations_migrations` and its `migration` column.

## [0.5.4] - 2021-08-12

- Added `load` for executing a SQL file and `list` for pairing definition and migration files by timestamp in a source directory.
- `migrate` now loads definition and migration files through `load`.

## [0.5.3] - 2021-08-08

- Added migrations support and schema handling: a new `schemas` argument attaches additional databases, models use `SCHEMA` instead of `DATABASE`, and table and index names are built from the schema.
- Split out `column_define` and `extract_define` so migrations can generate column DDL, and `model_init` marks `QUERY` as undefinable.

## [0.5.2] - 2021-06-17

- Empty `in` lists now match nothing (`FALSE`) and empty `ne` lists match everything (`TRUE`) instead of producing invalid SQL.
- Searching through a parent relation no longer fails when no parents match.

## [0.5.1] - 2021-06-16

- Bumped the `relations` requirement to 0.5.1 for apply and access support; no library code changed.

## [0.5.0] - 2021-06-14

- Reworked extracted fields: `field.extract` is now a dict of paths to kinds, each creating a generated column named `<store>__<path>` with a matching SQLite type.
- Criteria and `like` searches on an extracted path now query that generated column instead of calling `json_extract`.

## [0.1.7] - 2021-06-13

- Adapted to the new change tracking in `relations`: fields marked `auto` replace `readonly`, creates use `record.create` and updates use `record.mass` and `record.update` to decide which values are written.

## [0.1.6] - 2021-06-13

- Updates now use `field.export()` for every field value.

## [0.1.5] - 2021-06-02

- Added `model_count`, which runs `COUNT(*)` with the model's criteria and `like` search.

## [0.1.4] - 2021-05-31

- Added support for `inject` fields, which are skipped when creating, defining and updating.
- Updates export field values through the field's `attr` and JSON-encode objects.

## [0.1.3] - 2021-05-30

- Added extracted fields: a field with `extract` is defined as a generated column using `json_extract` on another field.
- Renamed the path helper to `walk`.

## [0.1.2] - 2021-05-29

- Any field whose kind is not `bool`, `int`, `float` or `str` is now stored as JSON, so objects round-trip, not only lists and dicts.
- JSON path building moved to a shared `path_retrieve` helper, and `like` searches can target a path within a JSON field or use the field's `label` paths.

## [0.1.1] - 2021-05-27

- Added searching inside JSON fields using `__` paths in criteria, translated to `json_extract` with array index and quoted key handling.
- Added `notlike` and `null` operators, and operators now work on JSON paths.

## [0.1.0] - 2021-05-24

- Initial release of the SQLite Source for relations, a `Source` class built on the stdlib `sqlite3` module that accepts a database path or an existing connection.
- Created tables from model definitions (`model_define`, `field_define`) and inserted records (`field_create`), JSON-encoding list and dict values on write and decoding them on read.
