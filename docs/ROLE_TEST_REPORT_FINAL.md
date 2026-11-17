# Final Role Test Report

Published app tested: https://credit-risk-dxit.onrender.com
Tester: Alejandro Alarcon Ibañez
Date: 16/11/2026

Three accounts were used, one per role. Passwords are not written in this document.

| Account | Role | Lands on after login |
| --- | --- | --- |
| Account A | Applicant | `/dashboard/` |
| Account B | Analyst | `/reviews/` (Review queue) |
| Account C | Administrator | `/admin/` (Users and roles) |

**Expected** comes from the access rules in the code (`roles_required` in each route). **Result** is what was observed on the published site: Allowed, 403 or Redirected to login. A role that opens a page it should not see gets the 403 page.

## What each role can and cannot do

| Action | Page | Applicant (Account A) | Analyst (Account B) | Administrator (Account C) |
| --- | --- | --- | --- | --- |
| Record income and expenses | `/transactions/` | Expected: Allowed. Result: [✅] | Expected: 403. Result: [✅] | Expected: 403. Result: [✅] |
| Create a credit request | `/credit/` | Expected: Allowed. Result: [✅] | Expected: 403. Result: [✅] | Expected: 403. Result: [✅] |
| See own requests | `/credit/history` | Expected: Allowed. Result: [✅] | Expected: 403. Result: [✅] | Expected: 403. Result: [✅] |
| Open the dashboard | `/dashboard/` | Expected: Allowed. Result: [✅] | Expected: 403. Result: [✅] | Expected: 403. Result: [✅] |
| Review the queue | `/reviews/` | Expected: 403. Result: [✅] | Expected: Allowed. Result: [✅] | Expected: Allowed. Result: [✅] |
| Decide a request | `/reviews/<id>` | Expected: 403. Result: [✅] | Expected: Allowed. Result: [✅] | Expected: Allowed. Result: [✅] |
| Decisions history | `/reviews/history` | Expected: 403. Result: [✅] | Expected: Allowed. Result: [✅] | Expected: Allowed. Result: [✅] |
| View indicators | `/reviews/indicators` | Expected: 403. Result: [✅] | Expected: Allowed. Result: [✅] | Expected: Allowed. Result: [✅] |
| Test models | `/credit/models/` | Expected: Allowed to view the comparison, not to run a prediction. Result: [✅] | Expected: Allowed, with prediction. Result: [✅] | Expected: Allowed, with prediction. Result: [✅] |
| Users and roles | `/admin/` | Expected: 403. Result: [✅] | Expected: 403. Result: [✅] | Expected: Allowed. Result: [✅] |
| Categories, monitoring, reports | `/admin/categories`, `/admin/monitoring`, `/admin/reports` | Expected: 403. Result: [✅] | Expected: 403. Result: [✅] | Expected: Allowed. Result: [✅] |
| Public pages | `/`, `/methodology/`, `/resources` | Expected: Allowed. Result: [✅] | Expected: Allowed. Result: [✅] | Expected: Allowed. Result: [✅] |

## Sidebar menu seen by each role

| Role | Expected items | Result |
| --- | --- | --- |
| Applicant | Dashboard, My finances, New request, My requests | [✅] |
| Analyst | Review queue, Decisions history, Indicators, Model testing | [✅] |
| Administrator | Users and roles, Categories, Monitoring, Reports, Review queue, Decisions history, Indicators, Model testing | [✅] |

## Direct URL checks

| Test | Expected | Result |
| --- | --- | --- |
| Logged out, open `/dashboard/` | Redirected to login | [✅] |
| As Account A, type `/admin/` in the address bar | 403 | [✅] |
| As Account A, type `/reviews/` in the address bar | 403 | [✅] |
| As Account B, type `/credit/` in the address bar | 403 | [✅] |
| As Account C, type `/credit/` in the address bar | 403 | [✅] |

## Observations

- All restrictions and permissions evaluated via navigation, sidebar menus, and direct URL entry behaved precisely as designed in the backend access rules.
- The administrator does not create requests or record finances: those pages are for applicants only.

## Conclusion

All role and page combinations successfully matched the expected behavior, confirming that the Role-Based Access Control (RBAC) segregation of duties is fully functional and secure on the published Render deployment.