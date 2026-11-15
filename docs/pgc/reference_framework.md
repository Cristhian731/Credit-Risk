# Reference Framework

## Background

Credit risk is the possibility that a borrower does not repay a loan. It is one of the main sources of vulnerability of banks: the Basel Committee on Banking Supervision (2017) asks institutions to hold capital in proportion to their credit exposure, because wrong lending decisions produce non-performing loans and provisioning costs. Approving a loan that will not be repaid costs money; rejecting a loan that would have been repaid excludes a customer and loses revenue. A decision-support system tries to reduce both errors while keeping the final decision with a person.

## Related studies

Lessmann et al. (2015) compared 41 classifiers on several credit datasets and found that ensemble methods outperform individual classifiers and the industry-standard logistic regression. Dastile et al. (2020) reviewed statistical and machine learning models for credit scoring and described a move toward ensembles and deep learning, with a lack of interpretability as the main weakness. Gunnarsson et al. (2021) showed that deep neural networks give only marginal gains over well-tuned gradient boosting on tabular credit data, so simpler models are preferable in practice. Chen and Guestrin (2016) introduced XGBoost, widely used for default prediction because of its accuracy and efficiency. Bussmann et al. (2021) showed that explainable techniques, such as Shapley values, make machine learning credit models understandable for risk managers and regulators. For this project, the studies support a tuned model compared against a logistic regression baseline, used inside a platform where an analyst reviews and justifies each decision.

## Key concepts

- **Credit risk:** probability that a borrower fails to meet the payment obligations of a loan.
- **Default:** the borrower does not repay the loan as agreed. In the dataset of the project it is the positive class of the classification.
- **Classification:** a machine learning task that assigns each example to a class (here, repaid or defaulted) and gives a probability.
- **ROC AUC:** probability that the model gives a higher risk to a borrower that defaulted than to one that repaid; 0.5 is chance and 1.0 is perfect.
- **Recall:** share of the real defaulters that the model detects. A low recall means many defaulters are approved.
- **Cross-validation:** repeated training and testing on different parts of the data to estimate how the model behaves on new data.
- **Champion model:** the model selected for production after comparing the candidates with the same metrics.
- **Model versioning and monitoring:** each prediction stores the version of the model; real outcomes are compared with the predictions to decide when to retrain.
- **CRISP-ML(Q):** process model for machine learning projects with quality assurance, with six phases from business understanding to monitoring and maintenance.

## References

Basel Committee on Banking Supervision. (2017). *Basel III: Finalising post-crisis reforms*. Bank for International Settlements. https://www.bis.org/bcbs/publ/d424.htm

Bussmann, N., Giudici, P., Marinelli, D., & Papenbrock, J. (2021). Explainable machine learning in credit risk management. *Computational Economics, 57*(1), 203–216. https://doi.org/10.1007/s10614-020-10042-0

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. In *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (pp. 785–794). ACM. https://doi.org/10.1145/2939672.2939785

Dastile, X., Celik, T., & Potsane, M. (2020). Statistical and machine learning models in credit scoring: A systematic literature survey. *Applied Soft Computing, 91*, Article 106263. https://doi.org/10.1016/j.asoc.2020.106263

Gunnarsson, B. R., vanden Broucke, S., Baesens, B., Óskarsdóttir, M., & Lemahieu, W. (2021). Deep learning for credit scoring: Do or don't? *European Journal of Operational Research, 295*(1), 292–305. https://doi.org/10.1016/j.ejor.2021.03.006

Lessmann, S., Baesens, B., Seow, H.-V., & Thomas, L. C. (2015). Benchmarking state-of-the-art classification algorithms for credit scoring: An update of research. *European Journal of Operational Research, 247*(1), 124–136. https://doi.org/10.1016/j.ejor.2015.05.030
