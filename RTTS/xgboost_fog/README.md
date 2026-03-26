# RTTS Fog Detection with XGBoost (Starter)
can you also create a good typescript based full stack project with django as the backend and react as frontend, reactbits.dev as css animations to showcase this detection and alert system. we have already implemented road hump and pothole detection and spreading the annotated data, but next goal is to detect, predict and identify fog from the front camera of the car and also different traffic signs, this is the gist, I will brief later, we have to concentrate on the frontend and fog prediction


This starter creates a **tabular fog-classification pipeline** from images:
1. Extract fog-related handcrafted features from RTTS images.
2. Train an XGBoost classifier for `fog(1)` vs `non-fog(0)`.
3. Run prediction on a single image.

## 1) Install dependencies

From this folder:

```bash
pip install -r requirements.txt
```

PowerShell note: use one-line commands (or PowerShell backtick `` ` `` for line continuation), not `\`.

## 2) Build feature CSV

RTTS images are used as positive fog samples (`label=1`).
You must provide a folder of clear/non-fog images for negative class (`label=0`).

```bash
python prepare_features.py --rtts-root .. --positives-list ../ImageSets/Main/test.txt --negatives-dir "E:/path/to/non_fog_images" --output-csv data/fog_features.csv
```

If `--negatives-dir` is omitted, only positive samples are created (useful for inspection, not training).

### No non-fog dataset yet? (Bootstrap mode)

You can still train an initial model by generating pseudo non-fog negatives from RTTS images:

```bash
python prepare_features.py --rtts-root .. --positives-list ../ImageSets/Main/test.txt --auto-pseudo-negatives --output-csv data/fog_features.csv
```

This is a temporary baseline. Replace pseudo negatives with real clear-weather images later for better reliability.

## 3) Train XGBoost

```bash
python train_xgboost.py --features-csv data/fog_features.csv --model-out models/xgboost_fog.joblib --metrics-out models/metrics.json
```

## 4) Predict on one image

```bash
python predict_image.py --model models/xgboost_fog.joblib --image "../JPEGImages/AM_Bing_211.png"
```

If your default `python` points to Anaconda, use this explicit interpreter for stable runs:

```bash
"E:/6th SEM Data/Projects/IDP/fog-alert-platform/backend/venv/Scripts/python.exe" train_xgboost.py --features-csv data/fog_features.csv --model-out models/xgboost_fog.joblib --metrics-out models/metrics.json
```

## Notes

- This is a practical baseline, not a deep model.
- Performance strongly depends on the quality/diversity of your negative (non-fog) images.
- If later you want better accuracy, we can extend this to CNN features (or YOLO/ViT embeddings) + XGBoost.
