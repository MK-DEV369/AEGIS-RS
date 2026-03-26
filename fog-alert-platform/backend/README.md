# Fog Alert Platform - Backend

A Django REST API for real-time road fog detection and alert management using XGBoost machine learning models.

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This backend provides a REST API for the Fog Alert Platform, an intelligent road monitoring system. It integrates:

- **Django REST Framework** for building RESTful APIs
- **XGBoost** machine learning model for fog detection
- **CORS Support** for frontend communication
- **Image Processing** for feature extraction

The main functionality is fog detection from road images, returning a fog probability score (0-1) and binary prediction (fog/no fog).

## 🛠 Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11.9 | Runtime environment |
| Django | 5.2.12 | Web framework |
| Django REST Framework | 3.17.1 | REST API builder |
| XGBoost | 3.2.0 | ML model for fog detection |
| Pillow | 11.0.0 | Image processing |
| NumPy | 1.26.4 | Numerical computing |
| OpenCV | 4.10.1 | Computer vision |
| Django CORS Headers | 4.6.0 | Cross-origin requests |

## ✅ Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed ([download](https://www.python.org/))
- **pip** (comes with Python)
- **Visual Studio Code** or any text editor
- **Windows PowerShell** or terminal of your choice
- The **RTTS dataset** with trained XGBoost model in `RTTS/xgboost_fog/models/xgboost_fog.joblib`

## 📁 Project Structure

```
backend/
├── config/                  # Django project settings
│   ├── settings.py         # Main Django configuration
│   ├── urls.py             # Project URL routing
│   └── wsgi.py             # WSGI config for deployment
├── fog_api/                # Main API app
│   ├── models.py           # Database models (if needed)
│   ├── views.py            # API view endpoints
│   ├── urls.py             # API route definitions
│   ├── services.py         # Business logic (FogPredictor)
│   └── admin.py            # Admin panel config
├── manage.py               # Django management CLI
├── requirements.txt        # Python dependencies
├── .env.example            # Template for environment variables
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🚀 Setup Instructions

### Step 1: Clone/Navigate to the Project

```powershell
cd fog-alert-platform/backend
```

### Step 2: Create a Python Virtual Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\Activate.ps1
```

**Note:** If you get an execution policy error, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 3: Install Dependencies

```powershell
pip install -r requirements.txt
```

This installs all required packages including Django, Django REST Framework, XGBoost, and OpenCV.

### Step 4: Configure Environment Variables

Create a `.env` file in the `backend/` directory:

```
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=your-secret-key-here-change-in-production
FOG_MODEL_PATH=../../RTTS/xgboost_fog/models/xgboost_fog.joblib
```

Copy from `.env.example` if it exists:
```powershell
Copy-Item .env.example .env
```

### Step 5: Initialize Database

```powershell
python manage.py migrate
```

This sets up the SQLite database with required tables.

## ▶️ Running the Server

### Development Mode

```powershell
python manage.py runserver
```

The server will start at `http://localhost:8000/`

You should see:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### Check Server Health

```powershell
# In another PowerShell window
curl http://localhost:8000/api/health/
```

Expected response:
```json
{
  "status": "healthy",
  "message": "Fog detection API is running"
}
```

## 📡 API Endpoints

### 1. Health Check

**Endpoint:** `GET /api/health/`

**Purpose:** Verify the API is running and model is loaded

**Response:**
```json
{
  "status": "healthy",
  "message": "Fog detection API is running"
}
```

### 2. Fog Prediction

**Endpoint:** `POST /api/fog/predict/`

**Purpose:** Analyze an image and predict if it contains fog

**Request:** Multipart form-data

| Field | Type | Description |
|-------|------|-------------|
| `image` | File | JPEG/PNG image of road |

**Example (PowerShell):**
```powershell
$imagePath = "E:/6th SEM Data/Projects/IDP/RTTS/JPEGImages/AM_Bing_211.png"
curl -X POST http://localhost:8000/api/fog/predict/ -F "image=@$imagePath"
```

**Example (cURL):**
```bash
curl -X POST http://localhost:8000/api/fog/predict/ \
  -F "image=@image.jpg"
```

**Success Response (200):**
```json
{
  "fog_probability": 0.87,
  "prediction": 1,
  "message": "Fog detected in image"
}
```

**Error Response (400):**
```json
{
  "error": "No image provided",
  "details": "Field 'image' is required"
}
```

## 🔐 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_DEBUG` | True | Enable debug mode (set to False in production) |
| `DJANGO_SECRET_KEY` | (required) | Secret key for session signing |
| `FOG_MODEL_PATH` | `../../RTTS/xgboost_fog/models/xgboost_fog.joblib` | Path to trained XGBoost model |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Allowed hostname list |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Frontend URL for CORS |

## 🧠 How It Works

### Request Flow

```
1. User sends image → POST /api/fog/predict/
2. Django receives multipart form-data
3. Image is passed to FogPredictor service
4. FogPredictor:
   a. Loads saved XGBoost model
   b. Extracts 20 fog-related features from image
   c. Runs model inference
   d. Returns probability (0-1) and binary prediction
5. Response returned as JSON
```

### Feature Extraction

The backend extracts 20 features from each image to detect fog:

- **Dark Channel Prior** - Measures atmospheric haze
- **Contrast Metrics** - Image sharpness indicators
- **Color Space Analysis** - Saturation, luminance patterns
- **Gradient Analysis** - Edge sharpness and texture
- **Entropy & Variance** - Information content

See `RTTS/xgboost_fog/README.md` for detailed feature descriptions.

### Model Integration

- **Model Type:** XGBoost Classifier
- **Training Samples:** 8,644 (4,322 fog + 4,322 pseudo-negatives)
- **Accuracy:** 90.6%
- **F1-Score:** 0.908
- **ROC-AUC:** 0.971

The model loads automatically on first API request and is cached in memory.

## 🐛 Troubleshooting

### Issue: "No module named 'django'"

**Solution:** Ensure virtual environment is activated and dependencies installed:
```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Issue: "ModuleNotFoundError: No module named 'xgboost_fog'"

**Solution:** The feature extractor is in `RTTS/xgboost_fog/`. Verify:
1. Path in `.env` is correct: `FOG_MODEL_PATH=../../RTTS/xgboost_fog/models/xgboost_fog.joblib`
2. File exists: Check `xgboost_fog.joblib` in the models folder
3. RTTS folder path is relative to backend: Use `../../` prefix

### Issue: "CORS error when calling from frontend"

**Solution:** Check `CORS_ALLOWED_ORIGINS` in `settings.py`:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # React dev server
    "http://localhost:3000",  # Alternative port
]
```

### Issue: Model takes time to load on first request

**Solution:** This is normal. XGBoost model loads into memory on first request (2-3 seconds). Subsequent requests are instant.

### Issue: Image upload returns 400 error

**Solution:** Ensure:
- Request uses `multipart/form-data` encoding
- File field is named exactly `image`
- Image format is JPEG or PNG
- File size is reasonable (< 10MB)

## 📞 Common Tasks

### Add a New Endpoint

1. Create view in `fog_api/views.py`:
```python
from rest_framework.views import APIView
from rest_framework.response import Response

class NewFeatureView(APIView):
    def get(self, request):
        return Response({"message": "Hello"})
```

2. Add URL in `fog_api/urls.py`:
```python
from django.urls import path
from .views import NewFeatureView

urlpatterns = [
    path('new-feature/', NewFeatureView.as_view(), name='new-feature'),
]
```

### Retrain the Model

```powershell
cd ../../RTTS/xgboost_fog
python train_xgboost.py --features-csv data/fog_features.csv --model-out models/xgboost_fog.joblib
```

Then restart the backend to load the new model.

### Enable Admin Panel

```powershell
python manage.py createsuperuser
```

Visit `http://localhost:8000/admin/`

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [Fog Detection Model](../../RTTS/xgboost_fog/README.md)

## 🤝 Contributing

To modify or extend the backend:

1. Create a new branch: `git checkout -b feature/my-feature`
2. Make changes to appropriate files
3. Test with: `python manage.py test`
4. Commit and push changes

## 📝 License

This project is part of the AEGIS-RS Road Monitoring System.

---

**Questions?** Check the [Frontend README](../frontend/README.md) for the full system overview or [Model Documentation](../../RTTS/xgboost_fog/README.md) for ML details.


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
