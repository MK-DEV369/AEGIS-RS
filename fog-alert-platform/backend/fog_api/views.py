from __future__ import annotations

import logging
import time
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .runtime_state import runtime_state
from .services import fog_predictor


logger = logging.getLogger(__name__)


def _as_bool(value: object) -> bool:
	if isinstance(value, bool):
		return value
	if value is None:
		return False
	return str(value).strip().lower() in {"1", "true", "yes", "on"}


class HealthView(APIView):
	def get(self, request):
		return Response({"status": "ok"})


class SourceStatusView(APIView):
	def get(self, request):
		rows = runtime_state.list_sources()
		return Response(
			{
				"count": len(rows),
				"items": rows,
			}
		)


class CacheClearView(APIView):
	def post(self, request):
		reset_models = _as_bool(request.data.get("reset_models"))
		runtime_info = fog_predictor.clear_runtime_cache(reset_models=reset_models)
		state_info = runtime_state.clear()
		return Response(
			{
				"ok": True,
				"runtime": runtime_info,
				"state": state_info,
			}
		)


class _BasePredictView(APIView):
	parser_classes = [MultiPartParser]

	def _get_source_id(self, request) -> str:
		source_id = str(request.data.get("source_id") or "unknown_source").strip()
		return source_id or "unknown_source"

	def _chunk_key(self, request, source_id: str) -> str:
		stream_id = str(request.data.get("stream_id") or "default_stream").strip() or "default_stream"
		frame_id = str(request.data.get("frame_id") or "latest").strip() or "latest"
		return f"{source_id}:{stream_id}:{frame_id}"

	def _read_image_bytes(self, request, source_id: str):
		image = request.FILES.get("image")
		if image is not None:
			return {"ok": True, "complete": True, "payload": image.read()}

		chunk = request.FILES.get("chunk")
		if chunk is None:
			return {
				"ok": False,
				"error": (
					"Missing image payload. Send multipart/form-data with key 'image' "
					"or chunked payload with key 'chunk'."
				),
			}

		try:
			chunk_index = int(request.data.get("chunk_index"))
			total_chunks = int(request.data.get("total_chunks"))
		except Exception:
			return {
				"ok": False,
				"error": "chunk_index and total_chunks must be valid integers for chunked uploads.",
			}

		chunk_key = self._chunk_key(request, source_id)
		chunk_result = runtime_state.store_chunk(
			chunk_key=chunk_key,
			total_chunks=total_chunks,
			chunk_index=chunk_index,
			chunk_bytes=chunk.read(),
		)
		return chunk_result

	def _record_state(
		self,
		*,
		source_id: str,
		mode: str,
		request_id: str,
		started: float,
		status_text: str,
	) -> None:
		runtime_state.update_source(
			source_id=source_id,
			mode=mode,
			request_id=request_id,
			latency_ms=(time.perf_counter() - started) * 1000.0,
			status_text=status_text,
		)

	def _debug(self, message: str, *args) -> None:
		if settings.PIPELINE_DEBUG_LOGS:
			logger.debug(message, *args)


class FogPredictView(_BasePredictView):
	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = self._get_source_id(request)
		self._debug("[%s] fog request started source=%s", request_id, source_id)

		payload_result = self._read_image_bytes(request, source_id)
		if not payload_result.get("ok"):
			self._record_state(
				source_id=source_id,
				mode="fog_only",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response({"error": payload_result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

		if not payload_result.get("complete"):
			self._record_state(
				source_id=source_id,
				mode="fog_only",
				request_id=request_id,
				started=started,
				status_text="chunking",
			)
			return Response(
				{
					"ok": True,
					"request_id": request_id,
					"source_id": source_id,
					"mode": "fog_only",
					"status": "chunk_received",
					"received_chunks": payload_result.get("received_chunks"),
					"total_chunks": payload_result.get("total_chunks"),
				},
				status=status.HTTP_202_ACCEPTED,
			)

		try:
			output = fog_predictor.predict_fog_only_from_bytes(payload_result["payload"], source_id=source_id)
			output["request_id"] = request_id
			self._record_state(
				source_id=source_id,
				mode="fog_only",
				request_id=request_id,
				started=started,
				status_text="ok",
			)
			return Response(output, status=status.HTTP_200_OK)
		except FileNotFoundError as exc:
			self._record_state(
				source_id=source_id,
				mode="fog_only",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response({"error": str(exc), "request_id": request_id}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		except Exception as exc:
			self._record_state(
				source_id=source_id,
				mode="fog_only",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response(
				{"error": f"Prediction failed: {exc}", "request_id": request_id},
				status=status.HTTP_400_BAD_REQUEST,
			)


class PotholePredictView(_BasePredictView):
	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = self._get_source_id(request)
		self._debug("[%s] pothole request started source=%s", request_id, source_id)

		payload_result = self._read_image_bytes(request, source_id)
		if not payload_result.get("ok"):
			self._record_state(
				source_id=source_id,
				mode="pothole_only",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response({"error": payload_result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

		if not payload_result.get("complete"):
			self._record_state(
				source_id=source_id,
				mode="pothole_only",
				request_id=request_id,
				started=started,
				status_text="chunking",
			)
			return Response(
				{
					"ok": True,
					"request_id": request_id,
					"source_id": source_id,
					"mode": "pothole_only",
					"status": "chunk_received",
					"received_chunks": payload_result.get("received_chunks"),
					"total_chunks": payload_result.get("total_chunks"),
				},
				status=status.HTTP_202_ACCEPTED,
			)

		try:
			output = fog_predictor.predict_pothole_only_from_bytes(payload_result["payload"], source_id=source_id)
			output["request_id"] = request_id
			self._record_state(
				source_id=source_id,
				mode="pothole_only",
				request_id=request_id,
				started=started,
				status_text="ok",
			)
			return Response(output, status=status.HTTP_200_OK)
		except FileNotFoundError as exc:
			self._record_state(
				source_id=source_id,
				mode="pothole_only",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response({"error": str(exc), "request_id": request_id}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		except Exception as exc:
			self._record_state(
				source_id=source_id,
				mode="pothole_only",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response(
				{"error": f"Prediction failed: {exc}", "request_id": request_id},
				status=status.HTTP_400_BAD_REQUEST,
			)


class CombinedPredictView(_BasePredictView):
	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = self._get_source_id(request)
		self._debug("[%s] combined request started source=%s", request_id, source_id)

		payload_result = self._read_image_bytes(request, source_id)
		if not payload_result.get("ok"):
			self._record_state(
				source_id=source_id,
				mode="combined",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response({"error": payload_result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

		if not payload_result.get("complete"):
			self._record_state(
				source_id=source_id,
				mode="combined",
				request_id=request_id,
				started=started,
				status_text="chunking",
			)
			return Response(
				{
					"ok": True,
					"request_id": request_id,
					"source_id": source_id,
					"mode": "combined",
					"status": "chunk_received",
					"received_chunks": payload_result.get("received_chunks"),
					"total_chunks": payload_result.get("total_chunks"),
				},
				status=status.HTTP_202_ACCEPTED,
			)

		try:
			output = fog_predictor.predict_combined_from_bytes(payload_result["payload"], source_id=source_id)
			output["request_id"] = request_id
			self._record_state(
				source_id=source_id,
				mode="combined",
				request_id=request_id,
				started=started,
				status_text="ok",
			)
			return Response(output, status=status.HTTP_200_OK)
		except FileNotFoundError as exc:
			self._record_state(
				source_id=source_id,
				mode="combined",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response({"error": str(exc), "request_id": request_id}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		except Exception as exc:
			self._record_state(
				source_id=source_id,
				mode="combined",
				request_id=request_id,
				started=started,
				status_text="error",
			)
			return Response(
				{"error": f"Prediction failed: {exc}", "request_id": request_id},
				status=status.HTTP_400_BAD_REQUEST,
			)
