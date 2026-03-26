from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost model for fog vs non-fog classification.")
    parser.add_argument("--features-csv", type=Path, required=True, help="CSV produced by prepare_features.py")
    parser.add_argument("--model-out", type=Path, default=Path("models") / "xgboost_fog.joblib")
    parser.add_argument("--metrics-out", type=Path, default=Path("models") / "metrics.json")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.features_csv)
    if "label" not in df.columns:
        raise ValueError("Input CSV must contain a 'label' column.")

    labels = df["label"]
    if labels.nunique() < 2:
        raise ValueError("Need both classes (fog=1, non-fog=0) to train. Add negative images first.")

    feature_columns = [c for c in df.columns if c not in {"label", "image_path"}]
    x = df[feature_columns]
    y = labels

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=y,
    )

    model = XGBClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=args.seed,
        eval_metric="logloss",
    )
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "train_samples": int(len(x_train)),
        "test_samples": int(len(x_test)),
        "num_features": int(len(feature_columns)),
    }

    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)

    bundle = {"model": model, "feature_columns": feature_columns}
    joblib.dump(bundle, args.model_out)
    args.metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"Model saved to: {args.model_out}")
    print(f"Metrics saved to: {args.metrics_out}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
