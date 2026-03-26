# Fog Alert Backend (Django)

## Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Server runs at `http://127.0.0.1:8000`.

## API Endpoints

- `GET /api/health/`
- `POST /api/fog/predict/` (multipart form-data)
  - key: `image`

Example curl:

```bash
curl -X POST http://127.0.0.1:8000/api/fog/predict/ \
  -F "image=@E:/6th SEM Data/Projects/IDP/RTTS/JPEGImages/AM_Bing_211.png"
```

## Model and extractor path

By default the backend reads:

- `RTTS/xgboost_fog/prepare_features.py`
- `RTTS/xgboost_fog/models/xgboost_fog.joblib`

You can override with environment variables from `.env.example`:

- `XGBOOST_FOG_DIR`
- `XGBOOST_FOG_MODEL_PATH`
