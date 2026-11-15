# System Design (Activity 2)

## Purpose and scope

This section designs the information system that wraps the credit risk champion model: who uses it, which business process it supports, which rules it enforces, how it is built and where the machine learning model helps a decision. The model supports a decision of a person and never replaces it: the credit analyst decides, and the system records whether the analyst followed or contradicted the model.

## Users and roles

The system has three roles. The registration always creates an Applicant. Only an Administrator changes the role of a user, and nobody can assign privileges to themselves.

| Role | Who | What the role does |
|---|---|---|
| Applicant | Person who asks for a loan | Keeps personal finances, requests credits, follows the status, edits or withdraws open requests |
| Credit Analyst | Employee of the lender | Reviews the queue, decides with a justification, records the real outcome, reads indicators, tests the models |
| Administrator | System owner | Manages users, roles and categories, reads monitoring and reports, can do everything an analyst does |

## Business process

1. The Applicant creates a credit request. The form is prefilled from the finances of the applicant. The first request creates the Client of the applicant automatically, with the name and document of the user.
2. The server scores the request with the champion model, using the same preprocessing and features as in training. The request is stored with the risk label, the risk percentage and the model version, in the status Pending.
3. The Analyst reviews the request. The review is mandatory when the risk is High Risk or the applicant is 18 to 24 years old, and those requests are shown first in the queue.
4. The Analyst decides Approve, Reject or Request documents, always with a written justification. The system stores whether the decision followed the model.
5. The Applicant sees the status and the justification. In the status Documents requested or Pending, the Applicant can edit or withdraw the request; an update from Documents requested returns the request to Pending and it is scored again.
6. Later, an Analyst or Administrator records the real outcome (Repaid or Defaulted) of an Approved request. These outcomes feed the monitoring of the model.

*Figure: Life cycle of a credit request* (act2_status_flow.png). The statuses Approved, Rejected and Withdrawn are final.

| Status | Meaning | Next statuses |
|---|---|---|
| Pending | Scored and waiting for an analyst | Approved, Rejected, Documents requested, Withdrawn |
| Documents requested | The analyst needs more information | Pending (after an update by the Applicant), Withdrawn |
| Approved | Credit granted | None; the outcome can be recorded once |
| Rejected | Credit denied | None |
| Withdrawn | Cancelled by the Applicant | None |

## Functional requirements

| Id | Requirement |
|---|---|
| FR1 | Register, log in and log out. The registration creates an Applicant. |
| FR2 | The Applicant manages their own transactions, categories and budgets (create, read, update, delete). |
| FR3 | The Applicant creates a credit request prefilled from their finances; the Client is created automatically on the first request. |
| FR4 | The server scores each request with the champion and stores label, percentage and model version. |
| FR5 | The Applicant lists their own requests with the status and the decision justification. |
| FR6 | The Applicant edits or withdraws a request in the status Pending or Documents requested. |
| FR7 | The Analyst sees a queue ordered by mandatory review first and then by age of the request. |
| FR8 | The Analyst decides Approve, Reject or Request documents with a justification. |
| FR9 | The Analyst or Administrator records the outcome of an Approved request. |
| FR10 | The Analyst reads the indicators and tests the candidate models. |
| FR11 | The Administrator manages users and roles, categories, monitoring and reports. |
| FR12 | Every inference is stored in a database table with its date, user, model, version, result, response time and error. |
| FR13 | Public pages show the documentation of the project, the methodology, the model results (read only) and the resources. |

## Business rules

| Id | Rule |
|---|---|
| BR1 | The registration cannot choose a role. Only an Administrator changes roles, and the last Administrator cannot be demoted. |
| BR2 | Authorization is checked on the server in every route. An Applicant only reads and changes their own data. |
| BR3 | A request has no automatic decision: every request waits for an Analyst. |
| BR4 | A request is flagged for mandatory review when the label is High Risk or the age is from 18 to 24. A Reject of an applicant aged 18 to 24 is a special case: its justification must state that a human reviewed it. |
| BR5 | Every decision (Approve, Reject and Request documents) needs a non-empty justification of at least 10 characters. A decision is final, except Request documents. |
| BR6 | The outcome can be recorded only for Approved requests, only once, and only by an Analyst or Administrator. |
| BR7 | The system stores whether the decision followed the model, only when the model gives a clear recommendation: a Low Risk label with Approve, or a High Risk label with Reject, follows it (true); a Low Risk label with Reject, or a High Risk label with Approve, contradicts it (false). Medium Risk requests and Request documents decisions count as no clear recommendation and are reported apart in the indicators. |
| BR11 | The first Administrator and the test account of each role are created only with the command line (`flask --app run create-user --role admin`), with the password read from an environment variable. They are never created from the web and never stored in the repository. In Render they are created with the same command and variables. |
| BR8 | Indicators, totals and rates are never stored: they are calculated when they are read. |
| BR9 | The document number is unique per user, and the form validates ranges (age, income, score from 300 to 850, term in months). |
| BR10 | The data of the inference log hold no password and no document number. |

## Modules and architecture

The application keeps the current Flask blueprints and adds three: reviews (analyst queue and decisions), administration (users, categories, monitoring) and public pages. All blueprints use one authorization decorator, `roles_required`, and one repository layer. The model is loaded once on the server and called through the same function that is used for training features (`ml.features`). The database is SQLite in development and PostgreSQL in Render, managed with Alembic migrations that have a downgrade. The inference log is a table, because the disk of Render is not persistent; the JSON lines file is kept only as a local copy.

*Figure: Architecture of the system* (act2_architecture.png). Browser, Flask blueprints, services, model artifacts and database.

## Data model

*Figure: Entity relationship diagram* (act2_er_diagram.png). New or changed entities are the role of User, the status and outcome of CreditApplication, Review and InferenceLog.

| Entity | Main fields | Change |
|---|---|---|
| User | username, email, password hash, role | New field role (default Applicant) |
| Client | full name, document number, user | Kept; created automatically |
| CreditApplication | nine model inputs, risk label, risk percentage, model version, status, outcome, outcome date, client, user | New fields status and outcome |
| Review | application, analyst, decision, justification, followed model (empty when there is no clear recommendation), mandatory, decided at | New |
| InferenceLog | date, user, model, model version, result, milliseconds, error | New |
| Transaction, Category, Budget | unchanged | None |

The migration adds the columns and tables with a downgrade, gives the existing users the role Applicant, and gives the existing applications the status Pending. The existing history is kept. A dated backup of the database is made before the migration.

## Menus

| Area | Item | Roles |
|---|---|---|
| Public | Home (project documentation), Methodology (six phases), Models (results, read only), Resources (report, repository, Colab, manuals, video), Login, Register | Everyone |
| Applicant | Dashboard, My finances (transactions, categories, budgets), New request, My requests | Applicant |
| Analyst | Review queue, Decisions history, Indicators, Model testing | Analyst, Administrator |
| Administrator | Users and roles, Categories, Monitoring, Reports | Administrator |

The public menu is a top bar before the login. After the login, the private area uses a sidebar with the items of the role and the public pages remain reachable from the top bar.

## Where the model helps

The model estimates the probability that an applicant defaults. It supports one decision: whether the analyst approves, rejects or asks for documents. It is not used to decide alone. Its limitations are shown with every result: the model was trained on a public dataset, it flags young applicants more often (hence the mandatory human review of 18 to 24), and the cost assumption of the errors is a team assumption.

## Visual direction

Palette: deep blue primary, teal accent, neutral grays, and the red and green of risk used only for risk labels. Typography: one sans-serif family for the whole interface and a monospace face only for numbers in tables. Public area: top bar, wide hero on the home page, content in cards. Private area: fixed sidebar with the items of the role, a page header with the title and the main action, and tables and forms with the same spacing. Every page must work on a phone width and keep a visible focus and sufficient contrast.

## Work plan

| Block | Content | Hours |
|---|---|---|
| D1 | Design (this section) | 1 |
| D2 | Roles, authorization decorator, menus and role tests | 4 |
| D3 | Request flow, review, outcome and tests | 6 |
| D4 | Inference log table, indicators, monitoring | 3 |
| D5 | Visual redesign | 3 |
| D6 | Basic home page with the project documentation | 1 |
| D8 | Deployment in Render, test accounts, manuals | 2 |
| Report | Activity 2 report | 3 |
| Total | | 23 |

If time runs short, the first items to cut are: the polish of the visual redesign beyond the sidebar and the palette, the exports of the reports, the training guide, and the detail of the monitoring page (the table and the response times stay). The role tests, the persistence and the deployment checks are never cut.

## Contract changes in block D2

- `User.role` (`applicant`, `analyst`, `admin`; default `applicant`; check constraint `ck_users_role`), added by migration `0003` with a downgrade. Existing users become applicants.
- `app.auth.services`: new `roles_required(*roles)`, `upsert_account`, `bootstrap_accounts` and `home_url_for`. `register_user` is unchanged and has no role parameter. `login_required` is kept but no route uses it.
- `app.menus`: `PUBLIC_MENU` and `MENU_BY_ROLE` list the pages of each role.
- New blueprints `reviews` (`/reviews`) and `admin` (`/admin`). Some of their pages are placeholders until blocks D3 and D4.
- The models page `/credit/models/` is public and read only; only analysts and administrators see the prediction forms and can post to `/credit/models/<name>/predict`.
- Commands `create-user` and `bootstrap-accounts`; `render.yaml` runs `bootstrap-accounts` at start with the four `BOOTSTRAP_*` values as `sync: false`.
- `/` no longer redirects a logged-in user: it stays public and each role lands on its own home after the login.
