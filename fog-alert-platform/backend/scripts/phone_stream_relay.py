from __future__ import annotations

import argparse
import time
import uuid
from dataclasses import dataclass

import cv2
import requests


DEFAULT_API_PATHS = {
    "fog": "/api/fog/predict/",
    "pothole": "/api/pothole/predict/",
    "combined": "/api/combined/predict/",
}


@dataclass
class RelayConfig:
    stream_url: str
    backend_url: str
    source_id: str
    stream_id: str
    fps: float
    jpeg_quality: int
    resize_width: int | None
    chunk_size: int
    timeout: float
    reconnect_delay: float
    realtime: bool
    quiet: bool


def parse_args() -> RelayConfig:
    parser = argparse.ArgumentParser(description="Relay frames from IP Webcam to the Django backend in real time.")
    parser.add_argument("--stream-url", required=True, help="IP Webcam URL, for example http://192.168.1.67:6969/video")
    parser.add_argument("--mode", choices=sorted(DEFAULT_API_PATHS.keys()), default="fog", help="Backend mode to target.")
    parser.add_argument(
        "--backend-base",
        default="http://127.0.0.1:8000",
        help="Backend base URL, for example http://192.168.1.41:8000",
    )
    parser.add_argument("--endpoint", default="", help="Override backend endpoint path, for example /api/fog/predict/.")
    parser.add_argument("--source-id", default="phone_01", help="Stable source identifier for the phone.")
    parser.add_argument("--stream-id", default="camera_01", help="Stable stream identifier for this camera stream.")
    parser.add_argument("--fps", type=float, default=5.0, help="How many frames per second to send.")
    parser.add_argument("--jpeg-quality", type=int, default=80, help="JPEG quality for frame compression.")
    parser.add_argument("--resize-width", type=int, default=0, help="Optional resize width before sending. 0 disables resizing.")
    parser.add_argument("--chunk-size", type=int, default=0, help="Optional chunk size in bytes. 0 sends each frame as one image.")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds.")
    parser.add_argument("--reconnect-delay", type=float, default=2.0, help="Delay before reopening the camera stream.")
    parser.add_argument("--realtime", action="store_true", help="Enable backend realtime mode for low-latency inference.")
    parser.add_argument("--quiet", action="store_true", help="Print concise status logs for long-running streams.")
    args = parser.parse_args()

    backend_base = args.backend_base.rstrip("/")
    endpoint = args.endpoint.strip()
    if not endpoint:
        endpoint = DEFAULT_API_PATHS[args.mode]
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    resize_width = args.resize_width if args.resize_width and args.resize_width > 0 else None

    return RelayConfig(
        stream_url=args.stream_url,
        backend_url=f"{backend_base}{endpoint}",
        source_id=args.source_id,
        stream_id=args.stream_id,
        fps=max(0.1, float(args.fps)),
        jpeg_quality=min(95, max(1, int(args.jpeg_quality))),
        resize_width=resize_width,
        chunk_size=max(0, int(args.chunk_size)),
        timeout=max(1.0, float(args.timeout)),
        reconnect_delay=max(0.5, float(args.reconnect_delay)),
        realtime=bool(args.realtime),
        quiet=bool(args.quiet),
    )


def open_camera(stream_url: str) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open stream: {stream_url}")
    return capture


def resize_frame(frame, resize_width: int | None):
    if not resize_width:
        return frame
    height, width = frame.shape[:2]
    if width <= resize_width:
        return frame
    new_height = int(height * (resize_width / float(width)))
    return cv2.resize(frame, (resize_width, new_height), interpolation=cv2.INTER_AREA)


def encode_frame(frame, jpeg_quality: int) -> bytes:
    ok, buffer = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
    )
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG")
    return buffer.tobytes()


def post_image_frame(session: requests.Session, config: RelayConfig, payload: bytes, frame_id: str) -> requests.Response:
    files = {"image": (f"{frame_id}.jpg", payload, "image/jpeg")}
    data = {
        "source_id": config.source_id,
        "stream_id": config.stream_id,
        "frame_id": frame_id,
        "realtime": "true" if config.realtime else "false",
    }
    return session.post(config.backend_url, files=files, data=data, timeout=config.timeout)


def post_chunked_frame(session: requests.Session, config: RelayConfig, payload: bytes, frame_id: str):
    if config.chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0 for chunked uploads")

    total_chunks = max(1, (len(payload) + config.chunk_size - 1) // config.chunk_size)
    last_response: requests.Response | None = None

    for chunk_index in range(total_chunks):
        start = chunk_index * config.chunk_size
        end = min(len(payload), start + config.chunk_size)
        chunk = payload[start:end]
        files = {"chunk": (f"{frame_id}.part{chunk_index}", chunk, "application/octet-stream")}
        data = {
            "source_id": config.source_id,
            "stream_id": config.stream_id,
            "frame_id": frame_id,
            "chunk_index": str(chunk_index),
            "total_chunks": str(total_chunks),
            "realtime": "true" if config.realtime else "false",
        }
        last_response = session.post(config.backend_url, files=files, data=data, timeout=config.timeout)
        if last_response.status_code not in (200, 202):
            return last_response

    if last_response is None:
        raise RuntimeError("Chunked upload did not send any data")
    return last_response


def print_response(response: requests.Response, quiet: bool = False) -> None:
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    if quiet and isinstance(payload, dict):
        request_id = payload.get("request_id", "-")
        latency = payload.get("latency_ms", "-")
        mode = payload.get("mode", "-")
        print(f"[{response.status_code}] mode={mode} req={request_id} latency_ms={latency}")
        return
    print(f"[{response.status_code}] {payload}")


def main() -> int:
    config = parse_args()
    interval = 1.0 / config.fps
    print(f"Relay target: {config.backend_url}")
    print(f"Camera source: {config.stream_url}")
    print(f"Source ID: {config.source_id} | Stream ID: {config.stream_id}")
    print(f"Realtime mode: {config.realtime}")

    session = requests.Session()
    frame_count = 0
    next_tick = time.perf_counter()

    while True:
        try:
            capture = open_camera(config.stream_url)
            print("Camera stream opened. Press Ctrl+C to stop.")

            while True:
                ok, frame = capture.read()
                if not ok or frame is None:
                    print("Frame read failed, reconnecting...")
                    break

                frame = resize_frame(frame, config.resize_width)
                frame_bytes = encode_frame(frame, config.jpeg_quality)
                frame_id = f"{config.stream_id}_{frame_count:08d}_{uuid.uuid4().hex[:8]}"

                if config.chunk_size > 0:
                    response = post_chunked_frame(session, config, frame_bytes, frame_id)
                else:
                    response = post_image_frame(session, config, frame_bytes, frame_id)

                print_response(response, quiet=config.quiet)
                frame_count += 1

                next_tick += interval
                sleep_for = next_tick - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    next_tick = time.perf_counter()

            capture.release()
        except KeyboardInterrupt:
            print("Stopped by user.")
            return 0
        except Exception as exc:
            print(f"Relay error: {exc}")
            time.sleep(config.reconnect_delay)


if __name__ == "__main__":
    raise SystemExit(main())