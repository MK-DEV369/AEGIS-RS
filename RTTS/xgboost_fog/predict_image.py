from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from prepare_features import extract_fog_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict fog probability for a single image.")
    parser.add_argument("--model", type=Path, required=True, help="Path to trained model bundle (.joblib)")
    parser.add_argument("--image", type=Path, required=True, help="Image to classify")
    parser.add_argument("--image-size", type=int, default=256)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    bundle = joblib.load(args.model)
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    features = extract_fog_features(args.image, image_size=args.image_size)
    if features is None:
        raise RuntimeError(f"Could not read image: {args.image}")

    x = pd.DataFrame([features])[feature_columns]
    fog_prob = float(model.predict_proba(x)[0, 1])
    prediction = int(fog_prob >= 0.5)

    print(f"Image: {args.image}")
    print(f"Fog probability: {fog_prob:.4f}")
    print(f"Prediction (1=fog, 0=non-fog): {prediction}")


if __name__ == "__main__":
    main()
