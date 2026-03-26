from django.urls import path

from .views import FogPredictView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("fog/predict/", FogPredictView.as_view(), name="fog-predict"),
]
