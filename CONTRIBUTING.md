# Contributing to Credit Risk

## Branches

- `main`: stable code that is presented each week. Never commit to it directly.
- `develop`: integration branch. Every feature is merged here first through a pull request.
- Work branches start from `develop` and use one of these prefixes:

| Prefix | Use | Example |
|---|---|---|
| `feature/` | New functionality | `feature/sqlalchemy-models` |
| `fix/` | Bug fix | `fix/login-redirect` |
| `docs/` | Documentation only | `docs/setup-guide` |
| `test/` | Tests only | `test/budget-cases` |
| `chore/` | Tooling, dependencies, config | `chore/update-flask` |

Use lowercase words separated by hyphens.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/), in English:

```
<type>(<optional scope>): <short summary in imperative mood>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `ci`, `chore`.

Examples:

```
feat(models): add Transaction model
fix(auth): reject empty passwords on register
test: cover budget relationships
```

Keep commits small: one logical change per commit.

## Contracts

`app/models.py`, `app/services/repository.py`, `app/auth/services.py` and the login form in
`templates/auth/_login_form.html` are shared contracts between team members.
`tests/test_models_contract.py`, `tests/test_repository.py` and `tests/test_auth_contract.py`
define when each contract is fulfilled. [docs/INTEGRATION.md](docs/INTEGRATION.md) lists the
integration steps.

**Do not rename functions, arguments, models, tables or fields of the contracts without
asking the team first.** Other parts of the app already depend on those names. If a change
is needed, agree on it, then update the contract, the tests and every caller in the same
pull request.

When your contract tests pass, delete the `pytestmark = pytest.mark.xfail(...)` line in your
test file so future regressions fail the build.

## Pull requests

1. Run `pytest` locally; everything must pass (`xfail` results are expected until a contract
   is implemented).
2. Open the pull request against `develop` and fill in the checklist.
3. GitHub Actions runs the tests on every pull request to `develop` and `main`.
4. Wait for a review from the code owner before merging.

Never commit secrets: keep them in a local `.env` file, which is ignored by git.

## Language

Everything in the repository is written in English: code, names, comments, docstrings,
interface text, documentation and commit messages.
