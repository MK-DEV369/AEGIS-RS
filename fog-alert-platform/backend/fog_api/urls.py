from django.urls import path

from .views import CacheClearView, CombinedPredictView, FogPredictView, HealthView, PotholePredictView, SourceStatusView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("sources/status/", SourceStatusView.as_view(), name="sources-status"),
    path("cache/clear/", CacheClearView.as_view(), name="cache-clear"),
    path("fog/predict/", FogPredictView.as_view(), name="fog-predict"),
    path("pothole/predict/", PotholePredictView.as_view(), name="pothole-predict"),
    path("combined/predict/", CombinedPredictView.as_view(), name="combined-predict"),
]
