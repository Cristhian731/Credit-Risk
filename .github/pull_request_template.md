## Summary

<!-- What does this pull request change and why? Which phase is it? -->

## How it was verified

<!-- Tests added or changed (and why), and the manual walk-through done. -->

## Checklist

- [ ] `pytest` passes locally, and both CI jobs (SQLite and PostgreSQL) are green
- [ ] No test was deleted or skipped to make the suite pass; changed tests are explained above
- [ ] Contracts respected: nothing in `app/models.py`, `app/services/repository.py` or `app/auth/services.py` was renamed or removed without team agreement (and `docs/INTEGRATION.md` is updated if it changed)
- [ ] Schema changes come with a migration, tried up and down on a copy of the database
- [ ] Every new POST form carries a CSRF token; nothing is deleted by GET
- [ ] Records are filtered by the current user; another user's id answers 404
- [ ] No calculable value (totals, balances) is stored
- [ ] No secrets or local databases committed (`.env`, keys, `instance/`)
- [ ] Branch name and commit messages follow `CONTRIBUTING.md`
