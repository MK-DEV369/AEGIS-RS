"""
Mock data generator for development and testing.
Generates realistic synthetic pothole and fog detection data.
"""

import time
import uuid
import random
from datetime import datetime
from typing import Dict, Any

import cv2
import numpy as np
from pathlib import Path

from django.conf import settings


class MockDataGenerator:
    """Generates realistic mock detection data for testing."""

    def __init__(self):
        self.frame_count = 0
        self.last_generated = 0.0

    def _generate_mock_frame(self, width: int = 640, height: int = 480) -> bytes:
        """Generate a synthetic frame with some visual variety."""
        # Create base frame
        frame = np.random.randint(100, 200, (height, width, 3), dtype=np.uint8)

        # Add some patterns to make it look less fake
        for _ in range(3):
            x1, y1 = random.randint(0, width - 100), random.randint(0, height - 100)
            x2, y2 = x1 + random.randint(50, 150), y1 + random.randint(50, 150)
            color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)

        # Add some noise
        noise = np.random.normal(0, 10, frame.shape)
        frame = np.clip(frame.astype(float) + noise, 0, 255).astype(np.uint8)

        # Encode to JPEG
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return encoded.tobytes() if ok else b""

    def generate_mock_pothole_detection(self, source_id: str = "mock_pothole_01") -> Dict[str, Any]:
        """Generate mock pothole detection data."""
        # Randomly decide if we detect potholes
        has_potholes = random.random() < settings.MOCK_POTHOLE_PROBABILITY

        num_potholes = random.randint(0, 5) if has_potholes else 0

        # Generate detection items
        items = []
        for i in range(num_potholes):
            x1 = random.randint(50, 500)
            y1 = random.randint(50, 400)
            width = random.randint(40, 150)
            height = random.randint(40, 150)
            x2 = x1 + width
            y2 = y1 + height

            confidence = random.uniform(0.7, 0.99)
            size_m2 = random.uniform(0.05, 0.8)
            distance_m = random.uniform(5.0, 30.0)
            depth_m = random.uniform(0.05, 0.4)

            risk = random.uniform(0.3, 0.95)
            severity_map = {
                "CRITICAL": risk > 0.8,
                "HIGH": 0.6 < risk <= 0.8,
                "MEDIUM": 0.4 < risk <= 0.6,
                "LOW": risk <= 0.4,
            }
            severity = next(k for k, v in severity_map.items() if v)

            items.append({
                "class_id": 0,
                "class_name": "pothole",
                "confidence": float(confidence),
                "bbox_xyxy": [float(x1), float(y1), float(x2), float(y2)],
                "width_m": random.uniform(0.1, 1.0),
                "depth_m": float(depth_m),
                "area_m2": float(size_m2),
                "distance_m": float(distance_m),
                "risk": float(risk),
                "risk_smoothed": float(risk * 0.95),
                "severity": severity,
                "alert_level": {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}[severity],
                "alert_message": f"⚠️ {severity}: Pothole {distance_m:.1f}m away",
            })

        max_risk = max((item["risk"] for item in items), default=0.0)
        critical_count = sum(1 for item in items if item["severity"] == "CRITICAL")
        high_count = sum(1 for item in items if item["severity"] == "HIGH")

        # Generate mock frame with annotations
        frame = self._generate_mock_frame()

        # Draw simple boxes on frame for visualization
        frame_img = np.random.randint(80, 180, (480, 640, 3), dtype=np.uint8)
        for item in items:
            x1, y1, x2, y2 = [int(v) for v in item["bbox_xyxy"]]
            severity = item["severity"]
            color_map = {"CRITICAL": (0, 0, 255), "HIGH": (0, 165, 255), "MEDIUM": (0, 255, 255), "LOW": (0, 255, 0)}
            color = color_map.get(severity, (255, 255, 255))
            thickness = 3 if severity == "CRITICAL" else 2
            cv2.rectangle(frame_img, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(
                frame_img,
                f"{severity} {item['risk']:.2f}",
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

        ok, encoded = cv2.imencode(".jpg", frame_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        annotated_frame = encoded.tobytes() if ok else b""

        request_id = str(uuid.uuid4())
        now = time.time()

        return {
            "request_id": request_id,
            "source_id": source_id,
            "mode": "pothole_only",
            "detections": {
                "enabled": True,
                "count": num_potholes,
                "items": items,
                "max_risk": float(max_risk),
                "critical_count": critical_count,
                "high_count": high_count,
            },
            "pothole_summary": {
                "id": random.randint(1000, 9999),
                "source_id": source_id,
                "request_id": request_id,
                "mode": "pothole_only",
                "pothole_count": num_potholes,
                "total_potholes": random.randint(10, 100),
                "coordinates": {
                    "lat": random.uniform(20.0, 28.0),
                    "lng": random.uniform(70.0, 80.0),
                    "accuracy_m": random.randint(5, 30),
                } if random.random() > 0.5 else None,
                "frame_id": f"mock_{int(now)}",
                "stream_id": "mock_stream",
                "pothole_metrics": {
                    "max_risk": float(max_risk),
                    "critical_count": critical_count,
                    "high_count": high_count,
                    "detections_analyzed": num_potholes,
                },
                "latency_ms": random.uniform(50, 300),
                "created_at": datetime.utcnow().isoformat(),
            },
            "dehazing": {"enabled": False, "method": "mock_data"},
            "realtime": {"realtime": True, "resized": False},
            "latency_ms": random.uniform(50, 300),
            "_annotated_frame_bytes": annotated_frame,
        }

    def generate_mock_fog_detection(self, source_id: str = "mock_fog_01") -> Dict[str, Any]:
        """Generate mock fog detection data."""
        has_fog = random.random() < settings.MOCK_FOG_PROBABILITY

        fog_prob = random.uniform(0.7, 0.95) if has_fog else random.uniform(0.0, 0.3)
        fog_level = "HIGH" if fog_prob > 0.7 else "MEDIUM" if fog_prob > 0.4 else "LOW"
        visibility = random.uniform(10, 50) if has_fog else random.uniform(50, 200)
        contrast = random.uniform(0.1, 0.5) if has_fog else random.uniform(0.5, 1.0)

        risk_score = fog_prob * 0.5 + (max(0, 100 - visibility) / 100) * 0.3

        # Generate annotated frame
        frame = np.ones((480, 640, 3), dtype=np.uint8) * int(200 * (1 - fog_prob) + 100 * fog_prob)

        # Add fog level overlay
        cv2.rectangle(frame, (20, 20), (400, 100), (0, 0, 0), -1)
        color = (0, 0, 255) if fog_level == "HIGH" else (0, 165, 255) if fog_level == "MEDIUM" else (0, 255, 0)
        cv2.putText(frame, f"Fog Level: {fog_level}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(frame, f"Probability: {fog_prob:.3f}", (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        annotated_frame = encoded.tobytes() if ok else b""

        request_id = str(uuid.uuid4())
        now = time.time()

        return {
            "request_id": request_id,
            "source_id": source_id,
            "mode": "fog_only",
            "fog_probability": float(fog_prob),
            "fog_probability_neural": float(random.uniform(0.6, 0.95) if has_fog else random.uniform(0.0, 0.3)),
            "fog_probability_fused": float(fog_prob),
            "fog_probability_smoothed": float(fog_prob * 0.95),
            "prediction": 1 if has_fog else 0,
            "fog_label": "fog" if has_fog else "clear",
            "fog_level": fog_level,
            "contrast": float(contrast),
            "visibility_meters": float(visibility),
            "risk_score": float(risk_score),
            "annotation_prior": {
                "object_density": random.uniform(0.2, 0.8),
                "occupancy_ratio": random.uniform(0.3, 0.9),
            } if random.random() > 0.5 else None,
            "dehazing": {"enabled": False, "method": "mock_data"},
            "realtime": {"realtime": True, "resized": False},
            "latency_ms": random.uniform(50, 300),
            "pipeline": {
                "dehaze_enabled": False,
                "annotation_aware_model": True,
                "fog_probability_source": "xgboost+neural_fusion",
                "real_time_ready": True,
            },
            "_annotated_frame_bytes": annotated_frame,
            "_dehazed_frame_bytes": annotated_frame,
        }

    def should_generate(self) -> bool:
        """Check if it's time to generate new mock data."""
        now = time.time()
        if now - self.last_generated >= settings.MOCK_DATA_INTERVAL:
            self.last_generated = now
            self.frame_count += 1
            return True
        return False


# Global mock generator instance
mock_generator = MockDataGenerator()
