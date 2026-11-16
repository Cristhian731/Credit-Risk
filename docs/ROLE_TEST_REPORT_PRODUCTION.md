# Role / Account Test Report

> **Note.** This test was made on the published site with the previous version of the system, which had no roles: all three accounts are standard users. The personal e-mail addresses of the original document were replaced by Account A, B and C. The test of the access rules of the three current roles is in [ROLE_TEST_REPORT.md](ROLE_TEST_REPORT.md).

Published app tested: https://credit-risk-dxit.onrender.com/dashboard/Date: 15/11/2026

## Accounts tested

| Account | Email | Username | Intended profile |
|---|---|---|---|
| A | Account A | admin | Admin user |
| B | Account B | Account B | Standard user |
| C | Account C | Account C | Standard user |

## Account A

1. Account A: login. Logged in with Account A. Landed on: /dashboard/. Username in top bar: Yes (displays 'admin' next to the Log out button).

2. Account A: Dashboard. Totals displayed on dashboard cards — Income: 5.00 | Expenses: 5.00 | Balance: 0.00 | Credit evaluations: 1. [Note: Attach updated screenshot showing the address bar with https://credit-risk-dxit.onrender.com/dashboard/]

3. Account A: Transactions. Rows visible: 2 recorded transactions matching the dashboard totals (1 Income of 5.00 and 1 Expense of 5.00). Anything not yours: No, all records belong exclusively to Account A.

4. Account A: Evaluation history. Rows visible: 1 evaluation record matching the dashboard card count. Anything not yours: No, only Account A's evaluation is displayed.

## Account B

5. Account B: login. Logged in with Account B. Landed on: /dashboard/. Username in top bar: Yes ('Account B' appears in the top navigation bar along with the confirmation banner 'You have successfully logged in.').

6. Account B: Dashboard. Totals displayed on dashboard cards — Income: 0.00 | Expenses: 0.00 | Balance: 0.00 | Credit evaluations: 0. [Note: Attach updated screenshot showing the address bar with https://credit-risk-dxit.onrender.com/dashboard/]

7. Account B: Transactions. Rows visible: 0 (empty transaction list, consistent with Income: 0.00 and Expenses: 0.00 on the Dashboard). Anything not yours: No.

8. Account B: Evaluation history. Rows visible: 0 (empty evaluation history, consistent with Credit evaluations: 0 on the Dashboard). Anything not yours: No.

## Account C

9. Account C: login. Logged in with Account C. Landed on: /dashboard/. Username in top bar: Yes ('Account C' appears in the top navigation bar).

10. Account C: Dashboard. Totals displayed on dashboard cards — Income: 0.00 | Expenses: 0.00 | Balance: 0.00 | Credit evaluations: 0. [Note: Attach updated screenshot showing the address bar with https://credit-risk-dxit.onrender.com/dashboard/]

11. Account C: Transactions. Rows visible: 0 (empty transaction list, matching the Dashboard totals of 0.00). Anything not yours: No.

12. Account C: Evaluation history. Rows visible: 0 (empty evaluation history, matching the Dashboard count of 0). Anything not yours: No.

## Isolation and Access Control Tests

Procedure: Created a test transaction (ID #1) and a credit evaluation (ID #1) under Account A, logged out, and logged in as Account B to verify cross-account access restrictions via direct URLs.

13. Another account's transaction. As Account B, navigated directly to https://credit-risk-dxit.onrender.com/transactions/1/edit and /transactions/1/delete (belonging to Account A). Expected: 404 Page Not Found. Observed: Verified — the application returned a 404 Page Not Found error on both routes, blocking unauthorized viewing, editing, or deletion.

14. Another account's evaluation. As Account B, navigated directly to https://credit-risk-dxit.onrender.com/credit/result/1 and /credit/history/1/delete (belonging to Account A). Expected: 404 Page Not Found. Observed: Verified — the application returned a 404 Page Not Found error on both routes, preventing cross-account data exposure.

15. Logged-out access. Logged out completely and attempted to open https://credit-risk-dxit.onrender.com/dashboard/, /transactions/, and /credit/ directly in the browser. Expected: Redirect to login page. Observed: Verified — all three protected routes immediately redirected to the login card and restored the requested destination after authentication.

## Summary

| Account | Sees own data | Sees other accounts' data | Differences from the others | Notes |
|---|---|---|---|---|
| A | Yes | No | None (standard user permissions) | Dashboard totals (Income 5.00, Expenses 5.00, 1 evaluation) match transaction and evaluation rows. |
| B | Yes | No | None (standard user permissions) | Clean account state (0.00 totals, 0 rows); cross-account URL access to Account A IDs returned 404. |
| C | Yes | No | None (standard user permissions) | Clean account state (0.00 totals, 0 rows); complete data isolation confirmed. |

| Conclusion: All three standard user accounts (A, B, and C) operate with identical role permissions and strict multi-tenant data isolation on https://credit-risk-dxit.onrender.com/dashboard/. Every account views only its own transactions and credit evaluations, dashboard totals align accurately with stored records, unauthenticated requests redirect properly to login, and direct URL attempts to access or modify another user's records return HTTP 404 as expected. |
|---|
