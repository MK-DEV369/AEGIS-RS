from __future__ import annotations

import base64
import logging
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


logger = logging.getLogger(__name__)

class PotholeDetection(models.Model):
	source_id = models.CharField(max_length=128, db_index=True)
	stream_id = models.CharField(max_length=128, blank=True, default="")
	frame_id = models.CharField(max_length=128, blank=True, default="")
	request_id = models.CharField(max_length=36, db_index=True)
	mode = models.CharField(max_length=32, default="pothole_only")
	pothole_count = models.PositiveIntegerField(default=0)
	total_potholes = models.PositiveIntegerField(default=0)
	coordinates = models.JSONField(null=True, blank=True)  # GPS: {lat, lng, accuracy_m, location_source}
	detections = models.JSONField(default=dict)  # YOLO detections with bbox, confidence
	pothole_metrics = models.JSONField(null=True, blank=True)  # Size, depth, distance, risk, severity
	annotated_frame = models.BinaryField(null=True, blank=True)
	frame_mime = models.CharField(max_length=64, default="image/jpeg")
	latency_ms = models.FloatField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["source_id", "-created_at"]),
			models.Index(fields=["stream_id", "-created_at"]),
		]

	@classmethod
	def prune_old_records(cls) -> int:
		cutoff = timezone.now() - timedelta(seconds=int(settings.POTHOLE_RECORD_TTL_SECONDS))
		deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
		return deleted

	@classmethod
	def record_detection(
		cls,
		*,
		source_id: str,
		request_id: str,
		mode: str,
		pothole_count: int,
		total_potholes: int,
		detections: dict[str, object],
		coordinates: dict[str, object] | None = None,
		pothole_metrics: dict[str, object] | None = None,
		annotated_frame: bytes | None = None,
		frame_mime: str = "image/jpeg",
		frame_id: str | None = None,
		stream_id: str | None = None,
		latency_ms: float | None = None,
	) -> "PotholeDetection":
		if settings.PIPELINE_DEBUG_LOGS:
			logger.info(
				"record_detection called source=%s request_id=%s pothole_count=%s total_potholes=%s metrics=%s annotated_frame_len=%s",
				source_id,
				request_id,
				pothole_count,
				total_potholes,
				pothole_metrics,
				len(annotated_frame) if annotated_frame is not None else 0,
			)

		cls.prune_old_records()
		record = cls.objects.create(
			source_id=source_id,
			stream_id=stream_id or "",
			frame_id=frame_id or "",
			request_id=request_id,
			mode=mode,
			pothole_count=max(0, int(pothole_count)),
			total_potholes=max(0, int(total_potholes)),
			coordinates=coordinates,
			detections=detections,
			pothole_metrics=pothole_metrics,
			annotated_frame=annotated_frame,
			frame_mime=frame_mime,
			latency_ms=latency_ms,
		)
		if settings.PIPELINE_DEBUG_LOGS:
			logger.info(
				"record_detection saved id=%s source=%s annotated_frame_len=%s",
				record.id,
				source_id,
				len(annotated_frame) if annotated_frame is not None else 0,
			)
		return record

	@classmethod
	def latest_for_source(cls, source_id: str | None = None) -> "PotholeDetection" | None:
		queryset = cls.objects.all()
		if source_id:
			queryset = queryset.filter(source_id=source_id)
		return queryset.first()

	@property
	def annotated_frame_base64(self) -> str:
		if not self.annotated_frame:
			return ""
		return base64.b64encode(self.annotated_frame).decode("ascii")
