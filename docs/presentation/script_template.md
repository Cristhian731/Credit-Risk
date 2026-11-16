# Presentation Script: Credit Risk Intelligent System

20-minute video presentation · 3 presenters · CRISP-ML(Q)

How to use this document: Text in [brackets] must be replaced with real information from your project (results, URL, names, metrics). Member 1, 2 and 3 are placeholders for your names. Lines marked [Show] or [Live] are on-screen actions, not spoken text.

## Time and speaker plan

Approximate speaking time: Member 1 ≈ 7 min, Member 2 ≈ 6.5 min, Member 3 ≈ 6.5 min.

| Time | Section | Speaker |
|---|---|---|
| 0:00–2:00 | Team, title, problem | Member 1 |
| 2:00–3:00 | Justification and objectives | Member 2 |
| 3:00–4:00 | Reference framework | Member 3 |
| 4:00–6:00 | CRISP-ML phases 1–2: business and data understanding | Member 1 |
| 6:00–8:00 | Phase 3: data preparation | Member 2 |
| 8:00–10:00 | Phases 4–5: modeling, evaluation, model selection | Member 3 |
| 10:00–12:00 | Demo: architecture, registration, login, roles | Member 1 |
| 12:00–14:30 | Demo: business data management and model execution | Member 2 |
| 14:30–17:00 | Demo: output interpretation and decision | Member 3 |
| 17:00–18:00 | Schedule and objective achievement | Member 1 |
| 18:00–19:00 | Monitoring, maintenance, limitations | Member 2 |
| 19:00–20:00 | Conclusions, future work, documentation | Member 3 |

## 0:00–4:00 | Introduction

**Member 1 (0:00–2:00): Team, title and problem**

Good [morning / afternoon]. We are [Name 1], [Name 2] and [Name 3], and today we present [Project title], an intelligent credit risk system.

Financial institutions must decide whether to grant a loan with limited information. If they approve a client who later defaults, they lose money. If they reject a good client, they lose business. The problem we address is: [state the problem from your report, e.g., how to estimate, before approval, the probability that an applicant will default].

Today we will show the data, the model we selected, and a published system where an analyst can use that model to make real decisions.

**Member 2 (2:00–3:00): Justification and objectives**

Why does this matter? [Justification: current manual process, cost of errors, need for consistency and speed].

Our general objective was to [general objective]. Our specific objectives were: first, [objective 1, e.g., prepare and analyze the dataset]; second, [objective 2, e.g., train and compare models]; third, [objective 3, e.g., deploy a web system with authentication and roles]. We will return to these at the end and show which ones we achieved, with evidence.

**Member 3 (3:00–4:00): Reference framework**

Our work follows CRISP-ML(Q), a methodology that extends CRISP-DM with quality assurance and monitoring. Our theoretical framework covers credit risk and credit scoring, [classification algorithms used], and evaluation metrics such as [precision, recall, F1, AUC-ROC]. Our main references are [2–3 key references]. The full list is available in our documentation.

## 4:00–10:00 | The CRISP-ML phases

**Member 1 (4:00–6:00): Phases 1 and 2**

Phase 1 is business and data understanding. The business goal is [goal], and success means [criterion, e.g., recall above X for the default class].

Phase 2 is data understanding. We used [dataset name and source], with [N rows] and [N variables]. The target variable is [name].

[Show] class distribution and key charts.

We found [class imbalance, missing values, outliers, etc.], and that shaped our next decisions.

**Member 2 (6:00–8:00): Phase 3, data preparation**

Data preparation is where we spent most of our effort.

[Show] before and after of the data, or the notebook.

We handled missing values with [method], encoded categorical variables with [method], and scaled numeric variables with [method]. We treated class imbalance with [SMOTE / class weights / none]. We split the data [e.g., 80/20, stratified] and applied the transformations only after splitting to avoid data leakage.

The same preprocessing is reused in the deployed system through [saved pipeline, e.g., a joblib/pkl file], so training and production stay consistent.

**Member 3 (8:00–10:00): Phases 4 and 5, modeling, evaluation and selection**

We compared [number] models: [e.g., Logistic Regression, Random Forest, XGBoost].

[Show] the comparison table.

| Model | Accuracy | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|
| [Model A] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [Model B] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [Model C] | [ ] | [ ] | [ ] | [ ] | [ ] |

We selected [model] because [reason, e.g., best recall on the default class, which matters because approving a defaulter costs more than rejecting a good client]. Its confusion matrix shows [interpretation]. We tuned hyperparameters with [method] and validated with [cross-validation / hold-out].

Phase 6, deployment, is what we show next.

## 10:00–17:00 | Live demonstration

**Member 1 (10:00–12:00): Architecture, registration, login and roles**

The system is published at [URL]. It uses [frontend], [backend], [database] and [hosting platform], and loads the trained model for inference.

[Live] Register a new user.

I will register a user with the role [e.g., Analyst].

[Live] Log in.

Now I am authenticated. The system has [N] roles. As an [Analyst] I can [permissions].

[Live] Log in as Admin, or try a restricted URL as Analyst.

As [Admin] I can also [manage users, view reports]. If an Analyst tries to open an admin page, access is denied. That is our role-based protection.

**Member 2 (12:00–14:30): Business data management and model execution**

Now the business process.

[Live] Open the clients / applications module.

I will create a new applicant with [fields: age, income, loan amount, credit history, etc.].

[Live] Also edit or delete a record, and show that the data persists.

These are the same variables the model was trained on, which connects the data we prepared to the system.

Now I run the model.

[Live] Click [Evaluate risk].

The system sends the data through the same preprocessing pipeline and calls the [selected model]. The result is [probability X% / class High Risk].

**Member 3 (14:30–17:00): Interpretation and decision**

Let us interpret this output. The model returned a default probability of [X%], which falls in the [risk level] category under our threshold of [threshold]. The main factors were [top features, if shown].

[Live] Show the decision action.

Based on this, the analyst can [approve / reject / request more guarantees / send to manual review], and the system [records the decision and result in the history].

[Show] the history or dashboard.

To summarize the complete case: authenticated access, applicant data entered, model executed, result interpreted, and a decision recorded. That is the original problem addressed end to end, using the data and the model we described.

## 17:00–20:00 | Results, limitations and closing

**Member 1 (17:00–18:00): Schedule and objective achievement**

Our schedule followed the CRISP-ML phases: [weeks / dates per phase].

[Show] Gantt chart or schedule table.

Regarding objectives: objective 1 was achieved, shown by [evidence]. Objective 2 was achieved, shown by [comparison table]. Objective 3 was achieved, shown by the live system. [Mention honestly any objective that was only partially achieved.]

**Member 2 (18:00–19:00): Monitoring, maintenance and limitations**

For monitoring and maintenance we have [logs, versioned model, repository commits, planned drift checks].

[Show] the evidence.

Our limitations are: [small or dated dataset, no real bank data, class imbalance, no fairness audit, no automatic retraining]. We want to be clear that these results come from [dataset], not from a real institution's portfolio.

**Member 3 (19:00–20:00): Conclusions, future work and documentation**

Demonstrated: we built a working system that predicts default risk with [metric] and supports a decision workflow with secure access.

Expected, but not yet demonstrated: reduced losses or faster approvals in a real environment.

Future work: [retraining with new data, explainability with SHAP, drift monitoring, integration with real systems].

Our code and documentation are in the GitHub repository [link], and the references are in [section / file]. Thank you. We are happy to answer questions.

## Requirements checklist

- Every member speaks substantially and equitably.
- Every member explains technical or methodological content and shows evidence.
- The published application is demonstrated, including protected modules.

## Notas de producción (en español)

- Ensayen con cronómetro. La demo (7 min) es lo que más se desvía; practíquenla varias veces.
- Preparen la demo antes: usuarios de prueba ya creados, un solicitante de respaldo y la app abierta en otra pestaña por si falla la conexión.
- Pantalla legible: zoom del navegador al 125–150 % y una sola ventana compartida.
- Audio: usen micrófonos similares y revisen que el enlace del video abra en una ventana de incógnito.
- Transiciones: cada persona cierra con una frase como "Now [Name] will continue with…".
- Honestidad en los resultados: distingan siempre lo demostrado (métricas reales, sistema funcionando) de lo esperado (beneficios futuros).

Complete case shown: authenticated access, data management, model execution, output interpretation, decision or action.

Relationship explained: problem → data → selected model → implemented system.

Conclusions backed by actual results; demonstrated outcomes clearly separated from expected future benefits.

Clear audio, readable on-screen content, accessible video link.
