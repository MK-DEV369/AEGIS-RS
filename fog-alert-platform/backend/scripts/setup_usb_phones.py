from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UsbPhone:
    role: str
    serial: str
    local_port: int


def run_adb(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def list_adb_devices(adb_path: str) -> list[str]:
    proc = run_adb([adb_path, "devices"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Failed to execute adb devices")

    devices: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def adb_forward(adb_path: str, serial: str, local_port: int, remote_port: int) -> None:
    remove_proc = run_adb([adb_path, "-s", serial, "forward", "--remove", f"tcp:{local_port}"])
    if remove_proc.returncode not in (0, 1):
        raise RuntimeError(remove_proc.stderr.strip() or f"Failed to remove existing forward on {local_port}")

    add_proc = run_adb([adb_path, "-s", serial, "forward", f"tcp:{local_port}", f"tcp:{remote_port}"])
    if add_proc.returncode != 0:
        raise RuntimeError(add_proc.stderr.strip() or f"Failed to forward {serial} -> localhost:{local_port}")


def pick_devices(found: list[str], serial_a: str | None, serial_b: str | None) -> tuple[str, str | None]:
    if serial_a and serial_a not in found:
        raise RuntimeError(f"serial-a {serial_a} is not connected")
    if serial_b and serial_b not in found:
        raise RuntimeError(f"serial-b {serial_b} is not connected")

    chosen_a = serial_a
    chosen_b = serial_b

    if not chosen_a:
        if not found:
            raise RuntimeError("No ADB devices found")
        chosen_a = sorted(found)[0]

    if not chosen_b:
        remaining = [s for s in sorted(found) if s != chosen_a]
        chosen_b = remaining[0] if remaining else None

    return chosen_a, chosen_b


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect USB Android phones, assign Phone A/B, and set ADB forwards.")
    parser.add_argument("--adb", default="adb", help="ADB executable path.")
    parser.add_argument("--serial-a", default="", help="Optional device serial for Phone A.")
    parser.add_argument("--serial-b", default="", help="Optional device serial for Phone B.")
    parser.add_argument("--remote-port", type=int, default=6969, help="IP Webcam server port on the phone.")
    parser.add_argument("--local-port-a", type=int, default=16969, help="Localhost port mapped to Phone A.")
    parser.add_argument("--local-port-b", type=int, default=26969, help="Localhost port mapped to Phone B.")
    parser.add_argument("--backend-base", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--save", default="scripts/usb_phone_map.json", help="Output mapping JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    adb_path = args.adb
    if shutil.which(adb_path) is None:
        print("adb not found. Install Android platform-tools and ensure adb is on PATH.")
        return 1

    try:
        devices = list_adb_devices(adb_path)
        serial_a, serial_b = pick_devices(devices, args.serial_a or None, args.serial_b or None)

        phones: list[UsbPhone] = [
            UsbPhone(role="phone_a", serial=serial_a, local_port=int(args.local_port_a)),
        ]
        if serial_b:
            phones.append(UsbPhone(role="phone_b", serial=serial_b, local_port=int(args.local_port_b)))

        for phone in phones:
            adb_forward(adb_path, phone.serial, phone.local_port, int(args.remote_port))

        mapping = {
            "remote_port": int(args.remote_port),
            "backend_base": args.backend_base.rstrip("/"),
            "phones": [
                {
                    "role": p.role,
                    "serial": p.serial,
                    "stream_base": f"http://127.0.0.1:{p.local_port}",
                    "video_url": f"http://127.0.0.1:{p.local_port}/video",
                    "shot_url": f"http://127.0.0.1:{p.local_port}/shot.jpg",
                }
                for p in phones
            ],
        }

        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")

        print("USB assignment complete.")
        for phone in phones:
            print(f"- {phone.role}: serial={phone.serial}, stream=http://127.0.0.1:{phone.local_port}/video")

        backend = args.backend_base.rstrip("/")
        print("\nSuggested relay commands:")
        print(
            "python scripts/phone_stream_relay.py "
            f"--stream-url http://127.0.0.1:{phones[0].local_port}/video "
            f"--backend-base {backend} --mode fog --source-id phone_a --stream-id fog_cam --fps 5"
        )
        if len(phones) > 1:
            print(
                "python scripts/phone_stream_relay.py "
                f"--stream-url http://127.0.0.1:{phones[1].local_port}/video "
                f"--backend-base {backend} --mode pothole --source-id phone_b --stream-id pothole_cam --fps 5"
            )

        print(f"\nSaved mapping: {save_path}")
        return 0
    except Exception as exc:
        print(f"Setup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())