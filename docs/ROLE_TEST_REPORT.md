# Role Test Report

The table lists every page of the system and what each role gets when it opens the page. Expected is what the access rules say; Result is what was observed when the test was run against the application (Allowed, Redirected to login or 403). The same matrix runs as an automatic test in `tests/test_roles.py`, so it is checked again with every change.

Pages checked: 18. Role and page combinations: 72. Differences between expected and observed: 0.

| Role | Page | Expected | Result | Notes |
| --- | --- | --- | --- | --- |
| Anonymous | `/` | Allowed | Allowed |  |
| Anonymous | `/admin/` | Redirected to login | Redirected to login |  |
| Anonymous | `/admin/categories` | Redirected to login | Redirected to login |  |
| Anonymous | `/admin/monitoring` | Redirected to login | Redirected to login |  |
| Anonymous | `/admin/reports` | Redirected to login | Redirected to login |  |
| Anonymous | `/admin/reports/decisions.csv` | Redirected to login | Redirected to login |  |
| Anonymous | `/credit/` | Redirected to login | Redirected to login |  |
| Anonymous | `/credit/history` | Redirected to login | Redirected to login |  |
| Anonymous | `/credit/models/` | Allowed | Allowed |  |
| Anonymous | `/dashboard/` | Redirected to login | Redirected to login |  |
| Anonymous | `/methodology/` | Allowed | Allowed |  |
| Anonymous | `/methodology/phase-1` | Allowed | Allowed |  |
| Anonymous | `/resources` | Allowed | Allowed |  |
| Anonymous | `/reviews/` | Redirected to login | Redirected to login |  |
| Anonymous | `/reviews/history` | Redirected to login | Redirected to login |  |
| Anonymous | `/reviews/indicators` | Redirected to login | Redirected to login |  |
| Anonymous | `/transactions/` | Redirected to login | Redirected to login |  |
| Anonymous | `/transactions/new` | Redirected to login | Redirected to login |  |
| Applicant | `/` | Allowed | Allowed |  |
| Applicant | `/admin/` | 403 | 403 |  |
| Applicant | `/admin/categories` | 403 | 403 |  |
| Applicant | `/admin/monitoring` | 403 | 403 |  |
| Applicant | `/admin/reports` | 403 | 403 |  |
| Applicant | `/admin/reports/decisions.csv` | 403 | 403 |  |
| Applicant | `/credit/` | Allowed | Allowed |  |
| Applicant | `/credit/history` | Allowed | Allowed |  |
| Applicant | `/credit/models/` | Allowed | Allowed |  |
| Applicant | `/dashboard/` | Allowed | Allowed |  |
| Applicant | `/methodology/` | Allowed | Allowed |  |
| Applicant | `/methodology/phase-1` | Allowed | Allowed |  |
| Applicant | `/resources` | Allowed | Allowed |  |
| Applicant | `/reviews/` | 403 | 403 |  |
| Applicant | `/reviews/history` | 403 | 403 |  |
| Applicant | `/reviews/indicators` | 403 | 403 |  |
| Applicant | `/transactions/` | Allowed | Allowed |  |
| Applicant | `/transactions/new` | Allowed | Allowed |  |
| Analyst | `/` | Allowed | Allowed |  |
| Analyst | `/admin/` | 403 | 403 |  |
| Analyst | `/admin/categories` | 403 | 403 |  |
| Analyst | `/admin/monitoring` | 403 | 403 |  |
| Analyst | `/admin/reports` | 403 | 403 |  |
| Analyst | `/admin/reports/decisions.csv` | 403 | 403 |  |
| Analyst | `/credit/` | 403 | 403 |  |
| Analyst | `/credit/history` | 403 | 403 |  |
| Analyst | `/credit/models/` | Allowed | Allowed |  |
| Analyst | `/dashboard/` | 403 | 403 |  |
| Analyst | `/methodology/` | Allowed | Allowed |  |
| Analyst | `/methodology/phase-1` | Allowed | Allowed |  |
| Analyst | `/resources` | Allowed | Allowed |  |
| Analyst | `/reviews/` | Allowed | Allowed |  |
| Analyst | `/reviews/history` | Allowed | Allowed |  |
| Analyst | `/reviews/indicators` | Allowed | Allowed |  |
| Analyst | `/transactions/` | 403 | 403 |  |
| Analyst | `/transactions/new` | 403 | 403 |  |
| Administrator | `/` | Allowed | Allowed |  |
| Administrator | `/admin/` | Allowed | Allowed |  |
| Administrator | `/admin/categories` | Allowed | Allowed |  |
| Administrator | `/admin/monitoring` | Allowed | Allowed |  |
| Administrator | `/admin/reports` | Allowed | Allowed |  |
| Administrator | `/admin/reports/decisions.csv` | Allowed | Allowed |  |
| Administrator | `/credit/` | 403 | 403 |  |
| Administrator | `/credit/history` | 403 | 403 |  |
| Administrator | `/credit/models/` | Allowed | Allowed |  |
| Administrator | `/dashboard/` | 403 | 403 |  |
| Administrator | `/methodology/` | Allowed | Allowed |  |
| Administrator | `/methodology/phase-1` | Allowed | Allowed |  |
| Administrator | `/resources` | Allowed | Allowed |  |
| Administrator | `/reviews/` | Allowed | Allowed |  |
| Administrator | `/reviews/history` | Allowed | Allowed |  |
| Administrator | `/reviews/indicators` | Allowed | Allowed |  |
| Administrator | `/transactions/` | 403 | 403 |  |
| Administrator | `/transactions/new` | 403 | 403 |  |

## Other checks made by the tests

- The registration always creates an Applicant; a role sent in the form is ignored.
- Only an Administrator changes a role, an Administrator cannot remove the role of the last Administrator.
- An Applicant opens only their own requests: the request of another Applicant answers 404.
- An Applicant cannot decide a request or record an outcome (the request is refused).
- Every route of the private area must appear in the matrix; a new route without a test fails the suite.
