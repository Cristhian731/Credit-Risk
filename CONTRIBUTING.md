# Contributing to Credit Risk

## Branches

- `main`: stable code that is presented each week. Never commit to it directly.
- `develop`: integration branch. Every change reaches it through a pull request.
- Work branches use one of these prefixes, in lowercase words separated by hyphens:

| Prefix | Use | Example |
|---|---|---|
| `feature/` | New functionality | `feature/edit-delete` |
| `fix/` | Bug fix | `fix/login-redirect` |
| `docs/` | Documentation only | `docs/setup-guide` |
| `test/` | Tests only | `test/budget-cases` |
| `chore/` | Tooling, dependencies, config | `chore/update-flask` |

## Working in phases

Larger work is split into phases, one branch and one pull request per phase:

1. **Design**: a short plan (what goes in, what does not, deliverables) agreed by the team.
2. **Implementation** on its own branch. When a phase builds on the previous one, its branch
   starts from the previous phase's branch.
3. **Verification**: the whole test suite, plus a manual walk through the app
   (register, log in, dashboard, transactions, credit evaluation, history, log out).
4. **Pull request** and review. Merge only after approval.

Bugs found outside the phase's scope are written down for a later phase, not fixed on the way.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/), in English:

```
<type>(<optional scope>): <short summary in imperative mood>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `ci`, `chore`. Keep commits small:
one logical change per commit.

## Contracts

`app/models.py`, `app/services/repository.py`, `app/auth/services.py` and the login form in
`templates/auth/_login_form.html` are shared between team members, and their tests
(`tests/test_models_contract.py`, `tests/test_repository.py`, `tests/test_auth_contract.py`)
describe them. [docs/INTEGRATION.md](docs/INTEGRATION.md) is the reference for the layers and
the contracts.

**Do not rename or remove functions, arguments, models, tables or fields of a contract without
agreeing with the team first.** When a change is agreed, update the contract, its tests, every
caller and `docs/INTEGRATION.md` in the same pull request.

## Rules every change follows

- **Data access**: routes call `app/services/repository.py`, never the database. Repository
  functions filter by `user_id` and return plain dicts; another user's record is answered with
  **404**, exactly like a missing one.
- **Nothing calculable is stored**: totals and balances are computed when read.
- **Forms**: every POST form carries `{{ csrf_token() }}` (a test checks all templates).
  Deleting is a POST behind a confirmation page, never a GET.
- **Schema changes** only through a migration:
  1. Change `app/models.py` and run `flask --app run db migrate -m "..."`; read the file.
  2. Back up `instance/credit_risk.db` with a date and try the migration on a copy, up and down.
  3. Commit the migration together with the model change. `tests/test_migrations.py` fails if
     the models and the migrations disagree.
  See [docs/MIGRATIONS.md](docs/MIGRATIONS.md).

## Tests

```bash
pytest                                                       # in-memory SQLite
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/credit_risk_test pytest   # PostgreSQL
```

- Use an empty database for `TEST_DATABASE_URL`: the tests create and drop the tables.
- Every test must pass. Never delete or skip a test to make the suite pass; if a behavior
  changes on purpose, update the test and say why in the pull request.
- New behavior needs tests, including the other user's case (404) and CSRF where it applies.
- GitHub Actions runs two jobs on every pull request to `develop` and `main`: SQLite and
  PostgreSQL. Both migrate an empty database (upgrade, downgrade, upgrade) and run the suite.

## Pull requests

1. Run `pytest` locally; everything must pass.
2. Open the pull request against `develop` (or against the previous phase's branch when the
   phases are reviewed in order) and fill in the checklist.
3. Wait for both CI jobs and a review from the code owner before merging.

Never commit secrets or local databases: keep secrets in a local `.env` file, which is ignored
by git, like `instance/`.

## Language

Everything in the repository is written in English: code, names, comments, docstrings,
interface text, documentation and commit messages.
