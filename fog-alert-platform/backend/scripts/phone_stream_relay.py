from __future__ import annotations

import argparse
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urljoin

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
    phone_base_url: str | None
    shot_url: str | None
    audio_wav_url: str | None
    audio_aac_url: str | None
    audio_opus_url: str | None
    focus_url: str | None
    nofocus_url: str | None
    source_id: str
    stream_id: str
    fps: float
    jpeg_quality: int
    resize_width: int | None
    chunk_size: int
    timeout: float
    reconnect_delay: float
    realtime: bool
    latitude: float | None
    longitude: float | None
    location_source: str | None
    accuracy_m: float | None
    frame_skip: int
    autofocus_on_start: bool
    release_focus_on_stop: bool
    quiet: bool


def parse_args() -> RelayConfig:
    parser = argparse.ArgumentParser(description="Relay frames from IP Webcam to the Django backend in real time.")
    parser.add_argument("--stream-url", default="", help="IP Webcam URL, for example http://192.168.1.67:6969/video")
    parser.add_argument(
        "--phone-base-url",
        default="http://10.203.106.139:6969",
        help="Phone base URL, for example http://10.203.106.139:6969. If stream URL is not provided, /video is used.",
    )
    parser.add_argument("--shot-url", default="", help="Optional latest-frame URL override, for example http://host:port/shot.jpg")
    parser.add_argument("--audio-wav-url", default="", help="Optional WAV audio stream URL override.")
    parser.add_argument("--audio-aac-url", default="", help="Optional AAC audio stream URL override.")
    parser.add_argument("--audio-opus-url", default="", help="Optional Opus audio stream URL override.")
    parser.add_argument("--focus-url", default="", help="Optional focus control URL override.")
    parser.add_argument("--nofocus-url", default="", help="Optional focus release URL override.")
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
    parser.add_argument("--lat", type=float, default=None, help="Optional latitude to attach to each frame.")
    parser.add_argument("--lng", type=float, default=None, help="Optional longitude to attach to each frame.")
    parser.add_argument("--location-source", default="", help="Optional location source label, for example browser or mobile.")
    parser.add_argument("--accuracy-m", type=float, default=None, help="Optional GPS accuracy in meters.")
    parser.add_argument("--frame-skip", type=int, default=2, help="Send every Nth captured frame to reduce GPU load. 1 sends all frames.")
    parser.add_argument("--autofocus-on-start", action="store_true", help="Call the phone /focus endpoint when capture starts.")
    parser.add_argument("--release-focus-on-stop", action="store_true", help="Call the phone /nofocus endpoint on shutdown.")
    parser.add_argument("--quiet", action="store_true", help="Print concise status logs for long-running streams.")
    args = parser.parse_args()

    backend_base = args.backend_base.rstrip("/")
    endpoint = args.endpoint.strip()
    if not endpoint:
        endpoint = DEFAULT_API_PATHS[args.mode]
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    phone_base = args.phone_base_url.strip().rstrip("/")

    def _resolve_phone_path(path: str, override: str) -> str | None:
        override = override.strip()
        if override:
            return override
        if not phone_base:
            return None
        return urljoin(phone_base + "/", path)

    stream_url = args.stream_url.strip() or _resolve_phone_path("video", "") or ""
    if not stream_url:
        raise SystemExit("Provide --stream-url or --phone-base-url (for example http://10.203.106.139:6969).")

    resize_width = args.resize_width if args.resize_width and args.resize_width > 0 else None

    return RelayConfig(
        stream_url=stream_url,
        backend_url=f"{backend_base}{endpoint}",
        phone_base_url=phone_base or None,
        shot_url=_resolve_phone_path("shot.jpg", args.shot_url),
        audio_wav_url=_resolve_phone_path("audio.wav", args.audio_wav_url),
        audio_aac_url=_resolve_phone_path("audio.aac", args.audio_aac_url),
        audio_opus_url=_resolve_phone_path("audio.opus", args.audio_opus_url),
        focus_url=_resolve_phone_path("focus", args.focus_url),
        nofocus_url=_resolve_phone_path("nofocus", args.nofocus_url),
        source_id=args.source_id,
        stream_id=args.stream_id,
        fps=max(0.1, float(args.fps)),
        jpeg_quality=min(95, max(1, int(args.jpeg_quality))),
        resize_width=resize_width,
        chunk_size=max(0, int(args.chunk_size)),
        timeout=max(1.0, float(args.timeout)),
        reconnect_delay=max(0.5, float(args.reconnect_delay)),
        realtime=bool(args.realtime),
        latitude=args.lat,
        longitude=args.lng,
        location_source=args.location_source.strip() or None,
        accuracy_m=args.accuracy_m,
        frame_skip=max(1, int(args.frame_skip)),
        autofocus_on_start=bool(args.autofocus_on_start),
        release_focus_on_stop=bool(args.release_focus_on_stop),
        quiet=bool(args.quiet),
    )


def open_camera(stream_url: str) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open stream: {stream_url}")
    return capture


def send_phone_command(session: requests.Session, command_url: str | None, timeout: float, quiet: bool, label: str) -> None:
    if not command_url:
        return
    try:
        response = session.get(command_url, timeout=timeout)
        if quiet:
            print(f"Phone {label}: {response.status_code}")
        else:
            print(f"Phone {label}: {command_url} [{response.status_code}]")
    except Exception as exc:
        print(f"Phone {label} failed: {exc}")


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
    if config.latitude is not None and config.longitude is not None:
        data["lat"] = str(config.latitude)
        data["lng"] = str(config.longitude)
    if config.location_source:
        data["location_source"] = config.location_source
    if config.accuracy_m is not None:
        data["accuracy_m"] = str(config.accuracy_m)
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
        if config.latitude is not None and config.longitude is not None:
            data["lat"] = str(config.latitude)
            data["lng"] = str(config.longitude)
        if config.location_source:
            data["location_source"] = config.location_source
        if config.accuracy_m is not None:
            data["accuracy_m"] = str(config.accuracy_m)
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
    print(f"Frame skip: every {config.frame_skip} frame(s)")
    if config.latitude is not None and config.longitude is not None:
        print(f"Location: {config.latitude}, {config.longitude} ({config.location_source or 'unknown'})")
    if config.phone_base_url:
        print(f"Phone base URL: {config.phone_base_url}")
        if config.shot_url:
            print(f"Snapshot URL: {config.shot_url}")
        if config.audio_wav_url:
            print(f"Audio WAV: {config.audio_wav_url}")
        if config.audio_aac_url:
            print(f"Audio AAC: {config.audio_aac_url}")
        if config.audio_opus_url:
            print(f"Audio Opus: {config.audio_opus_url}")
        if config.focus_url:
            print(f"Focus URL: {config.focus_url}")
        if config.nofocus_url:
            print(f"NoFocus URL: {config.nofocus_url}")

    session = requests.Session()
    frame_count = 0
    next_tick = time.perf_counter()

    while True:
        try:
            capture = open_camera(config.stream_url)
            print("Camera stream opened. Press Ctrl+C to stop.")
            if config.autofocus_on_start:
                send_phone_command(session, config.focus_url, config.timeout, config.quiet, "focus")

            while True:
                ok, frame = capture.read()
                if not ok or frame is None:
                    print("Frame read failed, reconnecting...")
                    break

                frame = resize_frame(frame, config.resize_width)
                frame_bytes = encode_frame(frame, config.jpeg_quality)
                frame_id = f"{config.stream_id}_{frame_count:08d}_{uuid.uuid4().hex[:8]}"

                if config.frame_skip > 1 and frame_count % config.frame_skip != 0:
                    frame_count += 1
                    next_tick += interval
                    sleep_for = next_tick - time.perf_counter()
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                    else:
                        next_tick = time.perf_counter()
                    continue

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
            if config.release_focus_on_stop:
                send_phone_command(session, config.nofocus_url, config.timeout, config.quiet, "nofocus")
            print("Stopped by user.")
            return 0
        except Exception as exc:
            print(f"Relay error: {exc}")
            time.sleep(config.reconnect_delay)


if __name__ == "__main__":
    raise SystemExit(main())