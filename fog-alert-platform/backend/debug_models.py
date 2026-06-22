#!/usr/bin/env python
"""Debug script to test model loading"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from fog_api.services import fog_predictor
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("\n" + "="*60)
print("Model Loading Debug")
print("="*60)

print("\n[1] YOLO Detector:")
print(f"  - Detector object: {fog_predictor.yolo}")
print(f"  - Model path: {fog_predictor.yolo.model_path}")
print(f"  - Path exists: {fog_predictor.yolo.model_path.exists()}")
print(f"  - Currently loaded: {fog_predictor.yolo._model is not None}")

print("\n[2] Attempting to trigger YOLO model load...")
try:
    model = fog_predictor.yolo.model
    print(f"  ✓ YOLO model loaded successfully: {model is not None}")
    print(f"  - Model type: {type(model)}")
except Exception as e:
    print(f"  ✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n[3] Dehazer:")
print(f"  - Dehazer object: {fog_predictor.dehazer}")
print(f"  - Enabled: {fog_predictor.dehazer.enabled}")
print(f"  - Currently loaded: {fog_predictor.dehazer._model is not None}")

print("\n[4] Attempting to trigger Dehazer load...")
try:
    if fog_predictor.dehazer.enabled:
        model = fog_predictor.dehazer.model
        print(f"  ✓ Dehazer loaded successfully: {model is not None}")
    else:
        print(f"  - Dehazer disabled")
except Exception as e:
    print(f"  ✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n[5] XGBoost:")
print(f"  - Model path: {fog_predictor.xgboost_model_path}")
print(f"  - Path exists: {fog_predictor.xgboost_model_path.exists()}")
print(f"  - Currently loaded: {fog_predictor._model_bundle is not None}")

print("\n" + "="*60)
