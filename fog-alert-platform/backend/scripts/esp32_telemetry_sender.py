from __future__ import annotations

import argparse
import random
import time

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send ESP32-like telemetry to backend demo endpoint.")
    parser.add_argument("--backend-base", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--source-id", default="esp32_01", help="Telemetry source id")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between packets")
    parser.add_argument("--count", type=int, default=120, help="Number of samples to send")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = args.backend_base.rstrip("/")
    url = f"{base}/api/telemetry/ingest/"

    with requests.Session() as session:
        for seq in range(max(1, int(args.count))):
            payload = {
                "source_id": args.source_id,
                "seq": seq,
                "device_ts": int(time.time() * 1000),
                "lat": 12.9716 + random.uniform(-0.0008, 0.0008),
                "lng": 77.5946 + random.uniform(-0.0008, 0.0008),
                "speed_kmph": round(24 + random.uniform(-6, 10), 2),
                "temp_c": round(31 + random.uniform(-2, 3), 2),
                "humidity": round(58 + random.uniform(-8, 8), 2),
                "rssi": int(-60 + random.uniform(-14, 6)),
                "battery_v": round(3.7 + random.uniform(-0.1, 0.1), 3),
                "event": "normal",
            }
            response = session.post(url, json=payload, timeout=5)
            print(f"[{response.status_code}] seq={seq}")
            time.sleep(max(0.05, float(args.interval)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
