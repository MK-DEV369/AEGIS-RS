from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from PIL import Image

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - optional dependency at runtime
    torch = None
    nn = None

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - optional dependency at runtime
    YOLO = None


logger = logging.getLogger(__name__)


if nn is not None:

    class _ConvBlock(nn.Module):
        def __init__(self, in_c: int, out_c: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(in_c, out_c, 3, 1, 1),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_c, out_c, 3, 1, 1),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.net(x)


    class _FFAInspiredDehazeNet(nn.Module):
        """A compact architecture compatible with the saved FFA-inspired checkpoint keys."""

        def __init__(self, base: int = 48):
            super().__init__()
            self.head = nn.Conv2d(3, base, 3, 1, 1)
            self.b1 = _ConvBlock(base, base)
            self.b2 = _ConvBlock(base, base)
            self.b3 = _ConvBlock(base, base)
            self.chan_attn = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Conv2d(base, max(4, base // 4), 1),
                nn.ReLU(inplace=True),
                nn.Conv2d(max(4, base // 4), base, 1),
                nn.Sigmoid(),
            )
            self.tail = nn.Conv2d(base, 3, 3, 1, 1)
            self.fog_head = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Linear(base, max(8, base // 2)),
                nn.ReLU(inplace=True),
                nn.Linear(max(8, base // 2), 3),
            )

        def forward(self, x):
            h = self.head(x)
            h = self.b1(h) + h
            h = self.b2(h) + h
            h = self.b3(h) + h
            a = self.chan_attn(h)
            h = h * a
            out = torch.clamp(self.tail(h) + x, 0.0, 1.0)
            fog_logits = self.fog_head(h)
            return out, fog_logits

else:

    class _FFAInspiredDehazeNet:  # pragma: no cover - only used when torch is unavailable
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyTorch is not installed.")


class Dehazer:
    def __init__(self, model_path: Path, image_size: int = 256):
        self.model_path = Path(model_path)
        self.image_size = image_size
        self._model = None
        self._enabled = bool(settings.DEHAZE_ENABLED)
        self._load_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _ensure_loaded(self) -> None:
        if not self._enabled:
            return
        if self._model is not None:
            return
        if torch is None or nn is None:
            self._load_error = "PyTorch is not installed."
            self._enabled = False
            return
        if not self.model_path.exists():
            self._load_error = f"Dehazing model file not found at {self.model_path}"
            self._enabled = False
            return

        checkpoint = torch.load(self.model_path, map_location="cpu")
        state_dict = checkpoint.get("model_state_dict", checkpoint)
        head_weight = state_dict.get("head.weight")
        if head_weight is None:
            self._load_error = "Dehazing checkpoint is missing head.weight"
            self._enabled = False
            return

        base = int(head_weight.shape[0])
        model = _FFAInspiredDehazeNet(base=base)
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if unexpected:
            self._load_error = f"Unexpected checkpoint keys: {unexpected}"
            self._enabled = False
            return

        if missing:
            # Keep this as informational only: classifier keys can be absent for inference use.
            self._load_error = f"Partial checkpoint load (missing keys): {missing}"

        model.eval()
        self._model = model
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("Dehazer loaded model from %s", self.model_path)

    def _fallback_clahe(self, bgr: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        merged = cv2.merge([l, a, b])
        out = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        return cv2.convertScaleAbs(out, alpha=1.1, beta=6)

    def dehaze_bgr(self, bgr: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
        if not self._enabled:
            return bgr, {"enabled": False, "method": "none", "note": self._load_error}

        self._ensure_loaded()
        if self._model is None:
            fallback = self._fallback_clahe(bgr)
            return fallback, {
                "enabled": True,
                "method": "clahe_fallback",
                "note": self._load_error,
            }

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        tensor = torch.from_numpy(resized.transpose(2, 0, 1)).float().unsqueeze(0) / 255.0

        with torch.no_grad():
            pred, _ = self._model(tensor)

        out = pred.squeeze(0).clamp(0.0, 1.0).cpu().numpy().transpose(1, 2, 0)
        out = (out * 255.0).astype(np.uint8)
        out = cv2.resize(out, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_CUBIC)
        out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        return out_bgr, {
            "enabled": True,
            "method": "ffa_rtts_model",
            "model_path": str(self.model_path),
            "input_size": self.image_size,
            "note": self._load_error,
        }


class YoloDetector:
    def __init__(self, model_path: Path, candidate_paths: list[Path] | None = None, auto_select_latest: bool = True):
        self.model_path = Path(model_path)
        self.candidate_paths = [Path(path) for path in (candidate_paths or [])]
        self.auto_select_latest = auto_select_latest
        self.selected_model_path = self.model_path
        self._model = None
        self._load_error: str | None = None

    def _resolve_model_path(self) -> Path:
        candidate_pool: list[Path] = [self.model_path, *self.candidate_paths]
        existing = [path for path in candidate_pool if path.exists()]

        if not existing:
            return self.model_path

        if not self.auto_select_latest:
            return existing[0]

        return max(existing, key=lambda path: path.stat().st_mtime)

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        if YOLO is None:
            self._load_error = "ultralytics is not installed."
            return

        resolved_model_path = self._resolve_model_path()
        self.selected_model_path = resolved_model_path
        if not resolved_model_path.exists():
            self._load_error = f"YOLOv8 model file not found at {resolved_model_path}"
            return

        self._model = YOLO(str(resolved_model_path))
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("YOLO model loaded: %s", resolved_model_path)

    def predict(self, bgr: np.ndarray) -> dict[str, object]:
        self._ensure_loaded()
        if self._model is None:
            return {
                "enabled": False,
                "model_path": str(self.selected_model_path),
                "error": self._load_error,
                "count": 0,
                "items": [],
            }

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
        results = self._model.predict(
            source=pil_image,
            conf=float(settings.YOLOV8_CONF_THRESHOLD),
            iou=float(settings.YOLOV8_IOU_THRESHOLD),
            max_det=int(settings.YOLOV8_MAX_DET),
            verbose=False,
        )

        boxes = results[0].boxes
        masks = results[0].masks
        names = results[0].names
        items: list[dict[str, object]] = []
        mask_points = masks.xy if masks is not None else None
        if boxes is not None and boxes.xyxy is not None:
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].tolist()
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                item: dict[str, object] = {
                    "class_id": cls_id,
                    "class_name": names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id),
                    "confidence": conf,
                    "bbox_xyxy": [float(v) for v in xyxy],
                }
                if mask_points is not None and i < len(mask_points):
                    polygon = mask_points[i]
                    item["mask_polygon_xy"] = [[float(p[0]), float(p[1])] for p in polygon.tolist()]
                items.append(
                    item
                )

        return {
            "enabled": True,
            "model_path": str(self.selected_model_path),
            "task": str(getattr(self._model, "task", "unknown")),
            "count": len(items),
            "items": items,
        }


class FogPredictor:
    def __init__(
        self,
        model_path: Path,
        feature_script_dir: Path,
        dehaze_model_path: Path,
        yolo_model_path: Path,
    ):
        self.model_path = Path(model_path)
        self.feature_script_dir = Path(feature_script_dir)
        self.dehazer = Dehazer(model_path=dehaze_model_path, image_size=int(settings.DEHAZE_IMAGE_SIZE))
        self.yolo = YoloDetector(
            model_path=yolo_model_path,
            candidate_paths=settings.YOLOV8_MODEL_CANDIDATES,
            auto_select_latest=settings.YOLOV8_AUTO_SELECT_LATEST,
        )
        self._model_bundle: dict | None = None

    def _ensure_model_loaded(self) -> dict:
        if self._model_bundle is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model file not found at {self.model_path}")
            self._model_bundle = joblib.load(self.model_path)
            if settings.PIPELINE_DEBUG_LOGS:
                logger.debug("XGBoost model bundle loaded from %s", self.model_path)
        return self._model_bundle

    def _extract_features(self, image_path: Path) -> dict[str, float]:
        if str(self.feature_script_dir) not in sys.path:
            sys.path.insert(0, str(self.feature_script_dir))

        from prepare_features import extract_fog_features  # pylint: disable=import-outside-toplevel

        features = extract_fog_features(image_path=image_path)
        if features is None:
            raise ValueError("Unable to extract features from provided image.")
        return features

    def _decode_image(self, image_bytes: bytes) -> np.ndarray:
        image_arr = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid or unsupported image bytes.")
        return image

    def _predict_fog_from_bgr(self, dehazed_bgr: np.ndarray) -> dict[str, object]:
        with NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
            ok, encoded = cv2.imencode(".png", dehazed_bgr)
            if not ok:
                raise ValueError("Failed to encode dehazed image for feature extraction.")
            temp_file.write(encoded.tobytes())
            temp_file.flush()

            features = self._extract_features(Path(temp_file.name))

        bundle = self._ensure_model_loaded()
        model = bundle["model"]
        feature_columns = bundle["feature_columns"]
        sample = pd.DataFrame([features])[feature_columns]
        fog_prob = float(model.predict_proba(sample)[0, 1])
        pred = int(fog_prob >= 0.5)

        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("Fog inference complete: prob=%.4f pred=%s", fog_prob, pred)

        return {
            "fog_probability": fog_prob,
            "prediction": pred,
            "fog_label": "fog" if pred == 1 else "clear",
        }

    def predict_fog_only_from_bytes(self, image_bytes: bytes, source_id: str | None = None) -> dict[str, object]:
        started = time.perf_counter()
        bgr = self._decode_image(image_bytes)
        dehazed_bgr, dehaze_meta = self.dehazer.dehaze_bgr(bgr)

        response = {
            **self._predict_fog_from_bgr(dehazed_bgr),
            "dehazing": dehaze_meta,
            "mode": "fog_only",
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }
        if source_id:
            response["source_id"] = source_id
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("Fog-only pipeline done source_id=%s latency_ms=%.2f", source_id, response["latency_ms"])
        return response

    def predict_pothole_only_from_bytes(self, image_bytes: bytes, source_id: str | None = None) -> dict[str, object]:
        started = time.perf_counter()
        bgr = self._decode_image(image_bytes)
        dehazed_bgr, dehaze_meta = self.dehazer.dehaze_bgr(bgr)
        yolo_output = self.yolo.predict(dehazed_bgr)

        response = {
            "detections": yolo_output,
            "dehazing": dehaze_meta,
            "mode": "pothole_only",
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }
        if source_id:
            response["source_id"] = source_id
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug(
                "Pothole-only pipeline done source_id=%s det_count=%s latency_ms=%.2f",
                source_id,
                yolo_output.get("count"),
                response["latency_ms"],
            )
        return response

    def predict_combined_from_bytes(self, image_bytes: bytes, source_id: str | None = None) -> dict[str, object]:
        started = time.perf_counter()
        bgr = self._decode_image(image_bytes)
        dehazed_bgr, dehaze_meta = self.dehazer.dehaze_bgr(bgr)
        yolo_output = self.yolo.predict(dehazed_bgr)

        response = {
            **self._predict_fog_from_bgr(dehazed_bgr),
            "dehazing": dehaze_meta,
            "detections": yolo_output,
            "mode": "combined",
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }
        if source_id:
            response["source_id"] = source_id
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug(
                "Combined pipeline done source_id=%s fog_pred=%s det_count=%s latency_ms=%.2f",
                source_id,
                response.get("prediction"),
                yolo_output.get("count"),
                response["latency_ms"],
            )
        return response

    def clear_runtime_cache(self, reset_models: bool = False) -> dict[str, object]:
        self._model_bundle = None
        if reset_models:
            self.dehazer._model = None
            self.yolo._model = None
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("FogPredictor cache clear called reset_models=%s", reset_models)
        return {
            "cleared": True,
            "reset_models": reset_models,
        }

    def predict_from_bytes(self, image_bytes: bytes) -> dict[str, object]:
        # Backward-compatible alias.
        return self.predict_combined_from_bytes(image_bytes=image_bytes)


fog_predictor = FogPredictor(
    model_path=settings.XGBOOST_FOG_MODEL_PATH,
    feature_script_dir=settings.XGBOOST_FOG_DIR,
    dehaze_model_path=settings.DEHAZE_MODEL_PATH,
    yolo_model_path=settings.YOLOV8_MODEL_PATH,
)
