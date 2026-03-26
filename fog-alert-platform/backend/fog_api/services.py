from __future__ import annotations

import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import joblib
import pandas as pd
from django.conf import settings


class FogPredictor:
    def __init__(self, model_path: Path, feature_script_dir: Path):
        self.model_path = Path(model_path)
        self.feature_script_dir = Path(feature_script_dir)
        self._model_bundle: dict | None = None

    def _ensure_model_loaded(self) -> dict:
        if self._model_bundle is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model file not found at {self.model_path}")
            self._model_bundle = joblib.load(self.model_path)
        return self._model_bundle

    def _extract_features(self, image_path: Path) -> dict[str, float]:
        if str(self.feature_script_dir) not in sys.path:
            sys.path.insert(0, str(self.feature_script_dir))

        from prepare_features import extract_fog_features  # pylint: disable=import-outside-toplevel

        features = extract_fog_features(image_path=image_path)
        if features is None:
            raise ValueError("Unable to extract features from provided image.")
        return features

    def predict_from_bytes(self, image_bytes: bytes) -> dict[str, float | int]:
        with NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
            temp_file.write(image_bytes)
            temp_file.flush()

            features = self._extract_features(Path(temp_file.name))
            bundle = self._ensure_model_loaded()
            model = bundle["model"]
            feature_columns = bundle["feature_columns"]

            sample = pd.DataFrame([features])[feature_columns]
            fog_prob = float(model.predict_proba(sample)[0, 1])
            pred = int(fog_prob >= 0.5)

            return {
                "fog_probability": fog_prob,
                "prediction": pred,
            }


fog_predictor = FogPredictor(
    model_path=settings.XGBOOST_FOG_MODEL_PATH,
    feature_script_dir=settings.XGBOOST_FOG_DIR,
)
