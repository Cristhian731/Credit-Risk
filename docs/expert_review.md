---
status: not_conducted
---
Review of the credit risk models by a domain expert: NOT CONDUCTED.

No interview or review with a domain expert (for example a credit analyst of a lending institution) took
place during this project. Nothing in this repository, in the Methodology pages or in the technical report is
based on the opinion of an expert. This is a limitation of the project.

This file is shown in Phase 4 of the Methodology pages. The questionnaire below is the validation protocol that
MUST be completed with a domain expert before the models are used in any real credit decision. If a review is
done in the future, fill in the header (`status: complete`, `name`, `role`, `organization`, `date`), add the
answers under each question and write the conclusions; the page will then show the expert and the answers.

Questionnaire for the domain expert

Q1. The model uses nine data of the applicant: age, income, loan amount, credit score, months employed,
number of credit lines, loan term, debt-to-income ratio and employment type. Do they make sense to assess a
loan? Is any indispensable one missing, or any one unnecessary?

Q2. The official model finds about 66 of every 100 applicants who really default (the rest are missed). Is that
level of detection acceptable for a support tool? What level would you expect?

Q3. To find more defaulters, the model also flags many applicants who would have repaid: about 20 of every 100
flagged applicants really default. In your experience, what costs more: rejecting (or asking for more
guarantees from) a good customer, or approving one who does not repay? Can you give an approximate ratio?

Q4. The model flags many more young applicants (ages 18 to 24, about 85%) than older ones (ages 55 to 69, about
6%), partly because young applicants default more in the data. Is it acceptable to use the age in the
assessment? Is there a regulation or a policy in your institution about it?

Q5. If the age were removed, the model would flag every age range at a similar rate, but its overall accuracy
would be lower. Which mitigation would you prefer: remove the age, use different thresholds by group, or keep the
age with human review of the rejections of young applicants?

Q6. The tool labels an application as Approved below 33% of estimated risk, Medium Risk from 33% to 66% and
High Risk above 66%. Are those cut-offs reasonable? What action would your institution take in each category?

Q7. In the data, some applicants have more months of employment than they could have worked at their age. Have
you seen something like this in real data? How would you treat it?

Q8. Would you use this tool as a support in your work? For which cases yes and for which not? What would you need
(more information, explanations, another format) to trust it?
