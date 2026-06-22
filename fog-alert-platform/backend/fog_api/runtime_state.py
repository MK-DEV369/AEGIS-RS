from __future__ import annotations

import time
import logging
from threading import Lock

from django.conf import settings


logger = logging.getLogger(__name__)


class RuntimeState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._source_state: dict[str, dict[str, object]] = {}
        self._chunk_state: dict[str, dict[str, object]] = {}
        self._telemetry_state: dict[str, dict[str, object]] = {}
        self._pothole_state: dict[str, dict[str, object]] = {}
        self._fog_state: dict[str, dict[str, object]] = {}

    def _cleanup_locked(self) -> None:
        now = time.time()
        source_ttl = float(settings.SOURCE_STATUS_TTL_SECONDS)
        chunk_ttl = float(settings.STREAM_CHUNK_TTL_SECONDS)

        stale_sources = [
            source_id
            for source_id, meta in self._source_state.items()
            if now - float(meta.get("updated_at", now)) > source_ttl
        ]
        for source_id in stale_sources:
            self._source_state.pop(source_id, None)

        stale_chunks = [
            chunk_key
            for chunk_key, meta in self._chunk_state.items()
            if now - float(meta.get("updated_at", now)) > chunk_ttl
        ]
        for chunk_key in stale_chunks:
            self._chunk_state.pop(chunk_key, None)

        stale_telemetry = [
            source_id
            for source_id, meta in self._telemetry_state.items()
            if now - float(meta.get("updated_at", now)) > source_ttl
        ]
        for source_id in stale_telemetry:
            self._telemetry_state.pop(source_id, None)

        stale_pothole_sources = [
            source_id
            for source_id, meta in self._pothole_state.items()
            if now - float(meta.get("updated_at", now)) > source_ttl
        ]
        for source_id in stale_pothole_sources:
            self._pothole_state.pop(source_id, None)

        stale_fog_sources = [
            source_id
            for source_id, meta in self._fog_state.items()
            if now - float(meta.get("updated_at", now)) > source_ttl
        ]
        for source_id in stale_fog_sources:
            self._fog_state.pop(source_id, None)

    def update_source(
        self,
        *,
        source_id: str,
        mode: str,
        request_id: str,
        latency_ms: float | None,
        status_text: str,
    ) -> None:
        now = time.time()
        with self._lock:
            self._cleanup_locked()
            current = self._source_state.get(source_id, {})
            request_count = int(current.get("request_count", 0)) + 1
            error_count = int(current.get("error_count", 0)) + (1 if status_text != "ok" else 0)
            self._source_state[source_id] = {
                "source_id": source_id,
                "mode": mode,
                "request_id": request_id,
                "status": status_text,
                "request_count": request_count,
                "error_count": error_count,
                "latency_ms": latency_ms,
                "updated_at": now,
            }

    def list_sources(self) -> list[dict[str, object]]:
        with self._lock:
            self._cleanup_locked()
            rows = list(self._source_state.values())
        rows.sort(key=lambda item: float(item.get("updated_at", 0.0)), reverse=True)
        return rows

    def update_telemetry(self, *, source_id: str, payload: dict[str, object]) -> dict[str, object]:
        now = time.time()
        with self._lock:
            self._cleanup_locked()
            current = self._telemetry_state.get(source_id, {})
            sample_count = int(current.get("sample_count", 0)) + 1
            merged = {
                **payload,
                "source_id": source_id,
                "sample_count": sample_count,
                "updated_at": now,
            }
            self._telemetry_state[source_id] = merged
            return merged

    def list_telemetry(self, limit: int = 50) -> list[dict[str, object]]:
        with self._lock:
            self._cleanup_locked()
            rows = list(self._telemetry_state.values())
        rows.sort(key=lambda item: float(item.get("updated_at", 0.0)), reverse=True)
        return rows[: max(1, int(limit))]

    def update_pothole_detection(
        self,
        *,
        source_id: str,
        request_id: str,
        mode: str,
        pothole_count: int,
        detections: dict[str, object],
        coordinates: dict[str, object] | None = None,
        frame_bytes: bytes | None = None,
        frame_mime: str = "image/jpeg",
        frame_id: str | None = None,
        stream_id: str | None = None,
        latency_ms: float | None = None,
    ) -> dict[str, object]:
        now = time.time()
        with self._lock:
            self._cleanup_locked()
            current = self._pothole_state.get(source_id, {})
            frame_count = int(current.get("frame_count", 0)) + 1
            total_potholes = int(current.get("total_potholes", 0)) + max(0, int(pothole_count))
            current["source_id"] = source_id
            current["request_id"] = request_id
            current["mode"] = mode
            current["frame_count"] = frame_count
            current["pothole_count"] = int(pothole_count)
            current["total_potholes"] = total_potholes
            current["detections"] = detections
            current["coordinates"] = coordinates or current.get("coordinates")
            current["frame_id"] = frame_id
            current["stream_id"] = stream_id
            current["latency_ms"] = latency_ms
            current["updated_at"] = now
            current["frame_mime"] = frame_mime
            if frame_bytes is not None:
                current["frame_bytes"] = frame_bytes
                current["frame_updated_at"] = now
                if settings.PIPELINE_DEBUG_LOGS:
                    try:
                        logger.info(
                            "runtime_state.update_pothole_detection source=%s request_id=%s frame_bytes_len=%s pothole_count=%s total_potholes=%s",
                            source_id,
                            request_id,
                            len(frame_bytes) if frame_bytes is not None else 0,
                            pothole_count,
                            total_potholes,
                        )
                    except Exception:
                        logger.exception("Failed to log pothole frame update for source=%s", source_id)
            self._pothole_state[source_id] = current

            summary = dict(current)
            summary.pop("frame_bytes", None)
            return summary

    def list_pothole_detections(self, limit: int = 50) -> list[dict[str, object]]:
        with self._lock:
            self._cleanup_locked()
            rows = []
            for meta in self._pothole_state.values():
                row = dict(meta)
                row.pop("frame_bytes", None)
                rows.append(row)
        rows.sort(key=lambda item: float(item.get("updated_at", 0.0)), reverse=True)
        return rows[: max(1, int(limit))]

    def get_latest_pothole_frame(self, source_id: str | None = None) -> dict[str, object] | None:
        with self._lock:
            self._cleanup_locked()
            if source_id:
                meta = self._pothole_state.get(source_id)
                if not meta:
                    return None
                frame_bytes = meta.get("frame_bytes")
                if not isinstance(frame_bytes, (bytes, bytearray)):
                    return None
                return {
                    "source_id": source_id,
                    "frame_bytes": bytes(frame_bytes),
                    "frame_mime": str(meta.get("frame_mime") or "image/jpeg"),
                    "updated_at": float(meta.get("frame_updated_at", meta.get("updated_at", 0.0))),
                }

            latest_meta: dict[str, object] | None = None
            latest_updated_at = -1.0
            for meta in self._pothole_state.values():
                frame_bytes = meta.get("frame_bytes")
                if not isinstance(frame_bytes, (bytes, bytearray)):
                    continue
                updated_at = float(meta.get("frame_updated_at", meta.get("updated_at", 0.0)))
                if updated_at > latest_updated_at:
                    latest_updated_at = updated_at
                    latest_meta = {
                        "source_id": meta.get("source_id"),
                        "frame_bytes": bytes(frame_bytes),
                        "frame_mime": str(meta.get("frame_mime") or "image/jpeg"),
                        "updated_at": updated_at,
                    }
            return latest_meta

    def update_fog_frame(
            self,
            *,
            source_id: str,
            request_id: str,
            fog_probability: float,
            fog_label: str,
            fog_probability_smoothed: float = 0.0,
            fog_level: str = "unknown",
            visibility_meters: float = 0.0,
            contrast: float = 0.0,
            risk_score: float = 0.0,
            frame_bytes: bytes | None = None,
            frame_mime: str = "image/jpeg",
            frame_id: str | None = None,
            stream_id: str | None = None,
            coordinates: dict[str, object] | None = None,
            latency_ms: float | None = None,
        ) -> dict[str, object]:
            now = time.time()
            with self._lock:
                self._cleanup_locked()
                current = self._fog_state.get(source_id, {})
                frame_count = int(current.get("frame_count", 0)) + 1
                current["source_id"] = source_id
                current["request_id"] = request_id
                current["frame_count"] = frame_count
                current["fog_probability"] = float(fog_probability)
                current["fog_probability_smoothed"] = float(fog_probability_smoothed)
                current["fog_label"] = str(fog_label)
                current["fog_level"] = str(fog_level)
                current["visibility_meters"] = float(visibility_meters)
                current["contrast"] = float(contrast)
                current["risk_score"] = float(risk_score)
                current["frame_id"] = frame_id
                current["stream_id"] = stream_id
                current["coordinates"] = coordinates or current.get("coordinates")
                current["latency_ms"] = latency_ms
                current["updated_at"] = now
                current["frame_mime"] = frame_mime
                if frame_bytes is not None:
                    current["frame_bytes"] = frame_bytes
                    current["frame_updated_at"] = now
                self._fog_state[source_id] = current

                summary = dict(current)
                summary.pop("frame_bytes", None)
                return summary
            
    def list_fog_frames(self, limit: int = 50) -> list[dict[str, object]]:
        with self._lock:
            self._cleanup_locked()
            rows = []
            for meta in self._fog_state.values():
                row = dict(meta)
                row.pop("frame_bytes", None)
                rows.append(row)
        rows.sort(key=lambda item: float(item.get("updated_at", 0.0)), reverse=True)
        return rows[: max(1, int(limit))]

    def get_latest_fog_frame(self, source_id: str | None = None) -> dict[str, object] | None:
        with self._lock:
            self._cleanup_locked()
            if source_id:
                meta = self._fog_state.get(source_id)
                if not meta:
                    return None
                frame_bytes = meta.get("frame_bytes")
                if not isinstance(frame_bytes, (bytes, bytearray)):
                    return None
                return {
                    "source_id": source_id,
                    "frame_bytes": bytes(frame_bytes),
                    "frame_mime": str(meta.get("frame_mime") or "image/jpeg"),
                    "updated_at": float(meta.get("frame_updated_at", meta.get("updated_at", 0.0))),
                }

            latest_meta: dict[str, object] | None = None
            latest_updated_at = -1.0
            for meta in self._fog_state.values():
                frame_bytes = meta.get("frame_bytes")
                if not isinstance(frame_bytes, (bytes, bytearray)):
                    continue
                updated_at = float(meta.get("frame_updated_at", meta.get("updated_at", 0.0)))
                if updated_at > latest_updated_at:
                    latest_updated_at = updated_at
                    latest_meta = {
                        "source_id": meta.get("source_id"),
                        "frame_bytes": bytes(frame_bytes),
                        "frame_mime": str(meta.get("frame_mime") or "image/jpeg"),
                        "updated_at": updated_at,
                    }
            return latest_meta

    def store_chunk(
        self,
        *,
        chunk_key: str,
        total_chunks: int,
        chunk_index: int,
        chunk_bytes: bytes,
    ) -> dict[str, object]:
        now = time.time()
        with self._lock:
            self._cleanup_locked()

            if len(chunk_bytes) > int(settings.STREAM_MAX_CHUNK_BYTES):
                return {
                    "ok": False,
                    "error": f"Chunk too large. Max allowed is {settings.STREAM_MAX_CHUNK_BYTES} bytes.",
                }
            if total_chunks < 1 or total_chunks > int(settings.STREAM_MAX_CHUNKS_PER_FRAME):
                return {
                    "ok": False,
                    "error": (
                        "Invalid total_chunks. "
                        f"Allowed range is 1..{settings.STREAM_MAX_CHUNKS_PER_FRAME}."
                    ),
                }
            if chunk_index < 0 or chunk_index >= total_chunks:
                return {
                    "ok": False,
                    "error": "Invalid chunk_index for provided total_chunks.",
                }

            entry = self._chunk_state.get(chunk_key)
            if entry is None:
                entry = {
                    "total_chunks": total_chunks,
                    "parts": {},
                    "created_at": now,
                    "updated_at": now,
                }
                self._chunk_state[chunk_key] = entry
            elif int(entry["total_chunks"]) != total_chunks:
                return {
                    "ok": False,
                    "error": "Mismatched total_chunks for an existing chunk sequence.",
                }

            parts: dict[int, bytes] = entry["parts"]  # type: ignore[assignment]
            parts[chunk_index] = chunk_bytes
            entry["updated_at"] = now

            received = len(parts)
            if settings.PIPELINE_DEBUG_LOGS:
                try:
                    logger.info(
                        "store_chunk received chunk_key=%s chunk_index=%s total_chunks=%s received=%s",
                        chunk_key,
                        chunk_index,
                        total_chunks,
                        received,
                    )
                except Exception:
                    logger.exception("Failed to log chunk receipt for %s", chunk_key)

            if received < total_chunks:
                return {
                    "ok": True,
                    "complete": False,
                    "received_chunks": received,
                    "total_chunks": total_chunks,
                }

            ordered = b"".join(parts[idx] for idx in range(total_chunks))
            self._chunk_state.pop(chunk_key, None)
            if settings.PIPELINE_DEBUG_LOGS:
                try:
                    logger.info(
                        "store_chunk complete chunk_key=%s assembled_bytes=%s",
                        chunk_key,
                        len(ordered),
                    )
                except Exception:
                    logger.exception("Failed to log chunk assembly for %s", chunk_key)

            return {
                "ok": True,
                "complete": True,
                "payload": ordered,
                "received_chunks": received,
                "total_chunks": total_chunks,
            }

    def clear(self) -> dict[str, int]:
        with self._lock:
            source_count = len(self._source_state)
            chunk_count = len(self._chunk_state)
            telemetry_count = len(self._telemetry_state)
            pothole_count = len(self._pothole_state)
            fog_count = len(self._fog_state)
            self._source_state.clear()
            self._chunk_state.clear()
            self._telemetry_state.clear()
            self._pothole_state.clear()
            self._fog_state.clear()
        return {
            "sources_cleared": source_count,
            "chunks_cleared": chunk_count,
            "telemetry_cleared": telemetry_count,
            "pothole_sources_cleared": pothole_count,
            "fog_sources_cleared": fog_count,
        }


runtime_state = RuntimeState()
