from __future__ import annotations

import time
from threading import Lock

from django.conf import settings


class RuntimeState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._source_state: dict[str, dict[str, object]] = {}
        self._chunk_state: dict[str, dict[str, object]] = {}

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
            if received < total_chunks:
                return {
                    "ok": True,
                    "complete": False,
                    "received_chunks": received,
                    "total_chunks": total_chunks,
                }

            ordered = b"".join(parts[idx] for idx in range(total_chunks))
            self._chunk_state.pop(chunk_key, None)
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
            self._source_state.clear()
            self._chunk_state.clear()
        return {"sources_cleared": source_count, "chunks_cleared": chunk_count}


runtime_state = RuntimeState()
