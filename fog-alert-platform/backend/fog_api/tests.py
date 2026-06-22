from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from fog_api.models import PotholeDetection


class ApiWiringTests(TestCase):
	def setUp(self):
		self.client = APIClient()

	def _image_payload(self):
		return {
			"image": SimpleUploadedFile("frame.jpg", b"fake-bytes", content_type="image/jpeg"),
			"source_id": "demo_cam",
		}

	def test_health_exposes_model_configuration(self):
		response = self.client.get("/api/health/")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["status"], "ok")
		self.assertEqual(response.data["models"]["fog_dehaze_model"], str(settings.DEHAZE_MODEL_PATH))
		self.assertEqual(response.data["models"]["pothole_primary_model"], str(settings.YOLOV8_MODEL_PATH))

	def test_pothole_model_defaults_prefer_named_checkpoints(self):
		self.assertEqual(settings.YOLOV8_MODEL_PATH.name, "pothole.pt")
		self.assertEqual([path.name for path in settings.YOLOV8_MODEL_CANDIDATES], ["yolo26n.pt", "yolov8n.pt"])

	def test_fog_endpoint_passes_realtime_flag(self):
		with patch("fog_api.views.fog_predictor.predict_fog_only_from_bytes") as predict_mock:
			predict_mock.return_value = {"prediction": 1, "fog_label": "fog"}
			payload = self._image_payload()
			payload["realtime"] = "true"
			response = self.client.post("/api/fog/predict/", data=payload, format="multipart")

		self.assertEqual(response.status_code, 200)
		predict_mock.assert_called_once()
		self.assertTrue(bool(predict_mock.call_args.kwargs.get("realtime")))

	def test_pothole_endpoint_uses_predictor(self):
		with patch("fog_api.views.fog_predictor.predict_pothole_only_from_bytes") as predict_mock:
			predict_mock.return_value = {"detections": {"count": 1}}
			response = self.client.post("/api/pothole/predict/", data=self._image_payload(), format="multipart")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["detections"]["count"], 1)
		predict_mock.assert_called_once()

	def test_pothole_endpoint_passes_location_and_frame_context(self):
		with patch("fog_api.views.fog_predictor.predict_pothole_only_from_bytes") as predict_mock:
			predict_mock.return_value = {"detections": {"count": 2}, "pothole_summary": {"total_potholes": 2}}
			payload = self._image_payload()
			payload.update({"lat": 12.9716, "lng": 77.5946, "frame_id": "frame_001", "stream_id": "cam_01"})
			response = self.client.post("/api/pothole/predict/", data=payload, format="multipart")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["location"]["lat"], 12.9716)
		self.assertEqual(response.data["location"]["lng"], 77.5946)
		self.assertEqual(response.data["request_id"], response.data["request_id"])
		predict_mock.assert_called_once()
		self.assertEqual(predict_mock.call_args.kwargs.get("frame_id"), "frame_001")
		self.assertEqual(predict_mock.call_args.kwargs.get("stream_id"), "cam_01")

	def test_combined_endpoint_uses_predictor(self):
		with patch("fog_api.views.fog_predictor.predict_combined_from_bytes") as predict_mock:
			predict_mock.return_value = {"prediction": 0, "detections": {"count": 2}}
			response = self.client.post("/api/combined/predict/", data=self._image_payload(), format="multipart")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["detections"]["count"], 2)
		predict_mock.assert_called_once()

	def test_combined_polling_endpoints(self):
		with patch("fog_api.views._fetch_camera_bytes") as fetch_mock:
			fetch_mock.return_value = b"fake-shot"
			# Start combined polling
			response_start = self.client.post("/api/combined/camera/start/", data={"camera_base": "http://127.0.0.1:9999"})
			self.assertEqual(response_start.status_code, 200)
			self.assertTrue(response_start.data["ok"])

			# Check polling status
			response_status = self.client.get("/api/combined/camera/poll_status/")
			self.assertEqual(response_status.status_code, 200)
			self.assertTrue(response_status.data["running"])

			# Stop combined polling
			response_stop = self.client.post("/api/combined/camera/stop/", data={"pothole_source_id": "phone_pothole_01", "fog_source_id": "phone_fog_01"})
			self.assertEqual(response_stop.status_code, 200)
			self.assertTrue(response_stop.data["ok"])

	def test_pothole_status_endpoint_returns_empty_collection(self):
		response = self.client.get("/api/pothole/status/")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 0)
		self.assertEqual(response.data["items"], [])

	def test_pothole_latest_frame_endpoint_returns_404_without_frames(self):
		response = self.client.get("/api/pothole/latest-frame/")

		self.assertEqual(response.status_code, 404)

	def test_pothole_status_endpoint_returns_persisted_rows(self):
		PotholeDetection.record_detection(
			source_id="demo_cam",
			request_id="req-1",
			mode="pothole_only",
			pothole_count=2,
			total_potholes=5,
			detections={"count": 2, "items": []},
			coordinates={"lat": 12.9716, "lng": 77.5946},
			annotated_frame=b"jpeg-bytes",
			frame_id="frame-1",
			stream_id="cam-1",
			latency_ms=12.5,
		)

		response = self.client.get("/api/pothole/status/?source_id=demo_cam")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["items"][0]["source_id"], "demo_cam")
		self.assertEqual(response.data["items"][0]["total_potholes"], 5)

	def test_pothole_mjpeg_stream_returns_multipart_response(self):
		PotholeDetection.record_detection(
			source_id="demo_cam",
			request_id="req-2",
			mode="pothole_only",
			pothole_count=1,
			total_potholes=1,
			detections={"count": 1, "items": []},
			coordinates={"lat": 12.9716, "lng": 77.5946},
			annotated_frame=b"jpeg-bytes",
			frame_id="frame-2",
			stream_id="cam-1",
			latency_ms=8.0,
		)

		response = self.client.get("/api/pothole/stream/?source_id=demo_cam&fps=2")

		self.assertEqual(response.status_code, 200)
		self.assertIn("multipart/x-mixed-replace", response.headers["Content-Type"])
		first_chunk = next(response.streaming_content)
		self.assertIn(b"--frame", first_chunk)
		self.assertIn(b"jpeg-bytes", first_chunk)

	def test_esp32_telemetry_ingest_and_latest(self):
		ingest_response = self.client.post(
			"/api/telemetry/ingest/",
			data={
				"source_id": "esp32_01",
				"seq": 42,
				"lat": 12.9716,
				"lng": 77.5946,
				"speed_kmph": 29.4,
				"temp_c": 31.2,
			},
			format="json",
		)

		self.assertEqual(ingest_response.status_code, 200)
		self.assertTrue(ingest_response.data["ok"])

		latest_response = self.client.get("/api/telemetry/latest/?limit=5")
		self.assertEqual(latest_response.status_code, 200)
		self.assertGreaterEqual(latest_response.data["count"], 1)
		self.assertEqual(latest_response.data["items"][0]["source_id"], "esp32_01")
