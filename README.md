## 🤖 ML: Churn Prediction

Trained a Random Forest classifier to predict customer churn.

**Features:** RFM-style (recency, frequency, monetary) + customer tenure
**Split:** Time-based — features from the past, label from the future (prevents data leakage)
**Metrics:** 82.7% accuracy, 50% recall, 30.8% precision
**Note:** The 10.4% churn rate creates class imbalance. In production, precision can be improved with threshold tuning or SMOTE.

Endpoints:
- `POST /ml/train` — retrain the model
- `GET /ml/churn?limit=20` — top at-risk customers
- `GET /ml/churn/{customer_id}` — single customer risk
