# Credit Risk and Loan Viability Prediction Platform: A Machine Learning–Based Web System for Lending Decision Support

## 1. Problem Statement
Credit risk is one of the main sources of vulnerability in banking systems worldwide. The Basel Committee on Banking Supervision (2017) requires institutions to hold capital proportional to their credit exposure, because misjudged lending produces non-performing loans, provisioning costs, and reduced capital available for new credit. Evidence shows that traditional scorecards and manual analyst reviews are limited in capturing non-linear relationships among borrower attributes, whereas machine learning (ML) classifiers consistently deliver better discrimination between good and bad borrowers (Lessmann et al., 2015; Dastile et al., 2020). In emerging economies such as Colombia, where many applicants have thin credit files and household indebtedness is rising, approving non-viable loans increases default rates, while rejecting viable ones excludes customers and wastes revenue. Manual evaluation is also slow and inconsistent across analysts, reducing operational efficiency. A predictive system is therefore needed to estimate loan viability objectively and quickly from variables such as age, income, employment status, credit history, debt-to-income ratio, loan amount, and term, while providing explanations that support auditable decisions (Bussmann et al., 2021).

## 2. Objectives
**General Objective:** Develop a web-based platform that predicts loan viability from customer financial information using machine learning to support credit decision-making in financial institutions.

**Specific Objectives:**
1. Elicit and document functional and non-functional requirements through analysis of the credit evaluation process and its data sources.
2. Build a cleaned and validated dataset through exploratory analysis, feature engineering, and class-imbalance treatment.
3. Train, compare, and select a classification model (e.g., logistic regression, random forest, XGBoost) using metrics such as AUC-ROC, recall, and F1-score, including explainability outputs.
4. Implement, test, and deploy a web application with an API that returns the viability prediction, risk score, and key decision factors.

## 3. Software Engineering Methodology
Systematic methodologies reduce project risk, ensure traceability between needs and deliverables, and improve the quality and maintainability of data-intensive systems. The project will follow an iterative, Scrum-based process covering the full life cycle: **requirements analysis** (user stories and acceptance criteria), **design** (layered architecture, UML diagrams, REST API specification), **implementation** (Python, a web framework, and a relational database), **testing** (unit, integration, and model validation tests), **deployment** (containerization with Docker and a CI/CD pipeline), and **maintenance** (performance monitoring and periodic retraining). Best practices include Git version control with branching, code reviews, automated testing, documentation, and data privacy safeguards.

## 4. Reference Framework (Literature Review)
Lessmann et al. (2015) benchmarked 41 classifiers on multiple credit datasets and found that ensemble methods significantly outperform individual classifiers and the industry-standard logistic regression. Dastile et al. (2020) reviewed statistical and ML credit scoring models, reporting a shift toward ensembles and deep learning but highlighting a lack of interpretability. Gunnarsson et al. (2021) showed that deep neural networks bring only marginal gains over well-tuned gradient boosting on tabular credit data, favoring simpler models in practice. Chen and Guestrin (2016) introduced XGBoost, now widely used in default prediction due to its accuracy and efficiency. Regarding adoption, Bussmann et al. (2021) demonstrated that explainable AI (Shapley values) can make ML credit models transparent for risk managers and regulators. Together, these studies support using tuned ensemble models with explainability within an accessible decision-support platform.

## 5. CRISP-DM Methodology
**Business Understanding:** define viability criteria, success metrics, and risk costs of false approvals and false rejections with stakeholders. **Data Understanding:** collect public credit datasets, describe variables, and examine quality, distributions, and correlations. **Data Preparation:** handle missing values and outliers, encode categorical features, scale variables, create ratios, and apply resampling (e.g., SMOTE) with a stratified train/test split. **Modeling:** train baseline and ensemble models with cross-validation and hyperparameter tuning. **Evaluation:** assess models using AUC-ROC, precision, recall, F1-score, and cost-sensitive analysis, along with fairness and explainability checks against business goals. **Deployment:** expose the chosen model through an API integrated into the web platform, with monitoring and a retraining plan.

## 6. Bibliographic References
Basel Committee on Banking Supervision. (2017). *Basel III: Finalising post-crisis reforms*. Bank for International Settlements. https://www.bis.org/bcbs/publ/d424.htm

Bussmann, N., Giudici, P., Marinelli, D., & Papenbrock, J. (2021). Explainable machine learning in credit risk management. *Computational Economics, 57*(1), 203–216. https://doi.org/10.1007/s10614-020-10042-0

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 785–794). ACM. https://doi.org/10.1145/2939672.2939785

Dastile, X., Celik, T., & Potsane, M. (2020). Statistical and machine learning models in credit scoring: A systematic literature survey. *Applied Soft Computing, 91*, Article 106263. https://doi.org/10.1016/j.asoc.2020.106263

Gunnarsson, B. R., vanden Broucke, S., Baesens, B., Óskarsdóttir, M., & Lemahieu, W. (2021). Deep learning for credit scoring: Do or don't? *European Journal of Operational Research, 295*(1), 292–305. https://doi.org/10.1016/j.ejor.2021.03.006

Lessmann, S., Baesens, B., Seow, H.-V., & Thomas, L. C. (2015). Benchmarking state-of-the-art classification algorithms for credit scoring: An update of research. *European Journal of Operational Research, 247*(1), 124–136. https://doi.org/10.1016/j.ejor.2015.05.030
