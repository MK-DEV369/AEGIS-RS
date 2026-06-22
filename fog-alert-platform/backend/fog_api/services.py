from __future__ import annotations

import logging
import gc
import os
import sys
import time
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from PIL import Image

from .models import PotholeDetection

try:
    import torch
    import torch.nn as nn
    # Set device globally for CPU-only inference (avoids CUDA NMS compatibility issues)
    torch.set_default_device("cpu")
    DEVICE = "cpu"
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
        def __init__(self, in_c: int, out_c: int, k: int = 3, s: int = 1, p: int = 1):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(in_c, out_c, k, s, p),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_c, out_c, k, 1, p),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.net(x)


    class _FFAInspiredDehazeNet(nn.Module):
        """Architecture aligned with the annotation-aware notebook checkpoint."""

        def __init__(self, base: int = 48):
            super().__init__()
            self.head = nn.Sequential(
                nn.Conv2d(3, base, 3, 1, 1),
                nn.BatchNorm2d(base),
                nn.ReLU(inplace=True),
            )
            self.b1 = _ConvBlock(base, base)
            self.b2 = _ConvBlock(base, base * 2, 3, 2, 1)
            self.b3 = _ConvBlock(base * 2, base * 2)
            self.b4 = _ConvBlock(base * 2, base, 3, 2, 1)
            self.b5 = _ConvBlock(base, base)

            self.up1 = nn.UpsamplingNearest2d(scale_factor=2)
            self.b6 = _ConvBlock(base * 3, base * 2)
            self.up2 = nn.UpsamplingNearest2d(scale_factor=2)
            self.b7 = _ConvBlock(base * 3, base)

            self.chan_attn = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Conv2d(base, max(4, base // 4), 1),
                nn.ReLU(inplace=True),
                nn.Conv2d(max(4, base // 4), base, 1),
                nn.Sigmoid(),
            )

            self.tail = nn.Sequential(
                nn.Conv2d(base, base, 3, 1, 1),
                nn.ReLU(inplace=True),
                nn.Conv2d(base, 3, 3, 1, 1),
            )

            self.fog_head = nn.Sequential(
                nn.AdaptiveAvgPool2d(4),
                nn.Flatten(),
                nn.Linear(base * 16, 128),
                nn.ReLU(inplace=True),
                nn.Dropout(0.3),
                nn.Linear(128, 64),
                nn.ReLU(inplace=True),
                nn.Dropout(0.2),
                nn.Linear(64, 3),
            )

            self.scene_head = nn.Sequential(
                nn.AdaptiveAvgPool2d(4),
                nn.Flatten(),
                nn.Linear(base * 16, 64),
                nn.ReLU(inplace=True),
                nn.Dropout(0.2),
                nn.Linear(64, 2),
                nn.Sigmoid(),
            )

        def forward(self, x):
            h0 = self.head(x)
            h1 = self.b1(h0) + h0

            h2 = self.b2(h1)
            h3 = self.b3(h2) + h2

            h4 = self.b4(h3)
            h5 = self.b5(h4) + h4

            h6 = self.up1(h5)
            h6 = torch.cat([h6, h3], dim=1)
            h6 = self.b6(h6)

            h7 = self.up2(h6)
            h7 = torch.cat([h7, h1], dim=1)
            h7 = self.b7(h7)

            a = self.chan_attn(h7)
            h7 = h7 * a
            out = torch.clamp(self.tail(h7) + x, 0.0, 1.0)

            fog_logits = self.fog_head(h5)
            scene_priors = self.scene_head(h5)
            return out, fog_logits, scene_priors

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
        head_weight = state_dict.get("head.0.weight") or state_dict.get("head.weight")
        if head_weight is None:
            self._load_error = "Dehazing checkpoint is missing head weights"
            self._enabled = False
            return

        base = int(head_weight.shape[0])
        model = _FFAInspiredDehazeNet(base=base)
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        notes: list[str] = []
        if missing:
            notes.append(f"missing keys={missing}")
        if unexpected:
            notes.append(f"unexpected keys={unexpected}")
        self._load_error = "; ".join(notes) if notes else None

        model.eval()
        self._model = model
        logger.info("✓ Dehazer (FFA-RTTS) model loaded successfully from: %s", self.model_path)
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("Dehazer checkpoint notes: %s", self._load_error or "none")

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

        fog_probs = None
        annotation_prior = None
        with torch.no_grad():
            outputs = self._model(tensor)
            if isinstance(outputs, tuple) and len(outputs) == 3:
                pred, fog_logits, scene_priors = outputs
                fog_probs = torch.softmax(fog_logits[0], dim=0).detach().cpu().numpy().tolist()
                scene_vals = scene_priors[0].detach().cpu().numpy().tolist()
                annotation_prior = {
                    "object_density": float(scene_vals[0]),
                    "occupancy_ratio": float(scene_vals[1]),
                }
            elif isinstance(outputs, tuple) and len(outputs) >= 2:
                pred, fog_logits = outputs[:2]
                fog_probs = torch.softmax(fog_logits[0], dim=0).detach().cpu().numpy().tolist()
            else:
                pred = outputs

        out = pred.squeeze(0).clamp(0.0, 1.0).cpu().numpy().transpose(1, 2, 0)
        out = (out * 255.0).astype(np.uint8)
        out = cv2.resize(out, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_CUBIC)
        out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        return out_bgr, {
            "enabled": True,
            "method": "ffa_rtts_annotation_model",
            "model_path": str(self.model_path),
            "input_size": self.image_size,
            "fog_head_probs": fog_probs,
            "annotation_prior": annotation_prior,
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
            logger.error(f"[DEBUG] YOLO load failed: {self._load_error}")
            return

        resolved_model_path = self._resolve_model_path()
        self.selected_model_path = resolved_model_path
        logger.info(f"[DEBUG] YOLO resolved model path: {resolved_model_path}")
        if not resolved_model_path.exists():
            self._load_error = f"YOLOv8 model file not found at {resolved_model_path}"
            logger.error(f"[DEBUG] {self._load_error}")
            return

        try:
            self._model = YOLO(str(resolved_model_path))
            logger.info("✓ YOLO (YOLOv8) model loaded successfully from: %s", resolved_model_path)
        except Exception as e:
            self._load_error = f"Failed to load YOLO model: {str(e)}"
            logger.error(f"[DEBUG] {self._load_error}")
            return
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("YOLO model task: %s", getattr(self._model, "task", "unknown"))

    def _predict_results(self, bgr: np.ndarray, realtime: bool = False):
        logger.info(f"[DEBUG] _predict_results START: bgr_shape={bgr.shape}, realtime={realtime}")
        self._ensure_loaded()
        if self._model is None:
            logger.error(f"[DEBUG] YOLO model failed to load: {self._load_error}")
            logger.error(f"[DEBUG] Model path attempted: {self.selected_model_path}")
            logger.error(f"[DEBUG] Model path exists: {self.selected_model_path.exists() if hasattr(self.selected_model_path, 'exists') else 'unknown'}")
            return {
                "enabled": False,
                "model_path": str(self.selected_model_path),
                "error": self._load_error,
                "count": 0,
                "items": [],
            }, None

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
        imgsz = int(settings.YOLOV8_IMGSZ_REALTIME if realtime else settings.YOLOV8_IMGSZ)
        device = str(settings.YOLOV8_DEVICE).strip()
        if not device and torch is not None:
            try:
                if torch.cuda.is_available():
                    device = "cuda:0"
            except Exception:
                device = device
                # Use CPU device by default for stability (override CUDA auto-detection)
                if not device:
                    device = "cpu"
        predict_kwargs = {
            "source": pil_image,
            "conf": float(settings.YOLOV8_CONF_THRESHOLD),
            "iou": float(settings.YOLOV8_IOU_THRESHOLD),
            "max_det": int(settings.YOLOV8_MAX_DET),
            "imgsz": imgsz,
            "half": bool(settings.YOLOV8_HALF and realtime),
            "verbose": False,
        }
        if device:
            predict_kwargs["device"] = device
        logger.info(f"[DEBUG] YOLO predict with kwargs: device={device}, imgsz={imgsz}, conf={predict_kwargs['conf']}")
        results = self._model.predict(
            **predict_kwargs,
        )
        logger.info(f"[DEBUG] YOLO prediction complete: results_count={len(results)}")

        boxes = results[0].boxes
        masks = results[0].masks
        names = results[0].names
        items: list[dict[str, object]] = []
        mask_points = masks.xy if masks is not None else None
        if boxes is not None and boxes.xyxy is not None:
            logger.info(f"[DEBUG] Boxes found: count={len(boxes)}")
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
                items.append(item)
        else:
            logger.info(f"[DEBUG] No boxes found in results")

        logger.info(f"[DEBUG] _predict_results END: items_count={len(items)}")
        return {
            "enabled": True,
            "model_path": str(self.selected_model_path),
            "task": str(getattr(self._model, "task", "unknown")),
            "imgsz": imgsz,
            "realtime": realtime,
            "device": device or "cpu",
            "half": bool(settings.YOLOV8_HALF and realtime and device.startswith("cuda")),
            "count": len(items),
            "items": items,
        }, results[0]

    def predict(self, bgr: np.ndarray, realtime: bool = False) -> dict[str, object]:
        detections, _ = self._predict_results(bgr, realtime=realtime)
        return detections

    def predict_with_annotated_frame(
        self,
        bgr: np.ndarray,
        realtime: bool = False,
    ) -> tuple[dict[str, object], np.ndarray | None]:
        detections, result = self._predict_results(bgr, realtime=realtime)
        if result is None:
            return detections, None
        annotated = result.plot()
        if annotated is None:
            return detections, None
        if annotated.ndim == 3 and annotated.shape[2] == 3:
            return detections, annotated
        return detections, None


def _release_inference_memory() -> None:
    gc.collect()
    if torch is not None:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


class PotholeAnalyzer:
    """Analyzes pothole detections and calculates metrics."""
    
    def __init__(self, frame_width: int = 640, frame_height: int = 480, calibration_factor: float = 200.0):
        """
        Initialize pothole analyzer.
        
        Args:
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
            calibration_factor: Calibration factor for size estimation (depends on camera height/focal length)
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.calibration_factor = calibration_factor
        self._temporal_state: dict[str, dict] = {}  # For tracking pothole deduplication

    def _estimate_pothole_size(self, bbox_xyxy: list[float]) -> dict[str, float]:
        """
        Estimate real-world pothole size from bounding box.
        
        Formula: Size_real = sqrt(pixel_area) / calibration_factor
        
        Args:
            bbox_xyxy: [x1, y1, x2, y2] normalized or absolute coordinates
            
        Returns:
            {width_m, depth_m, area_m2}
        """
        x1, y1, x2, y2 = bbox_xyxy
        pixel_width = abs(x2 - x1)
        pixel_height = abs(y2 - y1)
        pixel_area = pixel_width * pixel_height
        
        # Real-world size estimation (simplified)
        # Assuming camera calibration factor and perspective
        real_width = max(0.1, pixel_width / self.calibration_factor)
        real_depth = max(0.05, pixel_height / (self.calibration_factor * 1.5))
        real_area = real_width * real_depth
        
        return {
            "width_m": float(real_width),
            "depth_m": float(real_depth),
            "area_m2": float(real_area),
            "pixel_width": float(pixel_width),
            "pixel_height": float(pixel_height),
        }

    def _estimate_distance(self, bbox_xyxy: list[float], size_estimate: dict[str, float]) -> float:
        """
        Estimate distance to pothole using vertical position in frame.
        
        Formula: Distance = max_depth / (y_position / frame_height)
        
        Args:
            bbox_xyxy: [x1, y1, x2, y2] coordinates
            size_estimate: Output from _estimate_pothole_size
            
        Returns:
            Distance in meters
        """
        x1, y1, x2, y2 = bbox_xyxy
        
        # Vertical position (0 = top, 1 = bottom)
        # Lower in frame = closer to camera
        y_center = (y1 + y2) / 2.0
        y_normalized = y_center / max(1.0, self.frame_height)
        
        # Inverse distance: closer objects appear lower
        # Distance = 20 * (1 - normalized_y) + 1 (range: 1-20 meters)
        distance = max(1.0, 20.0 * (1.0 - y_normalized) + 1.0)
        
        # Adjust based on size (larger potholes closer)
        size_factor = size_estimate.get("area_m2", 0.1)
        distance = max(1.0, distance * (1.0 - min(0.3, size_factor * 0.2)))
        
        return float(distance)

    def _calculate_pothole_risk(
        self,
        size_m2: float,
        depth_m: float,
        distance_m: float,
        confidence: float = 1.0
    ) -> float:
        """
        Calculate pothole risk score.
        
        Formula: Risk = w1*Size + w2*Depth + w3*(1/Distance) * Confidence
        where w1=0.4, w2=0.3, w3=0.3
        
        Args:
            size_m2: Pothole area in square meters
            depth_m: Pothole depth in meters
            distance_m: Distance to pothole in meters
            confidence: YOLO detection confidence
            
        Returns:
            Risk score (0-1)
        """
        # Normalize factors to 0-1 range
        size_factor = min(1.0, size_m2 / 2.0)  # Normalize: 2m² = max risk
        depth_factor = min(1.0, depth_m / 0.5)  # Normalize: 0.5m = max depth
        distance_factor = max(0.0, 1.0 - (distance_m / 20.0))  # Closer = higher risk
        
        # Weighted combination
        w_size = 0.4
        w_depth = 0.3
        w_distance = 0.3
        
        risk = (
            w_size * size_factor +
            w_depth * depth_factor +
            w_distance * distance_factor
        ) * confidence
        
        return float(max(0.0, min(1.0, risk)))

    def _classify_pothole_severity(self, risk: float, distance_m: float) -> dict[str, str | float]:
        """
        Classify pothole severity based on risk and distance.
        
        Args:
            risk: Risk score (0-1)
            distance_m: Distance in meters
            
        Returns:
            {severity: HIGH/MEDIUM/LOW/SAFE, alert_level: int, alert_message: str}
        """
        if risk > 0.8 or distance_m < 5.0:
            return {
                "severity": "CRITICAL",
                "alert_level": 3,
                "alert_message": f"⚠️ CRITICAL: Pothole detected {distance_m:.1f}m ahead!",
            }
        elif risk > 0.6 or distance_m < 10.0:
            return {
                "severity": "HIGH",
                "alert_level": 2,
                "alert_message": f"⚠️ HIGH RISK: Pothole {distance_m:.1f}m away",
            }
        elif risk > 0.4 or distance_m < 15.0:
            return {
                "severity": "MEDIUM",
                "alert_level": 1,
                "alert_message": f"⚠ MEDIUM: Pothole detected {distance_m:.1f}m ahead",
            }
        else:
            return {
                "severity": "LOW",
                "alert_level": 0,
                "alert_message": f"ℹ️ Low risk pothole detected ({distance_m:.1f}m away)",
            }

    def _track_and_deduplicate_detections(
        self,
        source_id: str,
        current_items: list[dict]
    ) -> list[dict]:
        """
        Track potholes across consecutive frames using relative motion & horizontal overlap
        to filter out duplicate logging.
        """
        import time
        now = time.time()
        
        if source_id not in self._temporal_state:
            self._temporal_state[source_id] = {
                "last_frame_time": now,
                "next_track_id": 1,
                "tracks": []
            }
            
        state = self._temporal_state[source_id]
        last_t = state.get("last_frame_time", now)
        state["last_frame_time"] = now
        dt = max(0.01, now - last_t)
        
        # If last frame was more than 4.0 seconds ago, reset active tracks
        if dt > 4.0:
            state["tracks"] = []
            
        # Prune tracks that haven't been seen in the last 2.0 seconds
        state["tracks"] = [t for t in state["tracks"] if now - t["last_seen"] < 2.0]
        
        updated_items = []
        matched_track_ids = set()
        
        # Sort current items by distance (closest first) to prioritize nearest matches
        indexed_items = sorted(enumerate(current_items), key=lambda x: x[1].get("distance_m", 100.0))
        
        for idx, item in indexed_items:
            bbox = item.get("bbox_xyxy", [])
            if not bbox or len(bbox) != 4:
                item_copy = dict(item)
                item_copy["is_new"] = True
                updated_items.append((idx, item_copy))
                continue
                
            x1, y1, x2, y2 = bbox
            x_center = (x1 + x2) / 2.0
            x_normalized = (x_center - self.frame_width / 2.0) / max(1.0, self.frame_width)
            d_curr = item.get("distance_m", 100.0)
            
            best_match = None
            min_dist_score = 999.0
            
            for track in state["tracks"]:
                if track["track_id"] in matched_track_ids:
                    continue
                
                # Verify horizontal stripe alignment (column/lane match)
                x_diff = abs(x_normalized - track["x_normalized"])
                if x_diff > 0.16:
                    continue
                
                # Estimate distance displacement
                d_prev = track["distance_m"]
                d_diff = d_prev - d_curr
                
                # Match conditions:
                # 1. Car moving forward: pothole is getting closer (0 <= d_diff <= 30m/s * dt)
                # 2. Car is stationary: pothole stays at roughly similar distance (abs(d_diff) < 1.2m)
                is_valid_move = (0.0 <= d_diff <= 30.0 * dt)
                is_stationary = (abs(d_diff) < 1.2)
                
                if is_valid_move or is_stationary:
                    score = x_diff * 5.0 + abs(d_diff) / 10.0
                    if score < min_dist_score:
                        min_dist_score = score
                        best_match = track
            
            if best_match is not None:
                # Update matched track details
                best_match["distance_m"] = d_curr
                best_match["x_normalized"] = x_normalized
                best_match["last_seen"] = now
                best_match["risk"] = item.get("risk", 0.0)
                best_match["severity"] = item.get("severity", "LOW")
                
                matched_track_ids.add(best_match["track_id"])
                
                item_copy = dict(item)
                item_copy["track_id"] = best_match["track_id"]
                item_copy["is_new"] = False
                updated_items.append((idx, item_copy))
            else:
                # Create a new track
                new_id = state["next_track_id"]
                state["next_track_id"] += 1
                
                new_track = {
                    "track_id": new_id,
                    "distance_m": d_curr,
                    "x_normalized": x_normalized,
                    "last_seen": now,
                    "risk": item.get("risk", 0.0),
                    "severity": item.get("severity", "LOW")
                }
                state["tracks"].append(new_track)
                matched_track_ids.add(new_id)
                
                item_copy = dict(item)
                item_copy["track_id"] = new_id
                item_copy["is_new"] = True
                updated_items.append((idx, item_copy))
                
        updated_items.sort(key=lambda x: x[0])
        return [x[1] for x in updated_items]


    def analyze_detections(
        self,
        detections: dict[str, object],
        source_id: str | None = None,
    ) -> dict[str, object]:
        """
        Analyze YOLO detections and compute pothole metrics.
        
        Args:
            detections: YOLO output dict with 'items' list
            source_id: Source ID for temporal tracking
            
        Returns:
            Enriched detections with size, distance, risk metrics
        """
        items = detections.get("items", [])
        logger.info(f"[DEBUG] analyze_detections START: items_count={len(items)}, source_id={source_id}")
        analyzed_items = []
        
        for i, item in enumerate(items):
            bbox = item.get("bbox_xyxy", [])
            if not bbox or len(bbox) != 4:
                logger.warning(f"[DEBUG] Item {i} has invalid bbox: {bbox}")
                analyzed_items.append(item)
                continue
            
            # Calculate metrics
            size_est = self._estimate_pothole_size(bbox)
            distance = self._estimate_distance(bbox, size_est)
            risk = self._calculate_pothole_risk(
                size_m2=size_est["area_m2"],
                depth_m=size_est["depth_m"],
                distance_m=distance,
                confidence=item.get("confidence", 1.0)
            )
            severity_info = self._classify_pothole_severity(risk, distance)
            logger.info(f"[DEBUG] Item {i} analyzed: size={size_est['area_m2']:.2f}m², distance={distance:.1f}m, risk={risk:.3f}, severity={severity_info.get('severity')}")
            
            # Create detection object
            detection_obj = {
                "width_m": size_est["width_m"],
                "depth_m": size_est["depth_m"],
                "area_m2": size_est["area_m2"],
                "distance_m": distance,
                "risk": risk,
                "risk_smoothed": risk,
                **severity_info,
            }
            
            enriched_item = {**item, **detection_obj}
            analyzed_items.append(enriched_item)
        
        # Apply tracking and deduplication
        if source_id and analyzed_items:
            analyzed_items = self._track_and_deduplicate_detections(source_id, analyzed_items)
        
        result = {
            **detections,
            "items": analyzed_items,
            "max_risk": max((item.get("risk", 0.0) for item in analyzed_items), default=0.0),
            "critical_count": len([i for i in analyzed_items if i.get("severity") == "CRITICAL"]),
            "high_count": len([i for i in analyzed_items if i.get("severity") == "HIGH"]),
        }
        logger.info(f"[DEBUG] analyze_detections END: max_risk={result['max_risk']:.3f}, critical={result['critical_count']}, high={result['high_count']}")
        return result


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
        self.pothole_analyzer = PotholeAnalyzer(
            frame_width=int(settings.YOLOV8_IMGSZ),
            frame_height=int(settings.YOLOV8_IMGSZ),
            calibration_factor=200.0  # Tunable parameter
        )
        self._model_bundle: dict | None = None
        # Temporal smoothing state for each source
        self._temporal_state: dict[str, dict] = {}
        
        # Log initialization
        logger.info(
            "FogPredictor initialized with: XGBoost=%s | Dehaze=%s | YOLOv8=%s",
            self.model_path,
            dehaze_model_path,
            yolo_model_path,
        )
    def _enhance_pothole_frame(
        self,
        bgr: np.ndarray,
        detections: dict[str, object],
        coordinates: dict[str, object] | None = None,
        dehaze_meta: dict[str, object] | None = None
    ) -> np.ndarray:
        """
        Enhance frame with pothole detection boxes and metrics.
        
        Args:
            bgr: Frame image
            detections: Analyzed detection output
            coordinates: GPS coordinates
            dehaze_meta: Dehaze metrics
            
        Returns:
            Enhanced frame with annotations
        """
        overlay = bgr.copy()
        height, width = overlay.shape[:2]
        
        items = detections.get("items", [])
        max_risk = detections.get("max_risk", 0.0)
        
        # Draw header with overall metrics (enlarged to fit GPS & Dehaze)
        cv2.rectangle(overlay, (5, 5), (420, 115), (0, 0, 0), thickness=-1)
        y_offset = 25
        
        max_risk_color = (0, 0, 255) if max_risk > 0.8 else (0, 165, 255) if max_risk > 0.5 else (0, 255, 0)
        cv2.putText(overlay, f"Max Risk: {max_risk:.3f}", (15, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, max_risk_color, 2, cv2.LINE_AA)
        cv2.putText(overlay, f"Potholes: {len(items)}", (15, y_offset + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, f"Critical: {detections.get('critical_count', 0)} High: {detections.get('high_count', 0)}", (15, y_offset + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1, cv2.LINE_AA)
        
        # Draw GPS info if available
        if coordinates:
            lat = coordinates.get("lat")
            lng = coordinates.get("lng")
            if lat is not None and lng is not None:
                cv2.putText(overlay, f"GPS: {lat:.6f}, {lng:.6f}", (15, y_offset + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        
        # Draw Dehaze info if available
        if dehaze_meta:
            enabled = dehaze_meta.get("enabled", False)
            method = dehaze_meta.get("method", "none")
            if enabled:
                method_name = "FFA-Net" if "ffa" in method else "CLAHE" if "clahe" in method else "Active"
                cv2.putText(overlay, f"Dehaze: {method_name}", (15, y_offset + 78), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
            else:
                cv2.putText(overlay, "Dehaze: Skipped", (15, y_offset + 78), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1, cv2.LINE_AA)
        
        # Draw detection boxes with metrics
        for i, item in enumerate(items):
            bbox = item.get("bbox_xyxy", [])
            if not bbox or len(bbox) != 4:
                continue
            
            x1, y1, x2, y2 = bbox
            risk = item.get("risk", 0.0)
            severity = item.get("severity", "LOW")
            distance = item.get("distance_m", 0.0)
            size = item.get("area_m2", 0.0)
            
            # Color based on severity
            if severity == "CRITICAL":
                color = (0, 0, 255)  # Red
                thickness = 3
            elif severity == "HIGH":
                color = (0, 165, 255)  # Orange
                thickness = 2
            elif severity == "MEDIUM":
                color = (0, 255, 255)  # Yellow
                thickness = 2
            else:
                color = (0, 255, 0)  # Green
                thickness = 1
            
            # Draw bounding box
            cv2.rectangle(overlay, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
            
            # Draw label with info
            track_id = item.get("track_id")
            if track_id is not None:
                label_text = f"#{track_id} | {severity} R:{risk:.2f} {distance:.1f}m"
            else:
                label_text = f"{severity} R:{risk:.2f} {distance:.1f}m"
            text_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            label_y = max(30, int(y1) - 5)
            cv2.rectangle(overlay, (int(x1), label_y - text_size[1] - 4), (int(x1) + text_size[0] + 4, label_y), color, -1)
            cv2.putText(overlay, label_text, (int(x1) + 2, label_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Draw metrics inside bbox
            metrics_text = f"Size: {size:.2f}m²"
            cv2.putText(overlay, metrics_text, (int(x1) + 5, int(y2) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        return overlay

    def _enhance_fog_frame(
        self,
        bgr: np.ndarray,
        fog_result: dict[str, object]
    ) -> np.ndarray:
        """
        Enhance frame with fog annotations.
        
        Args:
            bgr: Frame image
            fog_result: Current fog prediction results
            
        Returns:
            Enhanced frame with annotations
        """
        overlay = bgr.copy()
        fog_prob = float(fog_result.get("fog_probability_smoothed", fog_result.get("fog_probability_fused", fog_result.get("fog_probability", 0.0))))
        fog_level = str(fog_result.get("fog_level", "unknown"))
        visibility = float(fog_result.get("visibility_meters", 0.0))
        risk = float(fog_result.get("risk_score", 0.0))
        ann_prior = fog_result.get("annotation_prior") or {}
        
        # Draw background
        cv2.rectangle(overlay, (12, 12), (500, 130), (0, 0, 0), thickness=-1)
        
        # Draw labels with colors based on risk
        if fog_level == "HIGH":
            color = (0, 0, 255)  # Red
        elif fog_level == "MEDIUM":
            color = (0, 165, 255)  # Orange
        else:
            color = (0, 255, 0)  # Green
        
        y_offset = 35
        cv2.putText(overlay, f"Fog Level: {fog_level}", (24, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(overlay, f"Probability: {fog_prob:.3f}", (24, y_offset + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.putText(overlay, f"Visibility: {visibility:.1f}m", (24, y_offset + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.putText(overlay, f"Risk Score: {risk:.3f}", (24, y_offset + 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.putText(overlay, f"Contrast: {fog_result.get('contrast', 0.0):.3f}", (24, y_offset + 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        if isinstance(ann_prior, dict) and ann_prior:
            cv2.putText(
                overlay,
                f"AnnPrior(density={float(ann_prior.get('object_density', 0.0)):.2f}, occ={float(ann_prior.get('occupancy_ratio', 0.0)):.2f})",
                (24, y_offset + 125),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (255, 200, 0),
                1,
            )
        return overlay

    def _enhance_combined_frame(
        self,
        bgr: np.ndarray,
        pothole_detections: dict[str, object],
        fog_result: dict[str, object],
        coordinates: dict[str, object] | None = None,
        dehaze_meta: dict[str, object] | None = None
    ) -> np.ndarray:
        """
        Enhance frame with both pothole bounding boxes and a detailed fog ADAS HUD.
        """
        overlay = bgr.copy()
        height, width = overlay.shape[:2]
        
        # 1. Draw Pothole Bounding Boxes as futuristic reticles
        items = pothole_detections.get("items", [])
        for item in items:
            bbox = item.get("bbox_xyxy", [])
            if not bbox or len(bbox) != 4:
                continue
            
            x1, y1, x2, y2 = bbox
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            risk = item.get("risk", 0.0)
            severity = item.get("severity", "LOW")
            distance = item.get("distance_m", 0.0)
            
            # Color based on severity
            if severity == "CRITICAL":
                color = (0, 0, 255)  # Red
            elif severity == "HIGH":
                color = (0, 165, 255)  # Orange
            elif severity == "MEDIUM":
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 255, 0)  # Green
            
            # Draw a subtle transparent overlay inside the box
            sub_box = overlay[y1:y2, x1:x2]
            if sub_box.size > 0:
                box_overlay = np.zeros_like(sub_box)
                cv2.rectangle(box_overlay, (0, 0), (x2 - x1, y2 - y1), color, -1)
                cv2.addWeighted(sub_box, 0.88, box_overlay, 0.12, 0, sub_box)

            # Draw thin outline
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 1)
            
            # Draw corner brackets (thicker lines)
            corner_len = max(5, min(15, int(min(x2 - x1, y2 - y1) * 0.2)))
            # Top-left corner
            cv2.line(overlay, (x1, y1), (x1 + corner_len, y1), color, 2, cv2.LINE_AA)
            cv2.line(overlay, (x1, y1), (x1, y1 + corner_len), color, 2, cv2.LINE_AA)
            # Top-right corner
            cv2.line(overlay, (x2, y1), (x2 - corner_len, y1), color, 2, cv2.LINE_AA)
            cv2.line(overlay, (x2, y1), (x2, y1 + corner_len), color, 2, cv2.LINE_AA)
            # Bottom-left corner
            cv2.line(overlay, (x1, y2), (x1 + corner_len, y2), color, 2, cv2.LINE_AA)
            cv2.line(overlay, (x1, y2), (x1, y2 - corner_len), color, 2, cv2.LINE_AA)
            # Bottom-right corner
            cv2.line(overlay, (x2, y2), (x2 - corner_len, y2), color, 2, cv2.LINE_AA)
            cv2.line(overlay, (x2, y2), (x2, y2 - corner_len), color, 2, cv2.LINE_AA)
            
            # Draw clean label tag
            track_id = item.get("track_id")
            if track_id is not None:
                label_text = f"POTHOLE #{track_id} | {severity} | {distance:.1f}m"
            else:
                label_text = f"POTHOLE | {severity} | {distance:.1f}m"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.38
            font_thickness = 1
            text_size = cv2.getTextSize(label_text, font, font_scale, font_thickness)[0]
            
            label_y = y1 - 6
            if label_y < 15:
                label_y = y2 + text_size[1] + 10
            
            tag_x1 = x1
            tag_y1 = label_y - text_size[1] - 6
            tag_x2 = x1 + text_size[0] + 10
            tag_y2 = label_y + 4
            
            tag_sub = overlay[max(0, tag_y1):min(height, tag_y2), max(0, tag_x1):min(width, tag_x2)]
            if tag_sub.size > 0:
                tag_bg = np.zeros_like(tag_sub)
                cv2.addWeighted(tag_sub, 0.35, tag_bg, 0.65, 0, tag_sub)
            cv2.rectangle(overlay, (tag_x1, tag_y1), (tag_x2, tag_y2), color, 1)
            cv2.putText(overlay, label_text, (x1 + 5, label_y - 1), font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)

        # 2. Draw Premium Semi-Transparent ADAS HUD Panel (Top-Left)
        hud_x, hud_y = 15, 15
        hud_w, hud_h = 350, 235
        
        # Ensure HUD coordinates fit inside the image bounds
        if hud_y + hud_h < height and hud_x + hud_w < width:
            sub_img = overlay[hud_y:hud_y+hud_h, hud_x:hud_x+hud_w]
            black_rect = np.zeros_like(sub_img)
            # Alpha blend: 65% opacity for HUD background
            cv2.addWeighted(sub_img, 0.35, black_rect, 0.65, 0, sub_img)
            # Draw border
            cv2.rectangle(overlay, (hud_x, hud_y), (hud_x + hud_w, hud_y + hud_h), (0, 255, 255), 1) # Cyan border
            
            # HUD Title & System Status
            cv2.putText(overlay, "AEGIS ACTIVE ADAS", (hud_x + 15, hud_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(overlay, "SYS: ACTIVE", (hud_x + hud_w - 110, hud_y + 23), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.line(overlay, (hud_x + 15, hud_y + 35), (hud_x + hud_w - 15, hud_y + 35), (0, 255, 255), 1)
            
            # Content calculations
            max_risk = pothole_detections.get("max_risk", 0.0)
            fog_prob = float(fog_result.get("fog_probability_smoothed", fog_result.get("fog_probability_fused", fog_result.get("fog_probability", 0.0))))
            fog_level = str(fog_result.get("fog_level", "unknown")).upper()
            visibility = float(fog_result.get("visibility_meters", 0.0))
            risk_score = float(fog_result.get("risk_score", 0.0))
            
            bar_x = hud_x + 180
            bar_w = 150
            bar_h = 10
 
            # Line 1: ADAS Risk Level
            cv2.putText(overlay, f"ADAS Risk: {risk_score:.2f}", (hud_x + 15, hud_y + 58), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            bar_y = hud_y + 48
            cv2.rectangle(overlay, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
            fill_w = int(bar_w * min(1.0, max(0.0, risk_score)))
            bar_color = (0, 0, 255) if risk_score > 0.75 else (0, 165, 255) if risk_score > 0.4 else (0, 255, 0)
            cv2.rectangle(overlay, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), bar_color, -1)
            cv2.rectangle(overlay, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (100, 100, 100), 1)
 
            # Line 2: Fog Info
            fog_color = (0, 0, 255) if fog_level == "HIGH" else (0, 165, 255) if fog_level == "MEDIUM" else (0, 255, 0)
            cv2.putText(overlay, f"Fog Level: {fog_level} ({fog_prob:.2f})", (hud_x + 15, hud_y + 88), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            bar_y_fog = hud_y + 78
            cv2.rectangle(overlay, (bar_x, bar_y_fog), (bar_x + bar_w, bar_y_fog + bar_h), (50, 50, 50), -1)
            fill_w_fog = int(bar_w * min(1.0, max(0.0, fog_prob)))
            cv2.rectangle(overlay, (bar_x, bar_y_fog), (bar_x + fill_w_fog, bar_y_fog + bar_h), fog_color, -1)
            cv2.rectangle(overlay, (bar_x, bar_y_fog), (bar_x + bar_w, bar_y_fog + bar_h), (100, 100, 100), 1)
 
            # Line 3: Visibility
            cv2.putText(overlay, f"Visibility: {visibility:.1f} m", (hud_x + 15, hud_y + 118), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
 
            # Line 4: Potholes
            pothole_color = (0, 0, 255) if max_risk > 0.75 else (0, 165, 255) if max_risk > 0.4 else (0, 255, 0)
            cv2.putText(overlay, f"Potholes: {len(items)} (Max Risk: {max_risk:.2f})", (hud_x + 15, hud_y + 148), cv2.FONT_HERSHEY_SIMPLEX, 0.45, pothole_color, 1, cv2.LINE_AA)
 
            # Line 5: GPS
            if coordinates:
                lat = coordinates.get("lat")
                lng = coordinates.get("lng")
                if lat is not None and lng is not None:
                    cv2.putText(overlay, f"GPS Coords: {lat:.6f}, {lng:.6f}", (hud_x + 15, hud_y + 178), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
                else:
                    cv2.putText(overlay, "GPS Coords: ACQUIRING...", (hud_x + 15, hud_y + 178), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1, cv2.LINE_AA)
            else:
                cv2.putText(overlay, "GPS Coords: NO TELEMETRY", (hud_x + 15, hud_y + 178), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1, cv2.LINE_AA)
                
            # Line 6: Dehaze Status & Priors
            if dehaze_meta:
                enabled = dehaze_meta.get("enabled", False)
                method = dehaze_meta.get("method", "none")
                if enabled:
                    method_name = "FFA-Net" if "ffa" in method else "CLAHE" if "clahe" in method else "Active"
                    prior = dehaze_meta.get("annotation_prior")
                    if prior and isinstance(prior, dict):
                        density = prior.get("object_density", 0.0)
                        occupancy = prior.get("occupancy_ratio", 0.0)
                        dehaze_text = f"Dehaze: {method_name} (Dens: {density:.2f}, Occ: {occupancy:.2f})"
                    else:
                        dehaze_text = f"Dehaze: {method_name} (Active)"
                    cv2.putText(overlay, dehaze_text, (hud_x + 15, hud_y + 208), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1, cv2.LINE_AA)
                else:
                    cv2.putText(overlay, "Dehaze: Disabled / Skipped", (hud_x + 15, hud_y + 208), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 150, 150), 1, cv2.LINE_AA)
            else:
                cv2.putText(overlay, "Dehaze: Not Available", (hud_x + 15, hud_y + 208), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 150, 150), 1, cv2.LINE_AA)
        
        return overlay

    def _ensure_model_loaded(self) -> dict[str, object]:
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

    def _prepare_realtime_frame(self, bgr: np.ndarray, realtime: bool) -> tuple[np.ndarray, dict[str, object]]:
        if not realtime:
            return bgr, {"realtime": False, "resized": False}

        max_side = int(settings.REALTIME_MAX_FRAME_SIDE)
        if max_side < 64:
            return bgr, {"realtime": True, "resized": False, "note": "REALTIME_MAX_FRAME_SIDE too low"}

        height, width = bgr.shape[:2]
        long_side = max(height, width)
        if long_side <= max_side:
            return bgr, {"realtime": True, "resized": False, "target_max_side": max_side}

        scale = max_side / float(long_side)
        out_w = max(32, int(width * scale))
        out_h = max(32, int(height * scale))
        resized = cv2.resize(bgr, (out_w, out_h), interpolation=cv2.INTER_AREA)
        return resized, {
            "realtime": True,
            "resized": True,
            "target_max_side": max_side,
            "input_shape": [height, width],
            "output_shape": [out_h, out_w],
            "scale": scale,
        }

    def _calculate_contrast(self, bgr: np.ndarray) -> float:
        """Calculate contrast ratio from image."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        i_min = float(np.min(gray))
        i_max = float(np.max(gray))
        if (i_max + i_min) == 0:
            return 0.0
        contrast = (i_max - i_min) / (i_max + i_min)
        return max(0.0, min(1.0, contrast))

    def _calculate_visibility(self, contrast: float) -> float:
        """Estimate visibility in meters from contrast. Higher contrast = better visibility."""
        if contrast < 0.01:
            return 10.0  # Very low visibility
        visibility = max(10.0, min(100.0, 50.0 / contrast))
        return float(visibility)

    def _classify_fog_level(self, fog_probability: float) -> str:
        """Classify fog into HIGH, MEDIUM, or LOW."""
        if fog_probability >= 0.7:
            return "HIGH"
        elif fog_probability >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"

    def _apply_temporal_smoothing(
        self,
        source_id: str,
        fog_prob: float,
        alpha: float = 0.3
    ) -> float:
        """Apply exponential moving average for temporal smoothing."""
        if source_id not in self._temporal_state:
            self._temporal_state[source_id] = {"smoothed_prob": fog_prob}
            return fog_prob
        
        prev_smoothed = self._temporal_state[source_id]["smoothed_prob"]
        smoothed = alpha * fog_prob + (1 - alpha) * prev_smoothed
        self._temporal_state[source_id]["smoothed_prob"] = smoothed
        return float(smoothed)

    def _calculate_risk_score(
        self,
        fog_prob: float,
        visibility: float,
        pothole_count: int = 0,
        speed_kmph: float = 0.0
    ) -> float:
        """
        Calculate comprehensive risk score integrating multiple factors.
        Risk formula: R = w1*F + w2*(100-V)/100 + w3*P + w4*S
        where F=fog_prob, V=visibility, P=pothole_factor, S=speed_factor
        """
        # Normalize factors
        fog_factor = fog_prob
        visibility_factor = max(0.0, min(1.0, (100.0 - visibility) / 100.0))
        pothole_factor = min(1.0, pothole_count / 5.0) if pothole_count > 0 else 0.0
        speed_factor = min(1.0, speed_kmph / 100.0) if speed_kmph > 0 else 0.0
        
        # Weights
        w_fog = 0.5
        w_visibility = 0.3
        w_pothole = 0.1
        w_speed = 0.1
        
        risk = (
            w_fog * fog_factor +
            w_visibility * visibility_factor +
            w_pothole * pothole_factor +
            w_speed * speed_factor
        )
        return float(max(0.0, min(1.0, risk)))

    def _predict_fog_from_bgr(
        self,
        dehazed_bgr: np.ndarray,
        source_id: str | None = None,
        fog_head_probs: list[float] | None = None,
        annotation_prior: dict[str, float] | None = None,
    ) -> dict[str, object]:
        temp_file = NamedTemporaryFile(suffix=".png", delete=False)
        try:
            ok, encoded = cv2.imencode(".png", dehazed_bgr)
            if not ok:
                raise ValueError("Failed to encode dehazed image for feature extraction.")
            temp_file.write(encoded.tobytes())
            temp_file.flush()
            temp_file.close()

            features = self._extract_features(Path(temp_file.name))
        finally:
            try:
                temp_file.close()
            except Exception:
                pass
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

        bundle = self._ensure_model_loaded()
        model = bundle["model"]
        feature_columns = bundle["feature_columns"]
        sample = pd.DataFrame([features])[feature_columns]
        xgb_prob = float(model.predict_proba(sample)[0, 1])

        neural_fog_prob = None
        if isinstance(fog_head_probs, list) and len(fog_head_probs) >= 3:
            neural_fog_prob = float(fog_head_probs[2])

        if neural_fog_prob is not None:
            fog_prob = 0.7 * xgb_prob + 0.3 * neural_fog_prob
        else:
            fog_prob = xgb_prob
        pred = int(fog_prob >= 0.5)

        # Apply temporal smoothing if source_id provided
        smoothed_fog_prob = fog_prob
        if source_id:
            smoothed_fog_prob = self._apply_temporal_smoothing(source_id, fog_prob)

        # Calculate additional features
        contrast = self._calculate_contrast(dehazed_bgr)
        visibility = self._calculate_visibility(contrast)
        fog_level = self._classify_fog_level(smoothed_fog_prob)
        risk_score = self._calculate_risk_score(smoothed_fog_prob, visibility)

        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug(
                "Fog inference complete: xgb=%.4f neural=%.4f fused=%.4f smoothed=%.4f pred=%s level=%s visibility=%.1f risk=%.3f",
                xgb_prob,
                neural_fog_prob if neural_fog_prob is not None else -1.0,
                fog_prob,
                smoothed_fog_prob,
                pred,
                fog_level,
                visibility,
                risk_score,
            )

        return {
            "fog_probability": xgb_prob,
            "fog_probability_neural": neural_fog_prob,
            "fog_probability_fused": fog_prob,
            "fog_probability_smoothed": smoothed_fog_prob,
            "prediction": pred,
            "fog_label": "fog" if pred == 1 else "clear",
            "fog_level": fog_level,
            "contrast": contrast,
            "visibility_meters": visibility,
            "risk_score": risk_score,
            "annotation_prior": annotation_prior,
            "features": features,
        }

    def predict_fog_only_from_bytes(
        self,
        image_bytes: bytes,
        source_id: str | None = None,
        realtime: bool = False,
        include_annotated_frame: bool = False,
    ) -> dict[str, object]:
        started = time.perf_counter()
        bgr = self._decode_image(image_bytes)
        prepared_bgr, realtime_meta = self._prepare_realtime_frame(bgr, realtime=realtime)
        if realtime and settings.REALTIME_SKIP_DEHAZE:
            dehazed_bgr = prepared_bgr
            dehaze_meta = {"enabled": False, "method": "skipped_realtime"}
        else:
            dehazed_bgr, dehaze_meta = self.dehazer.dehaze_bgr(prepared_bgr)

        fog_result = self._predict_fog_from_bgr(
            dehazed_bgr,
            source_id=source_id,
            fog_head_probs=dehaze_meta.get("fog_head_probs") if isinstance(dehaze_meta, dict) else None,
            annotation_prior=dehaze_meta.get("annotation_prior") if isinstance(dehaze_meta, dict) else None,
        )
        
        response = {
            **fog_result,
            "dehazing": dehaze_meta,
            "realtime": realtime_meta,
            "mode": "fog_only",
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }

        # Encode and include dehazed frame
        ok, encoded = cv2.imencode(".jpg", dehazed_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if ok:
            response["_dehazed_frame_bytes"] = encoded.tobytes()

        if include_annotated_frame:
            overlay = self._enhance_fog_frame(dehazed_bgr, response)
            ok, encoded = cv2.imencode(".jpg", overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if ok:
                response["_annotated_frame_bytes"] = encoded.tobytes()

        if source_id:
            response["source_id"] = source_id
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("Fog-only pipeline done source_id=%s latency_ms=%.2f", source_id, response["latency_ms"])
        return response

    def predict_pothole_only_from_bytes(
        self,
        image_bytes: bytes,
        source_id: str | None = None,
        realtime: bool = False,
        coordinates: dict[str, object] | None = None,
        frame_id: str | None = None,
        stream_id: str | None = None,
    ) -> dict[str, object]:
        started = time.perf_counter()
        logger.info(f"[DEBUG] predict_pothole_only_from_bytes START: source_id={source_id}, frame_id={frame_id}, stream_id={stream_id}, realtime={realtime}")
        bgr = self._decode_image(image_bytes)
        logger.info(f"[DEBUG] Image decoded: shape={bgr.shape}, dtype={bgr.dtype}")
        prepared_bgr, realtime_meta = self._prepare_realtime_frame(bgr, realtime=realtime)
        logger.info(f"[DEBUG] Frame prepared: realtime_meta={realtime_meta}")
        if realtime and settings.REALTIME_SKIP_DEHAZE:
            dehazed_bgr = prepared_bgr
            dehaze_meta = {"enabled": False, "method": "skipped_realtime"}
        else:
            dehazed_bgr, dehaze_meta = self.dehazer.dehaze_bgr(prepared_bgr)
        logger.info(f"[DEBUG] Dehazing complete: method={dehaze_meta.get('method')}, enabled={dehaze_meta.get('enabled')}")
        
        yolo_output, annotated_bgr = self.yolo.predict_with_annotated_frame(dehazed_bgr, realtime=realtime)
        logger.info(f"[DEBUG] YOLO detection complete: count={yolo_output.get('count')}, annotated_bgr_available={annotated_bgr is not None}")

        # Analyze pothole detections
        analyzed_output = self.pothole_analyzer.analyze_detections(yolo_output, source_id=source_id)
        logger.info(f"[DEBUG] Analysis complete: analyzed_items={len(analyzed_output.get('items', []))}, max_risk={analyzed_output.get('max_risk', 0.0)}")

        # Hardcode coordinates if pothole is detected
        pothole_count = int(analyzed_output.get("count", 0))
        if pothole_count > 0:
            coordinates = {
                "lat": 12.9242853,
                "lng": 77.4996733,
                "accuracy_m": 15.0,
                "location_source": "hardcoded"
            }

        # Validation: Check YOLO detection status
        yolo_enabled = yolo_output.get('enabled', False)
        yolo_error = yolo_output.get('error')
        if not yolo_enabled:
            logger.error(f"[DEBUG] YOLO detection not enabled: error={yolo_error}")
        logger.info(f"[DEBUG] YOLO status: enabled={yolo_enabled}, count={yolo_output.get('count', 0)}, annotated_bgr_available={annotated_bgr is not None}")

        # Validation: Check that we have a frame to annotate
        frame_to_annotate = dehazed_bgr if annotated_bgr is None else annotated_bgr
        if frame_to_annotate is None:
            logger.error("[DEBUG] CRITICAL: frame_to_annotate is None! Cannot create annotated frame")
        elif not isinstance(frame_to_annotate, np.ndarray):
            logger.error(f"[DEBUG] CRITICAL: frame_to_annotate is not ndarray: {type(frame_to_annotate)}")
        else:
            logger.info(f"[DEBUG] Frame to annotate: shape={frame_to_annotate.shape}, dtype={frame_to_annotate.dtype}, contains_valid_data={np.any(frame_to_annotate)}")

        # Enhance annotated frame with pothole metrics
        enhanced_annotated_bgr = self._enhance_pothole_frame(
            frame_to_annotate,
            analyzed_output,
            coordinates,
            dehaze_meta=dehaze_meta
        )
        logger.info(f"[DEBUG] Frame enhanced: enhanced_annotated_bgr_available={enhanced_annotated_bgr is not None}")

        if enhanced_annotated_bgr is not None:
            logger.info(f"[DEBUG] Enhanced frame shape={enhanced_annotated_bgr.shape}, dtype={enhanced_annotated_bgr.dtype}")
        else:
            logger.error("[DEBUG] CRITICAL: enhanced_annotated_bgr is None after _enhance_pothole_frame!")

        annotated_bytes = None
        if enhanced_annotated_bgr is not None:
            try:
                ok, encoded = cv2.imencode(".jpg", enhanced_annotated_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                logger.info(f"[DEBUG] cv2.imencode returned ok={ok}")
                if ok:
                    annotated_bytes = encoded.tobytes()
                    logger.info(f"[DEBUG] Annotated frame encoded: size_bytes={len(annotated_bytes)}")
                else:
                    logger.error("[DEBUG] cv2.imencode returned False - encoding failed")
            except Exception as encode_exc:
                logger.exception(f"[DEBUG] Exception during cv2.imencode: {encode_exc}")

        pothole_request_id = str(uuid.uuid4())
        pothole_count = int(analyzed_output.get("count", 0))
        new_potholes = len([i for i in analyzed_output.get("items", []) if i.get("is_new", True)])
        previous_record = PotholeDetection.latest_for_source(source_id=source_id or "unknown_source")
        previous_total = int(previous_record.total_potholes) if previous_record is not None else 0
        total_potholes = previous_total + new_potholes
        
        # Compile pothole metrics
        pothole_metrics = {
            "max_risk": float(analyzed_output.get("max_risk", 0.0)),
            "critical_count": int(analyzed_output.get("critical_count", 0)),
            "high_count": int(analyzed_output.get("high_count", 0)),
            "detections_analyzed": len(analyzed_output.get("items", [])),
        }
        logger.info(f"[DEBUG] Pothole metrics compiled: request_id={pothole_request_id}, count={pothole_count}, total={total_potholes}, metrics={pothole_metrics}")
        
        record = PotholeDetection.record_detection(
            source_id=source_id or "unknown_source",
            request_id=pothole_request_id,
            mode="pothole_only",
            pothole_count=pothole_count,
            total_potholes=total_potholes,
            detections=analyzed_output,
            coordinates=coordinates,
            pothole_metrics=pothole_metrics,
            annotated_frame=annotated_bytes,
            frame_mime="image/jpeg",
            frame_id=frame_id,
            stream_id=stream_id,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
        logger.info(f"[DEBUG] Database record created: record_id={record.id}, created_at={record.created_at}")

        response = {
            "detections": analyzed_output,
            "pothole_summary": {
                "id": record.id,
                "source_id": record.source_id,
                "request_id": record.request_id,
                "mode": record.mode,
                "pothole_count": record.pothole_count,
                "total_potholes": record.total_potholes,
                "coordinates": record.coordinates,
                "frame_id": record.frame_id,
                "stream_id": record.stream_id,
                "pothole_metrics": pothole_metrics,
                "latency_ms": record.latency_ms,
                "created_at": record.created_at.isoformat(),
            },
            "dehazing": dehaze_meta,
            "realtime": realtime_meta,
            "mode": "pothole_only",
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }
        if source_id:
            response["source_id"] = source_id
        logger.info(f"[DEBUG] Response prepared: latency={response['latency_ms']:.2f}ms, mode={response['mode']}")
        logger.info(f"[DEBUG] predict_pothole_only_from_bytes COMPLETE")
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug(
                "Pothole-only pipeline done source_id=%s det_count=%s max_risk=%.3f latency_ms=%.2f",
                source_id,
                analyzed_output.get("count"),
                analyzed_output.get("max_risk", 0.0),
                response["latency_ms"],
            )
        _release_inference_memory()
        return response

    def predict_combined_from_bytes(
        self,
        image_bytes: bytes,
        source_id: str | None = None,
        realtime: bool = False,
        coordinates: dict[str, object] | None = None,
        frame_id: str | None = None,
        stream_id: str | None = None,
    ) -> dict[str, object]:
        started = time.perf_counter()
        bgr = self._decode_image(image_bytes)
        prepared_bgr, realtime_meta = self._prepare_realtime_frame(bgr, realtime=realtime)
        if realtime and settings.REALTIME_SKIP_DEHAZE:
            dehazed_bgr = prepared_bgr
            dehaze_meta = {"enabled": False, "method": "skipped_realtime"}
        else:
            dehazed_bgr, dehaze_meta = self.dehazer.dehaze_bgr(prepared_bgr)
        yolo_output, annotated_bgr = self.yolo.predict_with_annotated_frame(dehazed_bgr, realtime=realtime)

        # Analyze pothole detections
        analyzed_output = self.pothole_analyzer.analyze_detections(yolo_output, source_id=source_id)

        # Hardcode coordinates if pothole is detected
        pothole_count = int(analyzed_output.get("count", 0))
        if pothole_count > 0:
            coordinates = {
                "lat": 12.9242853,
                "lng": 77.4996733,
                "accuracy_m": 15.0,
                "location_source": "hardcoded"
            }

        # Predict Fog first so we can draw it on the combined frame
        fog_result = self._predict_fog_from_bgr(
            dehazed_bgr,
            source_id=source_id,
            fog_head_probs=dehaze_meta.get("fog_head_probs") if isinstance(dehaze_meta, dict) else None,
            annotation_prior=dehaze_meta.get("annotation_prior") if isinstance(dehaze_meta, dict) else None,
        )

        # Enhance annotated frame with combined pothole metrics & fog HUD
        enhanced_combined = self._enhance_combined_frame(
            dehazed_bgr if annotated_bgr is None else annotated_bgr,
            analyzed_output,
            fog_result,
            coordinates,
            dehaze_meta=dehaze_meta
        )

        annotated_bytes = None
        if enhanced_combined is not None:
            ok, encoded = cv2.imencode(".jpg", enhanced_combined, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if ok:
                annotated_bytes = encoded.tobytes()

        pothole_request_id = str(uuid.uuid4())
        pothole_count = int(analyzed_output.get("count", 0))
        new_potholes = len([i for i in analyzed_output.get("items", []) if i.get("is_new", True)])
        previous_record = PotholeDetection.latest_for_source(source_id=source_id or "unknown_source")
        previous_total = int(previous_record.total_potholes) if previous_record is not None else 0
        total_potholes = previous_total + new_potholes
        
        # Compile pothole metrics
        pothole_metrics = {
            "max_risk": float(analyzed_output.get("max_risk", 0.0)),
            "critical_count": int(analyzed_output.get("critical_count", 0)),
            "high_count": int(analyzed_output.get("high_count", 0)),
            "detections_analyzed": len(analyzed_output.get("items", [])),
        }
        
        record = PotholeDetection.record_detection(
            source_id=source_id or "unknown_source",
            request_id=pothole_request_id,
            mode="combined",
            pothole_count=pothole_count,
            total_potholes=total_potholes,
            detections=analyzed_output,
            coordinates=coordinates,
            pothole_metrics=pothole_metrics,
            annotated_frame=annotated_bytes,
            frame_mime="image/jpeg",
            frame_id=frame_id,
            stream_id=stream_id,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
        
        response = {
            **fog_result,
            "dehazing": dehaze_meta,
            "detections": analyzed_output,
            "pothole_summary": {
                "id": record.id,
                "source_id": record.source_id,
                "request_id": record.request_id,
                "mode": record.mode,
                "pothole_count": record.pothole_count,
                "total_potholes": record.total_potholes,
                "pothole_metrics": pothole_metrics,
                "coordinates": record.coordinates,
                "frame_id": record.frame_id,
                "stream_id": record.stream_id,
                "latency_ms": record.latency_ms,
                "created_at": record.created_at.isoformat(),
            },
            "realtime": realtime_meta,
            "mode": "combined",
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }
        
        # Include dehazed frame
        ok, encoded = cv2.imencode(".jpg", dehazed_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if ok:
            response["_dehazed_frame_bytes"] = encoded.tobytes()
        
        if annotated_bytes is not None:
            response["_annotated_frame_bytes"] = annotated_bytes
            response["_fog_annotated_frame_bytes"] = annotated_bytes
        
        if source_id:
            response["source_id"] = source_id
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug(
                "Combined pipeline done source_id=%s fog_level=%s det_count=%s max_risk=%.3f latency_ms=%.2f",
                source_id,
                response.get("fog_level"),
                analyzed_output.get("count"),
                analyzed_output.get("max_risk", 0.0),
                response["latency_ms"],
            )
        _release_inference_memory()
        return response

    def clear_runtime_cache(self, reset_models: bool = False) -> dict[str, object]:
        self._model_bundle = None
        if reset_models:
            self.dehazer._model = None
            self.yolo._model = None
        _release_inference_memory()
        if settings.PIPELINE_DEBUG_LOGS:
            logger.debug("FogPredictor cache clear called reset_models=%s", reset_models)
        return {
            "cleared": True,
            "reset_models": reset_models,
        }

    def predict_from_bytes(self, image_bytes: bytes) -> dict[str, object]:
        # Backward-compatible alias.
        return self.predict_combined_from_bytes(image_bytes=image_bytes)


logger.info(
    "Initializing FogPredictor with models: XGBoost=%s, Dehaze=%s, YOLOv8=%s",
    settings.XGBOOST_FOG_MODEL_PATH,
    settings.DEHAZE_MODEL_PATH,
    settings.YOLOV8_MODEL_PATH,
)

fog_predictor = FogPredictor(
    model_path=settings.XGBOOST_FOG_MODEL_PATH,
    feature_script_dir=settings.XGBOOST_FOG_DIR,
    dehaze_model_path=settings.DEHAZE_MODEL_PATH,
    yolo_model_path=settings.YOLOV8_MODEL_PATH,
)
