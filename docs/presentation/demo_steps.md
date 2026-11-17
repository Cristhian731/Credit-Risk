# Demo Steps: Roles and Access Control

Target length: 2 min 30 s. Published app: https://credit-risk-dxit.onrender.com

Before recording: open the URL a few minutes earlier so the free server is awake, and use one browser window per account (or a private window) to avoid logging out each time.

| Time | Account | What to show | What to say |
| --- | --- | --- | --- |
| 0:00–0:15 | None | Home page, then the login page | The system has three roles: applicant, analyst and administrator. Each one sees only its own pages. |
| 0:15–1:00 | Account A (Applicant) | Login, Dashboard, My finances (add one transaction), New request (send a request), My requests | The applicant records income and expenses and sends a credit request. The model scores it and it stays pending. |
| 1:00–1:15 | Account A | Type `/admin/` in the address bar | A role that is not allowed gets a 403 page. The check runs on the server, not only in the menu. |
| 1:15–1:50 | Account B (Analyst) | Login, Review queue, open the request from Account A, register a decision, Indicators | The analyst reviews the queue, sees the model result and decides. The decision is stored with the request. |
| 1:50–2:00 | Account B | Type `/credit/` in the address bar | The analyst cannot create requests: 403. |
| 2:00–2:25 | Account C (Administrator) | Login, Users and roles, Monitoring, Reports | The administrator manages roles and categories and watches the model monitoring and the reports. |
| 2:25–2:30 | None | Back to the login or home page | Three roles, each with its own permissions, tested on the published system. |

## Checklist before recording

- The three accounts log in without errors.
- Account A has at least one transaction, so the request form fills its data.
- There is one pending request for Account B to decide.
- Rehearse once with a timer and cut anything that goes over 2:30.