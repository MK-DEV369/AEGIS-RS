#!/usr/bin/env python3
"""
Validation script to check if the fog-alert-platform detection pipeline is properly configured.
Run this from the backend directory: python scripts/validate_pipeline.py
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from fog_api.services import fog_predictor

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def check_yolo_model():
    print_section("YOLO Model Validation")

    yolo = fog_predictor.yolo
    print(f"Primary model path: {settings.YOLOV8_MODEL_PATH}")
    print(f"Primary model exists: {Path(settings.YOLOV8_MODEL_PATH).exists()}")

    print(f"\nCandidate models: {settings.YOLOV8_MODEL_CANDIDATES}")
    for candidate in settings.YOLOV8_MODEL_CANDIDATES:
        print(f"  - {candidate}: exists={Path(candidate).exists()}")

    yolo._ensure_loaded()
    print(f"\nSelected model path: {yolo.selected_model_path}")
    print(f"Selected model exists: {yolo.selected_model_path.exists()}")
    print(f"Model is loaded: {yolo._model is not None}")
    print(f"Load error: {yolo._load_error}")

    if yolo._model is None:
        print("⚠️  YOLO MODEL NOT LOADED - This is the primary issue!")
        print(f"   Error message: {yolo._load_error}")
        return False

    print("✓ YOLO model loaded successfully")
    print(f"  Model task: {getattr(yolo._model, 'task', 'unknown')}")
    return True

def check_dehazer_model():
    print_section("Dehazer Model Validation")

    dehazer = fog_predictor.dehazer
    print(f"Dehaze enabled: {settings.DEHAZE_ENABLED}")
    print(f"Model path: {settings.DEHAZE_MODEL_PATH}")
    print(f"Model exists: {Path(settings.DEHAZE_MODEL_PATH).exists()}")

    dehazer._ensure_loaded()
    print(f"Model is loaded: {dehazer._model is not None}")
    print(f"Load error: {dehazer.load_error}")

    if settings.DEHAZE_ENABLED and dehazer._model is None:
        print(f"⚠️  DEHAZER NOT LOADED (but enabled): {dehazer.load_error}")
        return False

    if not settings.DEHAZE_ENABLED:
        print("ℹ️  Dehazer is disabled in settings")
    else:
        print("✓ Dehazer model loaded successfully")
    return True

def check_xgboost_model():
    print_section("XGBoost Fog Model Validation")

    print(f"Model path: {settings.XGBOOST_FOG_MODEL_PATH}")
    print(f"Model exists: {Path(settings.XGBOOST_FOG_MODEL_PATH).exists()}")
    print(f"Feature script dir: {settings.XGBOOST_FOG_DIR}")

    try:
        fog_predictor._ensure_model_loaded()
        is_loaded = fog_predictor._model_bundle is not None
        print(f"Model is loaded: {is_loaded}")
        if is_loaded:
            print("✓ XGBoost model loaded successfully")
            print(f"  Features: {list(fog_predictor._model_bundle.get('feature_columns', [])[:5])}...")
            return True
        else:
            print("⚠️  XGBoost model not loaded")
            return False
    except Exception as e:
        print(f"✗ Error loading XGBoost model: {e}")
        return False

def test_pothole_detection():
    print_section("Test Pothole Detection")

    import cv2
    import numpy as np

    # Create a simple test image
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(test_frame, "Test Frame", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # Convert to bytes
    ok, encoded = cv2.imencode(".jpg", test_frame)
    if not ok:
        print("✗ Failed to encode test frame")
        return False

    test_bytes = encoded.tobytes()
    print(f"Test frame: {test_frame.shape}, encoded: {len(test_bytes)} bytes")

    try:
        result = fog_predictor.predict_pothole_only_from_bytes(
            test_bytes,
            source_id="test_validation",
            realtime=True
        )

        print(f"✓ Pothole detection ran successfully")
        print(f"  Potholes detected: {result.get('pothole_summary', {}).get('pothole_count', 0)}")
        print(f"  Latency: {result.get('latency_ms', 0):.2f}ms")
        print(f"  Has annotated frame: {'_annotated_frame_bytes' in result}")

        if '_annotated_frame_bytes' not in result:
            print("⚠️  WARNING: No annotated frame bytes in response!")
            return False

        return True
    except Exception as e:
        print(f"✗ Error during pothole detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fog_detection():
    print_section("Test Fog Detection")

    import cv2
    import numpy as np

    # Create a simple test image
    test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 200  # Gray frame (simulating fog)

    ok, encoded = cv2.imencode(".jpg", test_frame)
    if not ok:
        print("✗ Failed to encode test frame")
        return False

    test_bytes = encoded.tobytes()
    print(f"Test frame: {test_frame.shape}, encoded: {len(test_bytes)} bytes")

    try:
        result = fog_predictor.predict_fog_only_from_bytes(
            test_bytes,
            source_id="test_validation",
            realtime=True,
            include_annotated_frame=True
        )

        print(f"✓ Fog detection ran successfully")
        print(f"  Fog probability: {result.get('fog_probability', 0):.3f}")
        print(f"  Fog level: {result.get('fog_level', 'unknown')}")
        print(f"  Latency: {result.get('latency_ms', 0):.2f}ms")
        print(f"  Has annotated frame: {'_annotated_frame_bytes' in result}")

        if '_annotated_frame_bytes' not in result:
            print("⚠️  WARNING: No annotated frame bytes in response!")
            return False

        return True
    except Exception as e:
        print(f"✗ Error during fog detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("  FOG-ALERT-PLATFORM PIPELINE VALIDATION")
    print("="*60)

    results = {
        "YOLO Model": check_yolo_model(),
        "Dehazer Model": check_dehazer_model(),
        "XGBoost Model": check_xgboost_model(),
        "Pothole Detection": test_pothole_detection(),
        "Fog Detection": test_fog_detection(),
    }

    print_section("Validation Summary")
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:30} {status}")
        if not passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Pipeline is ready!")
    else:
        print("✗ SOME CHECKS FAILED - See details above")
    print("="*60 + "\n")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
