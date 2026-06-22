from __future__ import annotations

import logging
import time
import uuid
import threading
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from urllib.request import urlopen, Request
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PotholeDetection
from .runtime_state import runtime_state
from .services import fog_predictor
from .mock_data import mock_generator


logger = logging.getLogger(__name__)

# Polling registry for camera pollers: source_id -> {thread, stop_event, camera_base, params}
_polling_registry: dict[str, dict] = {}
_polling_lock = threading.Lock()


@dataclass(frozen=True)
class FrontendConfig:
	default_pothole_source_id: str
	default_fog_source_id: str
	stream_fps: float
	show_endpoints: bool
	backend_base_url: str
	frontend_base_url: str
	phone_pothole_base_url: str
	phone_fog_base_url: str


def _load_frontend_config() -> FrontendConfig:
	return FrontendConfig(
		default_pothole_source_id=str(settings.FRONTEND_POTHOLE_SOURCE_ID),
		default_fog_source_id=str(settings.FRONTEND_FOG_SOURCE_ID),
		stream_fps=float(settings.FRONTEND_STREAM_FPS),
		show_endpoints=bool(settings.FRONTEND_SHOW_ENDPOINTS),
		backend_base_url=str(settings.BACKEND_BASE_URL),
		frontend_base_url=str(settings.FRONTEND_BASE_URL),
		phone_pothole_base_url=str(settings.PHONE_POTHOLE_BASE_URL),
		phone_fog_base_url=str(settings.PHONE_FOG_BASE_URL),
	)


def _as_bool(value: object) -> bool:
	if isinstance(value, bool):
		return value
	if value is None:
		return False
	return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: object) -> float | None:
	if value in {None, ""}:
		return None
	if isinstance(value, (int, float)):
		return float(value)
	try:
		return float(str(value).strip())
	except Exception:
		return None


class HealthView(APIView):
	def get(self, request):
		dehaze_model_path = str(settings.DEHAZE_MODEL_PATH)

		yolo_detector = fog_predictor.yolo
		yolo_selected_path = str(yolo_detector.selected_model_path)
		yolo_model_path_exists = yolo_detector.selected_model_path.exists() if hasattr(yolo_detector.selected_model_path, 'exists') else False
		yolo_is_loaded = yolo_detector._model is not None
		yolo_load_error = yolo_detector._load_error

		dehazer = fog_predictor.dehazer
		dehazer_is_enabled = dehazer.enabled
		dehazer_is_loaded = dehazer._model is not None
		dehazer_load_error = dehazer.load_error

		xgboost_model_path = str(settings.XGBOOST_FOG_MODEL_PATH)
		xgboost_path_exists = Path(xgboost_model_path).exists()
		xgboost_is_loaded = fog_predictor._model_bundle is not None

		return Response(
			{
				"status": "ok",
				"version": "1.0.0",
				"models": {
					"fog_dehaze_model": dehaze_model_path,
					"fog_dehaze_annotation_aware": "annotation" in dehaze_model_path.lower(),
					"fog_classifier_model": str(settings.XGBOOST_FOG_MODEL_PATH),
					"pothole_primary_model": str(settings.YOLOV8_MODEL_PATH),
					"pothole_candidates": [str(path) for path in settings.YOLOV8_MODEL_CANDIDATES],
					"dehaze_enabled": bool(settings.DEHAZE_ENABLED),
				},
				"validation": {
					"yolo": {
						"selected_path": yolo_selected_path,
						"path_exists": yolo_model_path_exists,
						"is_loaded": yolo_is_loaded,
						"load_error": yolo_load_error,
						"status": "✓ Ready" if yolo_is_loaded else f"✗ Not loaded: {yolo_load_error}",
					},
					"dehazer": {
						"enabled": dehazer_is_enabled,
						"is_loaded": dehazer_is_loaded,
						"load_error": dehazer_load_error,
						"status": "✓ Ready" if dehazer_is_loaded else f"✗ Not loaded: {dehazer_load_error}",
					},
					"xgboost": {
						"model_path": xgboost_model_path,
						"path_exists": xgboost_path_exists,
						"is_loaded": xgboost_is_loaded,
						"status": "✓ Ready" if xgboost_is_loaded else f"✗ Not loaded. Path exists: {xgboost_path_exists}",
					},
				},
			}
		)


class FrontendConfigView(APIView):
	def get(self, request):
		cfg = _load_frontend_config()
		if settings.PIPELINE_DEBUG_LOGS:
			logger.info(
				"frontend-config served pothole_base=%s fog_base=%s backend_base=%s source=%s",
				cfg.phone_pothole_base_url or "<empty>",
				cfg.phone_fog_base_url or "<empty>",
				cfg.backend_base_url,
				request.META.get("REMOTE_ADDR", "unknown"),
			)
		return Response(
			{
				"default_sources": {
					"pothole": cfg.default_pothole_source_id,
					"fog": cfg.default_fog_source_id,
				},
				"stream_fps": cfg.stream_fps,
				"show_endpoints": cfg.show_endpoints,
				"backend_base_url": cfg.backend_base_url,
				"frontend_base_url": cfg.frontend_base_url,
				"phone_base_urls": {
					"pothole": cfg.phone_pothole_base_url,
					"fog": cfg.phone_fog_base_url,
				},
			},
			status=status.HTTP_200_OK,
		)


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
			try:
				size = getattr(image, "size", None)
				logger.info("_read_image_bytes: received image payload source=%s size=%s", source_id, size)
			except Exception:
				logger.exception("_read_image_bytes: failed to log image payload for source=%s", source_id)
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
		try:
			logger.info(
				"_read_image_bytes: chunk stored key=%s source=%s complete=%s received=%s total=%s",
				chunk_key,
				source_id,
				chunk_result.get("complete"),
				chunk_result.get("received_chunks"),
				chunk_result.get("total_chunks"),
			)
		except Exception:
			logger.exception("_read_image_bytes: failed to log chunk result for key=%s", chunk_key)
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

	def _is_realtime(self, request) -> bool:
		return _as_bool(request.data.get("realtime"))

	def _get_coordinates(self, request) -> dict[str, object] | None:
		lat = _as_float(request.data.get("lat"))
		lng = _as_float(request.data.get("lng"))
		if lat is None and lng is None:
			source_id = self._get_source_id(request)
			telemetry_rows = runtime_state.list_telemetry(limit=100)
			for row in telemetry_rows:
				if row.get("source_id") == source_id and row.get("lat") is not None and row.get("lng") is not None:
					lat = _as_float(row.get("lat"))
					lng = _as_float(row.get("lng"))
					if lat is not None and lng is not None:
						coordinates = {"lat": lat, "lng": lng, "location_source": "esp32_telemetry"}
						if row.get("device_ts") is not None:
							coordinates["device_ts"] = row.get("device_ts")
						return coordinates
			if telemetry_rows:
				fallback = telemetry_rows[0]
				lat = _as_float(fallback.get("lat"))
				lng = _as_float(fallback.get("lng"))
				if lat is not None and lng is not None:
					coordinates = {"lat": lat, "lng": lng, "location_source": "esp32_telemetry"}
					if fallback.get("source_id") is not None:
						coordinates["telemetry_source_id"] = fallback.get("source_id")
					return coordinates
			return None

		coordinates: dict[str, object] = {
			"lat": lat,
			"lng": lng,
		}
		accuracy_m = _as_float(request.data.get("accuracy_m"))
		if accuracy_m is not None:
			coordinates["accuracy_m"] = accuracy_m
		if request.data.get("location_source") not in {None, ""}:
			coordinates["location_source"] = request.data.get("location_source")
		return coordinates

	def _get_frame_context(self, request) -> dict[str, str]:
		frame_id = str(request.data.get("frame_id") or "latest").strip() or "latest"
		stream_id = str(request.data.get("stream_id") or "default_stream").strip() or "default_stream"
		return {"frame_id": frame_id, "stream_id": stream_id}


class FogPredictView(_BasePredictView):
	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = self._get_source_id(request)
		coordinates = self._get_coordinates(request)
		frame_context = self._get_frame_context(request)
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
			output = fog_predictor.predict_fog_only_from_bytes(
				payload_result["payload"],
				source_id=source_id,
				realtime=self._is_realtime(request),
				include_annotated_frame=True,
			)
			annotated_frame_bytes = output.pop("_annotated_frame_bytes", None)
			dehazed_frame_bytes = output.pop("_dehazed_frame_bytes", None)
			fog_summary = runtime_state.update_fog_frame(
				source_id=source_id,
				request_id=request_id,
				fog_probability=float(output.get("fog_probability", 0.0)),
				fog_label=str(output.get("fog_label") or "unknown"),
				frame_bytes=annotated_frame_bytes if isinstance(annotated_frame_bytes, (bytes, bytearray)) else None,
				frame_mime="image/jpeg",
				frame_id=frame_context["frame_id"],
				stream_id=frame_context["stream_id"],
				coordinates=coordinates,
				latency_ms=float(output.get("latency_ms", 0.0)),
			)
			
			# Include dehazed frame in response if available
			if dehazed_frame_bytes:
				output["_dehazed_frame_bytes"] = dehazed_frame_bytes
			
			output["request_id"] = request_id
			output["location"] = coordinates
			output["fog_summary"] = fog_summary
			output["pipeline"] = {
				"dehaze_enabled": bool(output.get("dehazing", {}).get("enabled", False)),
				"annotation_aware_model": bool(output.get("annotation_prior")),
				"fog_probability_source": "xgboost+neural_fusion" if output.get("fog_probability_neural") is not None else "xgboost",
				"real_time_ready": True,
			}
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


class PotholeCameraProcessView(APIView):
	"""Fetch latest frame from a camera base URL (/shot.jpg), optionally focus, then run pothole prediction."""
	parser_classes = [MultiPartParser, JSONParser, FormParser]

	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = str(request.data.get("source_id") or request.query_params.get("source_id") or "camera_unknown").strip() or "camera_unknown"
		camera_base = str(request.data.get("camera_base") or request.query_params.get("camera_base") or "").strip()
		if not camera_base:
			return Response({"error": "camera_base is required (e.g. http://<ip>:6969)"}, status=status.HTTP_400_BAD_REQUEST)

		# Normalize base URL (no trailing slash)
		camera_base = camera_base.rstrip('/')
		focus_before = _as_bool(request.data.get("focus_before") or request.query_params.get("focus_before"))
		focus_after = _as_bool(request.data.get("focus_after") or request.query_params.get("focus_after"))

		def _call_camera(path: str):
			url = camera_base + path
			print(f"_call_camera: calling camera url={url} focus_before={focus_before} focus_after={focus_after}")
			try:
				req = Request(url, headers={"User-Agent": "AEGIS-Backend/1.0"})
				with urlopen(req, timeout=5) as resp:
					return resp.read()
			except Exception as exc:
				logger.exception("Camera call failed url=%s", url)
				return None

		# Optionally focus
		if focus_before:
			_call_camera('/focus')
			runtime_state.update_source(source_id=source_id, mode='camera_focus', request_id=request_id, latency_ms=0.0, status_text='focus_requested')
			time.sleep(0.5)

		# Fetch latest shot.jpg
		shot_bytes = None
		shot_bytes = _call_camera('/shot.jpg')

		if shot_bytes is None:
			runtime_state.update_source(source_id=source_id, mode='pothole_camera', request_id=request_id, latency_ms=0.0, status_text='no_frame')
			return Response({"error": "Unable to fetch camera frame"}, status=status.HTTP_502_BAD_GATEWAY)

		# Run predictor
		try:
			output = fog_predictor.predict_pothole_only_from_bytes(
				shot_bytes,
				source_id=source_id,
				realtime=True,
			)
		except Exception as exc:
			logger.exception("Camera processing failed for source=%s", source_id)
			return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

		# Store focus-after event if requested
		if focus_after:
			_call_camera('/nofocus')
			runtime_state.update_source(source_id=source_id, mode='camera_focus', request_id=request_id, latency_ms=0.0, status_text='focus_released')

		# Ensure runtime cache is updated (predictor should already cache annotated frame)
		# Add a small runtime_state update so UI can see latest activity
		runtime_state.update_pothole_detection(
			source_id=source_id,
			request_id=request_id,
			mode='pothole_camera',
			pothole_count=int(output.get('pothole_summary', {}).get('pothole_count', 0)),
			detections=output.get('detections', {}),
			frame_bytes=output.pop('_annotated_frame_bytes', None) if isinstance(output.get('_annotated_frame_bytes', None), (bytes, bytearray)) else None,
			frame_mime='image/jpeg',
			frame_id=str(time.time()),
			stream_id='camera_stream',
			latency_ms=float(output.get('latency_ms', 0.0)),
		)

		output['request_id'] = request_id
		output['camera_base'] = camera_base
		runtime_state.update_source(source_id=source_id, mode='pothole_camera', request_id=request_id, latency_ms=(time.perf_counter() - started) * 1000.0, status_text='ok')
		return Response(output, status=status.HTTP_200_OK)


def _fetch_camera_bytes(camera_base: str, path_candidates=('/shot.jpg', '/latest.jpg', '/image.jpg'), timeout=5, user_agent='AEGIS-Backend/1.0'):
    camera_base = (camera_base or '').rstrip('/')
    for path in path_candidates:
        url = camera_base + path
        try:
            req = Request(url, headers={"User-Agent": user_agent})
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception:
            logger.debug("camera fetch failed for %s", url)
            continue
    return None


def _process_pothole_camera_shot_bytes(shot_bytes: bytes, source_id: str, request_id: str, frame_id: str = None):
    try:
        output = fog_predictor.predict_pothole_only_from_bytes(
            shot_bytes,
            source_id=source_id,
            realtime=True,
        )
    except Exception:
        logger.exception("_process_pothole_camera_shot_bytes: predictor failed for source=%s", source_id)
        return None

    annotated_frame_bytes = output.pop('_annotated_frame_bytes', None)
    pothole_count = int(output.get('pothole_summary', {}).get('pothole_count', 0))
    runtime_state.update_pothole_detection(
        source_id=source_id,
        request_id=request_id,
        mode='pothole_camera_poll',
        pothole_count=pothole_count,
        detections=output.get('detections', {}),
        frame_bytes=annotated_frame_bytes if isinstance(annotated_frame_bytes, (bytes, bytearray)) else None,
        frame_mime='image/jpeg',
        frame_id=frame_id or str(time.time()),
        stream_id='camera_poll',
        latency_ms=float(output.get('latency_ms', 0.0)),
    )
    return output

def _process_fog_camera_shot_bytes(shot_bytes: bytes, source_id: str, request_id: str, frame_id: str = None):
    try:
        output = fog_predictor.predict_fog_only_from_bytes(
            shot_bytes,
            source_id=source_id,
            realtime=True,
            include_annotated_frame=True,
        )
    except Exception:
        logger.exception("_process_fog_camera_shot_bytes: predictor failed for source=%s", source_id)
        return None

    annotated_bytes = output.pop('_annotated_frame_bytes', None)
    
    # 🚨 Pass the expanded metrics into the runtime state
    fog_summary = runtime_state.update_fog_frame(
        source_id=source_id,
        request_id=request_id,
        fog_probability=float(output.get('fog_probability', 0.0)),
        fog_label=str(output.get('fog_label') or 'unknown'),
        fog_probability_smoothed=float(output.get('fog_probability_smoothed', 0.0)),
        fog_level=str(output.get('fog_level') or 'unknown'),
        visibility_meters=float(output.get('visibility_meters', 0.0)),
        contrast=float(output.get('contrast', 0.0)),
        risk_score=float(output.get('risk_score', 0.0)),
        frame_bytes=annotated_bytes if isinstance(annotated_bytes, (bytes, bytearray)) else None,
        frame_mime='image/jpeg',
        frame_id=frame_id or str(time.time()),
        stream_id='camera_poll',
        coordinates=None,
        latency_ms=float(output.get('latency_ms', 0.0)),
    )
    
    output['fog_summary'] = fog_summary
    return output


class PotholeCameraStartPollingView(APIView):
	"""Start polling a camera every N seconds (default 2s) and run pothole processing."""
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		camera_base = str(request.data.get('camera_base') or '').strip()
		source_id = str(request.data.get('source_id') or 'camera_unknown').strip() or 'camera_unknown'
		interval = float(request.data.get('interval') or 2.0)
		if not camera_base:
			return Response({'error': 'camera_base is required'}, status=status.HTTP_400_BAD_REQUEST)

		with _polling_lock:
			if source_id in _polling_registry:
				return Response({'ok': False, 'message': 'polling already running for source'}, status=status.HTTP_409_CONFLICT)
			stop_event = threading.Event()

			def _poll_loop():
				logger.info('Started polling loop for source=%s camera=%s interval=%s', source_id, camera_base, interval)
				while not stop_event.is_set():
					request_id = str(uuid.uuid4())
					shot = _fetch_camera_bytes(camera_base)
					if shot is None:
						runtime_state.update_source(source_id=source_id, mode='pothole_camera_poll', request_id=request_id, latency_ms=0.0, status_text='no_frame')
						logger.debug('Polling: no frame for source=%s', source_id)
					else:
						_process_pothole_camera_shot_bytes(shot, source_id=source_id, request_id=request_id)
						runtime_state.update_source(source_id=source_id, mode='pothole_camera_poll', request_id=request_id, latency_ms=0.0, status_text='ok')
						logger.debug('Polling: processed frame for source=%s', source_id)
					# Wait interval seconds or until stopped
					stop_event.wait(interval)
				logger.info('Stopping polling loop for source=%s', source_id)

			thread = threading.Thread(target=_poll_loop, daemon=True)
			_polling_registry[source_id] = {'thread': thread, 'stop_event': stop_event, 'camera_base': camera_base, 'interval': interval}
			thread.start()

		return Response({'ok': True, 'message': 'polling started', 'source_id': source_id}, status=status.HTTP_200_OK)


class PotholeCameraStopPollingView(APIView):
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		source_id = str(request.data.get('source_id') or '').strip()
		if not source_id:
			return Response({'error': 'source_id required'}, status=status.HTTP_400_BAD_REQUEST)

		with _polling_lock:
			entry = _polling_registry.get(source_id)
			if not entry:
				return Response({'ok': False, 'message': 'no polling for source'}, status=status.HTTP_404_NOT_FOUND)
			entry['stop_event'].set()
			# Optionally join thread briefly
			try:
				entry['thread'].join(timeout=1.0)
			except Exception:
				logger.debug('Failed to join polling thread for source=%s', source_id)
			del _polling_registry[source_id]
		return Response({'ok': True, 'message': 'polling stopped', 'source_id': source_id}, status=status.HTTP_200_OK)


class FogCameraStartPollingView(APIView):
	"""Start polling a camera every N seconds and run fog processing."""
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		camera_base = str(request.data.get('camera_base') or '').strip()
		source_id = str(request.data.get('source_id') or 'camera_unknown').strip() or 'camera_unknown'
		interval = float(request.data.get('interval') or 2.0)
		if not camera_base:
			return Response({'error': 'camera_base is required'}, status=status.HTTP_400_BAD_REQUEST)

		with _polling_lock:
			if source_id in _polling_registry:
				return Response({'ok': False, 'message': 'polling already running for source'}, status=status.HTTP_409_CONFLICT)
			stop_event = threading.Event()

			def _poll_loop():
				logger.info('Started FOG polling loop for source=%s camera=%s interval=%s', source_id, camera_base, interval)
				while not stop_event.is_set():
					request_id = str(uuid.uuid4())
					shot = _fetch_camera_bytes(camera_base)
					if shot is None:
						runtime_state.update_source(source_id=source_id, mode='fog_camera_poll', request_id=request_id, latency_ms=0.0, status_text='no_frame')
						logger.debug('FOG polling: no frame for source=%s', source_id)
					else:
						_process_fog_camera_shot_bytes(shot, source_id=source_id, request_id=request_id)
						runtime_state.update_source(source_id=source_id, mode='fog_camera_poll', request_id=request_id, latency_ms=0.0, status_text='ok')
						logger.debug('FOG polling: processed frame for source=%s', source_id)
					stop_event.wait(interval)
				logger.info('Stopping FOG polling loop for source=%s', source_id)

			thread = threading.Thread(target=_poll_loop, daemon=True)
			_polling_registry[source_id] = {'thread': thread, 'stop_event': stop_event, 'camera_base': camera_base, 'interval': interval}
			thread.start()

		return Response({'ok': True, 'message': 'fog polling started', 'source_id': source_id}, status=status.HTTP_200_OK)


class FogCameraStopPollingView(APIView):
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		source_id = str(request.data.get('source_id') or '').strip()
		if not source_id:
			return Response({'error': 'source_id required'}, status=status.HTTP_400_BAD_REQUEST)

		with _polling_lock:
			entry = _polling_registry.get(source_id)
			if not entry:
				return Response({'ok': False, 'message': 'no polling for source'}, status=status.HTTP_404_NOT_FOUND)
			entry['stop_event'].set()
			try:
				entry['thread'].join(timeout=1.0)
			except Exception:
				logger.debug('Failed to join FOG polling thread for source=%s', source_id)
			del _polling_registry[source_id]
		return Response({'ok': True, 'message': 'fog polling stopped', 'source_id': source_id}, status=status.HTTP_200_OK)


class FogCameraPollingStatusView(APIView):
	def get(self, request):
		with _polling_lock:
			items = [
				{
					'source_id': sid,
					'camera_base': info.get('camera_base'),
					'interval': info.get('interval'),
					'running': not info.get('stop_event').is_set(),
				}
				for sid, info in _polling_registry.items()
			]
		return Response({'count': len(items), 'items': items}, status=status.HTTP_200_OK)


class PotholeCameraPollingStatusView(APIView):
	def get(self, request):
		with _polling_lock:
			items = [
				{
					'source_id': sid,
					'camera_base': info.get('camera_base'),
					'interval': info.get('interval'),
					'running': not info.get('stop_event').is_set(),
				}
				for sid, info in _polling_registry.items()
			]
		return Response({'count': len(items), 'items': items}, status=status.HTTP_200_OK)


def _fetch_camera_gps(camera_base: str, timeout=2) -> dict[str, object] | None:
	import json
	url = camera_base.rstrip('/') + '/sensors.json?sense=gps'
	try:
		req = Request(url, headers={"User-Agent": "AEGIS-Backend/1.0"})
		with urlopen(req, timeout=timeout) as resp:
			data = json.loads(resp.read().decode('utf-8'))
			gps_data = data.get("gps", {}).get("data", [])
			if gps_data and len(gps_data[0]) >= 2 and len(gps_data[0][1]) >= 2:
				coords = gps_data[0][1]
				return {
					"lat": float(coords[0]),
					"lng": float(coords[1]),
					"accuracy_m": 10.0,
					"location_source": "ip_webcam_sensor"
				}
	except Exception:
		pass
	return None


def _process_combined_camera_shot_bytes(shot_bytes: bytes, pothole_source_id: str, fog_source_id: str, request_id: str, frame_id: str = None, coordinates: dict = None):
	try:
		output = fog_predictor.predict_combined_from_bytes(
			shot_bytes,
			source_id=pothole_source_id,
			realtime=True,
			coordinates=coordinates,
		)
	except Exception:
		logger.exception("_process_combined_camera_shot_bytes: predictor failed for pothole_source=%s", pothole_source_id)
		return None

	# Pop annotated bytes to avoid payload bloat if returned
	pothole_annotated_bytes = output.pop('_annotated_frame_bytes', None)
	fog_annotated_bytes = output.pop('_fog_annotated_frame_bytes', None)
	
	# Update pothole runtime state
	pothole_count = int(output.get('pothole_summary', {}).get('pothole_count', 0))
	runtime_state.update_pothole_detection(
		source_id=pothole_source_id,
		request_id=request_id,
		mode='combined_camera_poll',
		pothole_count=pothole_count,
		detections=output.get('detections', {}),
		coordinates=output.get('pothole_summary', {}).get('coordinates', coordinates),
		frame_bytes=pothole_annotated_bytes if isinstance(pothole_annotated_bytes, (bytes, bytearray)) else None,
		frame_mime='image/jpeg',
		frame_id=frame_id or str(time.time()),
		stream_id='combined_camera_poll',
		latency_ms=float(output.get('latency_ms', 0.0)),
	)
	
	# Update fog runtime state
	fog_summary = runtime_state.update_fog_frame(
		source_id=fog_source_id,
		request_id=request_id,
		fog_probability=float(output.get('fog_probability', 0.0)),
		fog_label=str(output.get('fog_label') or 'unknown'),
		fog_probability_smoothed=float(output.get('fog_probability_smoothed', 0.0)),
		fog_level=str(output.get('fog_level') or 'unknown'),
		visibility_meters=float(output.get('visibility_meters', 0.0)),
		contrast=float(output.get('contrast', 0.0)),
		risk_score=float(output.get('risk_score', 0.0)),
		frame_bytes=fog_annotated_bytes if isinstance(fog_annotated_bytes, (bytes, bytearray)) else None,
		frame_mime='image/jpeg',
		frame_id=frame_id or str(time.time()),
		stream_id='combined_camera_poll',
		coordinates=output.get('pothole_summary', {}).get('coordinates', coordinates),
		latency_ms=float(output.get('latency_ms', 0.0)),
	)
	
	output['fog_summary'] = fog_summary
	return output


class CombinedCameraStartPollingView(APIView):
	"""Start combined camera polling for pothole and fog models sequentially on a single thread."""
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		camera_base = str(request.data.get('camera_base') or '').strip()
		pothole_source_id = str(request.data.get('pothole_source_id') or 'phone_pothole_01').strip() or 'phone_pothole_01'
		fog_source_id = str(request.data.get('fog_source_id') or 'phone_fog_01').strip() or 'phone_fog_01'
		interval = float(request.data.get('interval') or 2.0)
		
		# Parse laptop GPS if provided
		latitude = request.data.get('latitude')
		longitude = request.data.get('longitude')
		laptop_coords = None
		if latitude is not None and longitude is not None:
			try:
				laptop_coords = {
					"lat": float(latitude),
					"lng": float(longitude),
					"accuracy_m": 15.0,
					"location_source": "laptop_browser_gps"
				}
			except (ValueError, TypeError):
				pass

		if not camera_base:
			return Response({'error': 'camera_base is required'}, status=status.HTTP_400_BAD_REQUEST)

		registry_key = f"combined_{pothole_source_id}_{fog_source_id}"
		with _polling_lock:
			if registry_key in _polling_registry:
				return Response({'ok': False, 'message': 'combined polling already running'}, status=status.HTTP_409_CONFLICT)
			
			# Check if there is ANY combined polling running to avoid duplicate threads on the same camera URL
			for k in _polling_registry.keys():
				if k.startswith("combined_"):
					return Response({'ok': False, 'message': 'Another combined polling instance is already running'}, status=status.HTTP_409_CONFLICT)

			stop_event = threading.Event()

			def _poll_loop():
				logger.info('Started combined polling loop for pothole_source=%s fog_source=%s camera=%s interval=%s', pothole_source_id, fog_source_id, camera_base, interval)
				if laptop_coords:
					logger.info('Combined Polling: using laptop browser GPS: %s', laptop_coords)
				while not stop_event.is_set():
					request_id = str(uuid.uuid4())
					shot = _fetch_camera_bytes(camera_base)
					if shot is None:
						runtime_state.update_source(source_id=pothole_source_id, mode='combined_camera_poll', request_id=request_id, latency_ms=0.0, status_text='no_frame')
						runtime_state.update_source(source_id=fog_source_id, mode='combined_camera_poll', request_id=request_id, latency_ms=0.0, status_text='no_frame')
						logger.debug('Combined Polling: no frame for camera=%s', camera_base)
					else:
						res = _process_combined_camera_shot_bytes(shot, pothole_source_id=pothole_source_id, fog_source_id=fog_source_id, request_id=request_id, coordinates=laptop_coords)
						latency = float(res.get('latency_ms', 0.0)) if res else 0.0
						runtime_state.update_source(source_id=pothole_source_id, mode='combined_camera_poll', request_id=request_id, latency_ms=latency, status_text='ok')
						runtime_state.update_source(source_id=fog_source_id, mode='combined_camera_poll', request_id=request_id, latency_ms=latency, status_text='ok')
						logger.debug('Combined Polling: processed frame for camera=%s latency=%.2fms', camera_base, latency)
					stop_event.wait(interval)
				logger.info('Stopping combined polling loop for camera=%s', camera_base)

			thread = threading.Thread(target=_poll_loop, daemon=True)
			_polling_registry[registry_key] = {
				'thread': thread,
				'stop_event': stop_event,
				'camera_base': camera_base,
				'interval': interval,
				'pothole_source_id': pothole_source_id,
				'fog_source_id': fog_source_id,
			}
			thread.start()

		return Response({'ok': True, 'message': 'combined polling started', 'registry_key': registry_key}, status=status.HTTP_200_OK)


class CombinedCameraStopPollingView(APIView):
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		pothole_source_id = str(request.data.get('pothole_source_id') or '').strip()
		fog_source_id = str(request.data.get('fog_source_id') or '').strip()
		source_id = str(request.data.get('source_id') or '').strip()

		registry_key = None
		with _polling_lock:
			if pothole_source_id and fog_source_id:
				registry_key = f"combined_{pothole_source_id}_{fog_source_id}"

			if not registry_key or registry_key not in _polling_registry:
				candidates = []
				for key, info in list(_polling_registry.items()):
					if key.startswith("combined_"):
						if not source_id or source_id in (info.get('pothole_source_id'), info.get('fog_source_id'), key):
							candidates.append(key)
				if candidates:
					registry_key = candidates[0]

			if not registry_key or registry_key not in _polling_registry:
				return Response({'ok': False, 'message': 'no combined polling running'}, status=status.HTTP_404_NOT_FOUND)

			entry = _polling_registry[registry_key]
			entry['stop_event'].set()
			try:
				entry['thread'].join(timeout=1.0)
			except Exception:
				logger.debug('Failed to join combined polling thread')
			del _polling_registry[registry_key]
		return Response({'ok': True, 'message': 'combined polling stopped', 'registry_key': registry_key}, status=status.HTTP_200_OK)


class CombinedCameraPollingStatusView(APIView):
	def get(self, request):
		pothole_source_id = str(request.query_params.get('pothole_source_id') or '').strip()
		fog_source_id = str(request.query_params.get('fog_source_id') or '').strip()
		source_id = str(request.query_params.get('source_id') or '').strip()

		with _polling_lock:
			found_key = None
			for key, info in _polling_registry.items():
				if key.startswith("combined_"):
					if source_id:
						if source_id in (info.get('pothole_source_id'), info.get('fog_source_id'), key):
							found_key = key
							break
					elif pothole_source_id and fog_source_id:
						if info.get('pothole_source_id') == pothole_source_id and info.get('fog_source_id') == fog_source_id:
							found_key = key
							break
					else:
						found_key = key
						break

			if found_key:
				entry = _polling_registry[found_key]
				item = {
					'registry_key': found_key,
					'camera_base': entry.get('camera_base'),
					'interval': entry.get('interval'),
					'running': not entry.get('stop_event').is_set(),
					'pothole_source_id': entry.get('pothole_source_id'),
					'fog_source_id': entry.get('fog_source_id'),
				}
				return Response({'running': True, 'item': item}, status=status.HTTP_200_OK)

		return Response({'running': False}, status=status.HTTP_200_OK)



class FogCameraProcessView(APIView):
	"""Fetch latest frame from a camera base URL (/shot.jpg), optionally focus, dehaze via FFA model, then run fog prediction and cache annotated preview."""
	parser_classes = [MultiPartParser, JSONParser, FormParser]

	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = str(request.data.get("source_id") or request.query_params.get("source_id") or "camera_unknown").strip() or "camera_unknown"
		camera_base = str(request.data.get("camera_base") or request.query_params.get("camera_base") or "").strip()
		if not camera_base:
			return Response({"error": "camera_base is required (e.g. http://<ip>:6969)"}, status=status.HTTP_400_BAD_REQUEST)

		camera_base = camera_base.rstrip('/')
		focus_before = _as_bool(request.data.get("focus_before") or request.query_params.get("focus_before"))
		focus_after = _as_bool(request.data.get("focus_after") or request.query_params.get("focus_after"))

		def _call_camera(path: str):
			url = camera_base + path
			try:
				req = Request(url, headers={"User-Agent": "AEGIS-Backend/1.0"})
				with urlopen(req, timeout=5) as resp:
					return resp.read()
			except Exception:
				logger.exception("Camera call failed url=%s", url)
				return None

		if focus_before:
			_call_camera('/focus')
			runtime_state.update_source(source_id=source_id, mode='camera_focus', request_id=request_id, latency_ms=0.0, status_text='focus_requested')
			time.sleep(0.5)

		shot_bytes = _call_camera('/shot.jpg')
		if shot_bytes is None:
			shot_bytes = _call_camera('/latest.jpg') or _call_camera('/image.jpg')

		if shot_bytes is None:
			runtime_state.update_source(source_id=source_id, mode='fog_camera', request_id=request_id, latency_ms=0.0, status_text='no_frame')
			return Response({"error": "Unable to fetch camera frame"}, status=status.HTTP_502_BAD_GATEWAY)

		try:
			output = fog_predictor.predict_fog_only_from_bytes(
				shot_bytes,
				source_id=source_id,
				realtime=True,
				include_annotated_frame=True,
			)
		except Exception as exc:
			logger.exception("Fog camera processing failed for source=%s", source_id)
			return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

		if focus_after:
			_call_camera('/nofocus')
			runtime_state.update_source(source_id=source_id, mode='camera_focus', request_id=request_id, latency_ms=0.0, status_text='focus_released')

		# Cache annotated dehazed preview in runtime state
		annotated_bytes = output.pop('_annotated_frame_bytes', None)
		dehazed_bytes = output.pop('_dehazed_frame_bytes', None)
		fog_summary = runtime_state.update_fog_frame(
			source_id=source_id,
			request_id=request_id,
			fog_probability=float(output.get('fog_probability', 0.0)),
			fog_label=str(output.get('fog_label') or 'unknown'),
			frame_bytes=annotated_bytes if isinstance(annotated_bytes, (bytes, bytearray)) else None,
			frame_mime='image/jpeg',
			frame_id=str(time.time()),
			stream_id='camera_stream',
			coordinates=None,
			latency_ms=float(output.get('latency_ms', 0.0)),
		)

		if dehazed_bytes:
			output['_dehazed_frame_bytes'] = dehazed_bytes

		output['request_id'] = request_id
		output['camera_base'] = camera_base
		output['fog_summary'] = fog_summary
		runtime_state.update_source(source_id=source_id, mode='fog_camera', request_id=request_id, latency_ms=(time.perf_counter() - started) * 1000.0, status_text='ok')
		return Response(output, status=status.HTTP_200_OK)


class FogRuntimeStatusView(APIView):
	def get(self, request):
		source_id = str(request.query_params.get("source_id") or "").strip()
		rows = runtime_state.list_fog_frames(limit=100)
		if source_id:
			rows = [row for row in rows if row.get("source_id") == source_id]

		# Add mock data if enabled and no real data exists
		if settings.ENABLE_MOCK_DATA and len(rows) == 0:
			if mock_generator.should_generate():
				mock_data = mock_generator.generate_mock_fog_detection(source_id or "phone_fog_01")
				rows.append({
					"source_id": mock_data.get("source_id"),
					"request_id": mock_data.get("request_id"),
					"fog_probability": mock_data.get("fog_probability"),
					"fog_label": mock_data.get("fog_label"),
					"fog_level": mock_data.get("fog_level"),
					"visibility_meters": mock_data.get("visibility_meters"),
					"risk_score": mock_data.get("risk_score"),
					"latency_ms": mock_data.get("latency_ms"),
					"updated_at": time.time(),
					"_is_mock": True,
				})

		return Response({"count": len(rows), "items": rows[:50]}, status=status.HTTP_200_OK)


class FogLatestFrameView(APIView):
	"""Get the latest annotated fog frame (with overlays)."""
	def get(self, request):
		source_id = str(request.query_params.get("source_id") or "").strip() or None
		record = runtime_state.get_latest_fog_frame(source_id=source_id)

		# Check if we should fall back to mock data
		if record is None or not record.get("frame_bytes"):
			if settings.ENABLE_MOCK_DATA:
				if mock_generator.should_generate():
					mock_data = mock_generator.generate_mock_fog_detection(source_id or "mock_fog_01")
					annotated_bytes = mock_data.get("_annotated_frame_bytes")
					if annotated_bytes:
						return HttpResponse(bytes(annotated_bytes), content_type="image/jpeg")
			return Response({"error": "No annotated fog frame available."}, status=status.HTTP_404_NOT_FOUND)

		return HttpResponse(bytes(record["frame_bytes"]), content_type=str(record.get("frame_mime") or "image/jpeg"))


class FogMJPEGStreamView(APIView):
	def get(self, request):
		source_id = str(request.query_params.get("source_id") or "").strip() or None
		fps = _as_float(request.query_params.get("fps")) or 3.0
		frame_interval = 1.0 / max(0.5, fps)

		def _placeholder_frame() -> bytes:
			import cv2
			import numpy as np

			frame = np.zeros((480, 640, 3), dtype=np.uint8)
			cv2.putText(frame, "Waiting for fog frames...", (70, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
			ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
			return encoded.tobytes() if ok else b""

		def _frame_bytes() -> bytes:
			frame = runtime_state.get_latest_fog_frame(source_id=source_id)
			if frame is None:
				return _placeholder_frame()
			return bytes(frame["frame_bytes"])

		def _stream():
			boundary = b"--frame\r\n"
			headers = b"Content-Type: image/jpeg\r\n\r\n"
			while True:
				payload = _frame_bytes()
				if payload:
					yield boundary + headers + payload + b"\r\n"
				time.sleep(frame_interval)

		response = StreamingHttpResponse(_stream(), content_type="multipart/x-mixed-replace; boundary=frame")
		response["Cache-Control"] = "no-cache, no-store, must-revalidate"
		response["Pragma"] = "no-cache"
		response["X-Accel-Buffering"] = "no"
		return response


class PotholePredictView(_BasePredictView):
	def post(self, request):
		request_id = str(uuid.uuid4())
		started = time.perf_counter()
		source_id = self._get_source_id(request)
		coordinates = self._get_coordinates(request)
		frame_context = self._get_frame_context(request)
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
			logger.info("PotholePredictView: invoking predictor request_id=%s source=%s payload_bytes=%s", request_id, source_id, len(payload_result.get("payload") or b""))
			output = fog_predictor.predict_pothole_only_from_bytes(
				payload_result["payload"],
				source_id=source_id,
				realtime=self._is_realtime(request),
				coordinates=coordinates,
				frame_id=frame_context["frame_id"],
				stream_id=frame_context["stream_id"],
			)
			try:
				logger.info(
					"PotholePredictView: predictor returned request_id=%s source=%s pothole_summary=%s",
					request_id,
					source_id,
					output.get("pothole_summary"),
				)
			except Exception:
				logger.exception("PotholePredictView: failed to log predictor output for request=%s", request_id)
			
			# Extract annotated frame and cache it in runtime state for fast retrieval
			annotated_frame_bytes = output.pop("_annotated_frame_bytes", None)
			pothole_count = int(output.get("pothole_summary", {}).get("pothole_count", 0))
			pothole_summary = output.get("pothole_summary", {})

			logger.info(
				"PotholePredictView: [EXTRACT] request_id=%s pothole_count=%s frame_bytes_len=%s detections=%s",
				request_id,
				pothole_count,
				len(annotated_frame_bytes) if annotated_frame_bytes is not None else None,
				len(output.get("detections", {})) if output.get("detections") else 0,
			)

			# Update runtime state to cache the frame for /api/pothole/latest-frame/ and /api/pothole/stream/
			logger.info(
				"PotholePredictView: updating runtime state request_id=%s source=%s frame_bytes_len=%s",
				request_id,
				source_id,
				len(annotated_frame_bytes) if annotated_frame_bytes is not None else 0,
			)
			runtime_state.update_pothole_detection(
				source_id=source_id,
				request_id=request_id,
				mode="pothole_only",
				pothole_count=pothole_count,
				detections=output.get("detections", {}),
				coordinates=output.get("pothole_summary", {}).get("coordinates", coordinates),
				frame_bytes=annotated_frame_bytes if isinstance(annotated_frame_bytes, (bytes, bytearray)) else None,
				frame_mime="image/jpeg",
				frame_id=frame_context["frame_id"],
				stream_id=frame_context["stream_id"],
				latency_ms=float(output.get("latency_ms", 0.0)),
			)

			# Save detection results to database for status endpoint to retrieve
			logger.info(
				"PotholePredictView: [DB-SAVE] request_id=%s source=%s pothole_count=%s has_frame=%s",
				request_id,
				source_id,
				pothole_count,
				annotated_frame_bytes is not None,
			)
			PotholeDetection.record_detection(
				source_id=source_id,
				request_id=request_id,
				mode="pothole_only",
				pothole_count=pothole_count,
				total_potholes=pothole_count,
				detections=output.get("detections", {}),
				coordinates=coordinates,
				pothole_metrics=pothole_summary.get("pothole_metrics"),
				annotated_frame=annotated_frame_bytes if isinstance(annotated_frame_bytes, (bytes, bytearray)) else None,
				frame_mime="image/jpeg",
				frame_id=frame_context["frame_id"],
				stream_id=frame_context["stream_id"],
				latency_ms=float(output.get("latency_ms", 0.0)),
			)

			output["request_id"] = request_id
			output["location"] = coordinates
			output["pipeline"] = {
				"dehaze_enabled": bool(output.get("dehazing", {}).get("enabled", False)),
				"annotation_aware_model": bool(output.get("annotation_prior")),
				"fog_probability_source": "xgboost+neural_fusion" if output.get("fog_probability_neural") is not None else "xgboost",
				"real_time_ready": True,
			}
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
		coordinates = self._get_coordinates(request)
		frame_context = self._get_frame_context(request)
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
			output = fog_predictor.predict_combined_from_bytes(
				payload_result["payload"],
				source_id=source_id,
				realtime=self._is_realtime(request),
				coordinates=coordinates,
				frame_id=frame_context["frame_id"],
				stream_id=frame_context["stream_id"],
			)
			output["request_id"] = request_id
			output["location"] = coordinates
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


class PotholeRuntimeStatusView(APIView):
	def get(self, request):
		source_id = str(request.query_params.get("source_id") or "").strip()
		if source_id:
			queryset = PotholeDetection.objects.filter(source_id=source_id)
		else:
			queryset = PotholeDetection.objects.all()

		queryset = queryset.order_by("-created_at")[:50]
		items = [
			{
				"id": row.id,
				"source_id": row.source_id,
				"stream_id": row.stream_id,
				"frame_id": row.frame_id,
				"request_id": row.request_id,
				"mode": row.mode,
				"pothole_count": row.pothole_count,
				"total_potholes": row.total_potholes,
				"pothole_metrics": row.pothole_metrics,
				"coordinates": row.coordinates,
				"detections": row.detections,
				"latency_ms": row.latency_ms,
				"created_at": row.created_at.isoformat(),
				"updated_at": row.updated_at.isoformat(),
			}
			for row in queryset
		]

		# Add mock data if enabled and no real data exists
		if settings.ENABLE_MOCK_DATA and len(items) == 0:
			if mock_generator.should_generate():
				mock_data = mock_generator.generate_mock_pothole_detection(source_id or "phone_pothole_01")
				summary = mock_data.get("pothole_summary", {})
				items.append({
					"id": summary.get("id"),
					"source_id": summary.get("source_id"),
					"stream_id": summary.get("stream_id"),
					"frame_id": summary.get("frame_id"),
					"request_id": summary.get("request_id"),
					"mode": summary.get("mode"),
					"pothole_count": summary.get("pothole_count"),
					"total_potholes": summary.get("total_potholes"),
					"pothole_metrics": summary.get("pothole_metrics"),
					"coordinates": summary.get("coordinates"),
					"detections": mock_data.get("detections"),
					"latency_ms": summary.get("latency_ms"),
					"created_at": summary.get("created_at"),
					"updated_at": summary.get("created_at"),
					"_is_mock": True,
				})

		return Response({"count": len(items), "items": items}, status=status.HTTP_200_OK)


class PotholeLatestFrameView(APIView):
	def get(self, request):
		source_id = str(request.query_params.get("source_id") or "").strip() or None
		record = PotholeDetection.latest_for_source(source_id=source_id)

		# Check if we should fall back to mock data
		if record is None or not record.annotated_frame:
			if settings.ENABLE_MOCK_DATA:
				if mock_generator.should_generate():
					mock_data = mock_generator.generate_mock_pothole_detection(source_id or "mock_pothole_01")
					annotated_bytes = mock_data.get("_annotated_frame_bytes")
					if annotated_bytes:
						return HttpResponse(bytes(annotated_bytes), content_type="image/jpeg")
			return Response({"error": "No annotated pothole frame available."}, status=status.HTTP_404_NOT_FOUND)

		return HttpResponse(bytes(record.annotated_frame), content_type=str(record.frame_mime or "image/jpeg"))


class PotholeMJPEGStreamView(APIView):
	def get(self, request):
		source_id = str(request.query_params.get("source_id") or "").strip() or None
		fps = _as_float(request.query_params.get("fps")) or 3.0
		frame_interval = 1.0 / max(0.5, fps)

		def _placeholder_frame() -> bytes:
			import cv2
			import numpy as np

			frame = np.zeros((480, 640, 3), dtype=np.uint8)
			cv2.putText(frame, "Waiting for pothole frames...", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
			ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
			return encoded.tobytes() if ok else b""

		def _frame_bytes() -> bytes:
			record = PotholeDetection.latest_for_source(source_id=source_id)
			if record is None or not record.annotated_frame:
				return _placeholder_frame()
			return bytes(record.annotated_frame)

		def _stream():
			boundary = b"--frame\r\n"
			headers = b"Content-Type: image/jpeg\r\n\r\n"
			while True:
				payload = _frame_bytes()
				if not payload:
					time.sleep(frame_interval)
					continue
				yield boundary + headers + payload + b"\r\n"
				time.sleep(frame_interval)

		response = StreamingHttpResponse(_stream(), content_type="multipart/x-mixed-replace; boundary=frame")
		response["Cache-Control"] = "no-cache, no-store, must-revalidate"
		response["Pragma"] = "no-cache"
		response["X-Accel-Buffering"] = "no"
		return response


class Esp32TelemetryIngestView(APIView):
	parser_classes = [JSONParser, FormParser, MultiPartParser]

	def post(self, request):
		source_id = str(request.data.get("source_id") or "esp32_unknown").strip() or "esp32_unknown"
		payload: dict[str, object] = {
			"device_ts": request.data.get("device_ts"),
			"seq": request.data.get("seq"),
			"lat": request.data.get("lat"),
			"lng": request.data.get("lng"),
			"speed_kmph": request.data.get("speed_kmph"),
			"temp_c": request.data.get("temp_c"),
			"humidity": request.data.get("humidity"),
			"rssi": request.data.get("rssi"),
			"battery_v": request.data.get("battery_v"),
			"event": request.data.get("event"),
		}
		payload = {k: v for k, v in payload.items() if v is not None}

		stored = runtime_state.update_telemetry(source_id=source_id, payload=payload)
		runtime_state.update_source(
			source_id=source_id,
			mode="esp32_telemetry",
			request_id=str(uuid.uuid4()),
			latency_ms=0.0,
			status_text="ok",
		)
		return Response({"ok": True, "source_id": source_id, "telemetry": stored}, status=status.HTTP_200_OK)


class Esp32TelemetryLatestView(APIView):
	def get(self, request):
		limit_raw = request.query_params.get("limit")
		try:
			limit = int(limit_raw) if limit_raw else 50
		except Exception:
			limit = 50

		rows = runtime_state.list_telemetry(limit=limit)
		return Response({"count": len(rows), "items": rows}, status=status.HTTP_200_OK)


class SimulatePotholeAlertView(APIView):
	def post(self, request):
		try:
			lat = float(request.data.get("lat", 12.9242853))
			lng = float(request.data.get("lng", 77.4996733))
		except (ValueError, TypeError):
			lat = 12.9242853
			lng = 77.4996733
		severity = str(request.data.get("severity", "MEDIUM")).upper()
		source_id = str(request.data.get("source_id", "simulated_source"))
		
		# Get latest record to increment total_potholes
		latest = PotholeDetection.objects.first()
		prev_total = latest.total_potholes if latest else 0
		current_total = prev_total + 1
		
		record = PotholeDetection.record_detection(
			source_id=source_id,
			request_id=str(uuid.uuid4()),
			mode="pothole_only",
			pothole_count=1,
			total_potholes=current_total,
			detections={"items": [{"severity": severity, "confidence": 0.95}]},
			coordinates={"lat": lat, "lng": lng, "location_source": "simulated"},
			pothole_metrics={"max_risk": 0.6, "critical_count": 0, "high_count": 1 if severity == "HIGH" else 0}
		)
		
		# Also update in runtime state
		runtime_state.update_pothole_detection(
			source_id=source_id,
			request_id=record.request_id,
			mode=record.mode,
			pothole_count=record.pothole_count,
			detections=record.detections,
			coordinates=record.coordinates
		)
		
		return Response({"ok": True, "pothole_id": record.id, "total_potholes": current_total}, status=status.HTTP_200_OK)


class SimulateFogAlertView(APIView):
	def post(self, request):
		try:
			lat = float(request.data.get("lat", 12.9242853))
			lng = float(request.data.get("lng", 77.4996733))
		except (ValueError, TypeError):
			lat = 12.9242853
			lng = 77.4996733
		fog_level = str(request.data.get("fog_level", "MEDIUM")).upper()
		risk_score = float(request.data.get("risk_score", 0.5))
		source_id = str(request.data.get("source_id", "simulated_source"))
		
		summary = runtime_state.update_fog_frame(
			source_id=source_id,
			request_id=str(uuid.uuid4()),
			fog_probability=0.8,
			fog_label=fog_level,
			fog_probability_smoothed=0.8,
			fog_level=fog_level,
			visibility_meters=50.0,
			contrast=0.4,
			risk_score=risk_score,
			coordinates={"lat": lat, "lng": lng, "location_source": "simulated"}
		)
		
		# Also update source state
		runtime_state.update_source(
			source_id=source_id,
			mode="fog_camera",
			request_id=str(uuid.uuid4()),
			latency_ms=0.0,
			status_text="ok",
		)
		
		return Response({"ok": True, "fog_summary": summary}, status=status.HTTP_200_OK)
