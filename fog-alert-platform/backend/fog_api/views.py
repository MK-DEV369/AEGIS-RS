from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import fog_predictor


class HealthView(APIView):
	def get(self, request):
		return Response({"status": "ok"})


class FogPredictView(APIView):
	parser_classes = [MultiPartParser]

	def post(self, request):
		image = request.FILES.get("image")
		if image is None:
			return Response(
				{"error": "Missing image file. Send multipart/form-data with key 'image'."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			output = fog_predictor.predict_from_bytes(image.read())
			return Response(output, status=status.HTTP_200_OK)
		except FileNotFoundError as exc:
			return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		except Exception as exc:
			return Response({"error": f"Prediction failed: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
