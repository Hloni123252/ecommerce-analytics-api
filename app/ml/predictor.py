"""
Churn prediction model — training and inference.
"""
from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score

from app.ml.features import FEATURE_COLUMNS


# Where the trained model lives
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "churn_model.joblib"


def is_model_trained() -> bool:
    """Check if a trained model exists on disk."""
    return MODEL_PATH.exists()


def train_model(df: pd.DataFrame) -> dict:
    """
    Train a RandomForest on the feature DataFrame.
    
    Returns evaluation metrics.
    """
    # Only train on customers who have at least one order
    df_train = df[df["total_orders"] > 0].copy()

    X = df_train[FEATURE_COLUMNS].fillna(0)
    y = df_train["churned"]

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
    )

    # Train
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "training_rows": len(df_train),
        "churn_rate": round(float(y.mean()), 4),
    }

    # Feature importance
    importance = dict(zip(FEATURE_COLUMNS, [round(float(v), 4) for v in model.feature_importances_]))

    # Save
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    return {"metrics": metrics, "feature_importance": importance}


def load_model() -> RandomForestClassifier:
    """Load the trained model from disk. Raises if not found."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Model not trained yet. Call POST /ml/train first."
        )
    return joblib.load(MODEL_PATH)


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Predict churn probability for each row.
    
    Returns the input DataFrame with added 'churn_probability' and 'risk_level' columns.
    """
    model = load_model()

    X = df[FEATURE_COLUMNS].fillna(0)
    probs = model.predict_proba(X)[:, 1]

    result = df.copy()
    result["churn_probability"] = [round(float(p), 4) for p in probs]
    result["risk_level"] = [
        "high" if p >= 0.7 else "medium" if p >= 0.4 else "low"
        for p in probs
    ]

    return result