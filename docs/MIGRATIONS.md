# Database migrations

The schema is created and changed only through migrations (Flask-Migrate / Alembic).
`create_app()` no longer creates tables. All commands use `flask --app run`.

## Everyday commands

| Task | Command |
|---|---|
| Create the schema in a new database | `flask --app run db upgrade` |
| Show the current revision | `flask --app run db current` |
| Generate a migration after changing `app/models.py` | `flask --app run db migrate -m "Describe the change"` |
| Apply it | `flask --app run db upgrade` |
| Undo the last migration | `flask --app run db downgrade` |

Always read the generated file in `migrations/versions/` before applying it. A test
(`tests/test_migrations.py`) fails if the models and the migrations disagree, so a model
change without its migration cannot be merged.

## Before any schema change

1. Stop the server.
2. Back up the database with a date, for example:
   `copy instance\credit_risk.db instance\backups\credit_risk_YYYYMMDD_before_change.db`
3. Try the migration on a **copy** first (`DATABASE_URL=sqlite:///path/to/copy.db`).
4. Apply it to the real database only if the copy is correct.

## Moving a database created before migrations existed

Databases created with `db.create_all()` have the old global `UNIQUE (document_number)` on
`clients`, so `flask db stamp` is **not enough**: it would keep the old constraint. Instead:

```bash
flask --app run adopt-legacy-db instance/credit_risk.db instance/credit_risk_migrated.db
```

The command builds the new file with the migrations, copies every row, checks the row counts
and never modifies the source. It refuses to overwrite an existing target. When the result
looks right, keep the old file as a backup and rename the new one to `credit_risk.db`.

## Reverting

- **Undo the migration but keep the file:** `flask --app run db downgrade base` drops every
  table (the data is lost, so use it only on a copy).
- **Go back to the previous database:** stop the server and copy the dated backup over
  `instance/credit_risk.db`. The backup made by `adopt-legacy-db` is the pre-migration file.
- **Undo only the last change:** `flask --app run db downgrade`, then restore the code to the
  previous commit.

## Notes

- `migrations/env.py` is project code, not generated boilerplate: it keeps the app logger
  enabled while migrations run and uses `db.engine` (the `get_engine()` helper is deprecated).
- Constraint names follow the convention in `app/extensions.py`, which makes SQLite batch
  migrations reproducible.
