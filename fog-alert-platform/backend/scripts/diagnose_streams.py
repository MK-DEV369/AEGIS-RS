#!/usr/bin/env python3
"""
Diagnostics script to capture detailed logs when processing camera streams.
This helps identify exactly where annotated frames are not being generated or cached.

Usage:
  python scripts/diagnose_streams.py --backend-url http://127.0.0.1:8000 \
    --pothole-source phone_pothole_01 --fog-source phone_fog_01
"""

import argparse
import time
import requests
from datetime import datetime

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}  [{datetime.now().strftime('%H:%M:%S')}]")
    print(f"{'='*70}\n")

def check_health(backend_url):
    print_header("Health & Model Status Check")

    try:
        resp = requests.get(f"{backend_url}/api/health/", timeout=5)
        data = resp.json()

        print("Backend Status: ✓ OK\n")

        print("Models Configuration:")
        for model_name, model_path in data.get("models", {}).items():
            print(f"  {model_name:30} {model_path}")

        print("\nValidation Results:")
        validation = data.get("validation", {})

        for component, info in validation.items():
            status = "✓" if info.get("is_loaded") or info.get("enabled") else "✗"
            print(f"\n  {component.upper()} {status}")
            for key, value in info.items():
                if key != "load_error" or value:
                    print(f"    {key:20} {str(value)[:60]}")

        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

def check_sources_status(backend_url):
    print_header("Sources & Streaming Status")

    try:
        resp = requests.get(f"{backend_url}/api/sources/status/", timeout=5)
        data = resp.json()

        print(f"Total sources: {data.get('count', 0)}\n")

        for source in data.get("items", [])[:10]:
            print(f"Source: {source.get('source_id')}")
            print(f"  Mode: {source.get('mode')}")
            print(f"  Status: {source.get('status')}")
            print(f"  Requests: {source.get('request_count')}")
            print(f"  Latency: {source.get('latency_ms')}ms")
            print(f"  Last updated: {time.time() - source.get('updated_at', 0):.1f}s ago\n")

        return True
    except Exception as e:
        print(f"✗ Sources status check failed: {e}")
        return False

def check_pothole_frames(backend_url, source_id):
    print_header(f"Pothole Detection Status - Source: {source_id}")

    try:
        resp = requests.get(
            f"{backend_url}/api/pothole/status/",
            params={"source_id": source_id},
            timeout=5
        )
        data = resp.json()

        print(f"Total detections: {data.get('count', 0)}\n")

        for record in data.get("items", [])[:3]:
            print(f"Detection #{record.get('id')}")
            print(f"  Frame ID: {record.get('frame_id')}")
            print(f"  Potholes: {record.get('pothole_count')}")
            print(f"  Total: {record.get('total_potholes')}")
            print(f"  Max Risk: {record.get('pothole_metrics', {}).get('max_risk', 'N/A')}")
            print(f"  Latency: {record.get('latency_ms', 0):.1f}ms")
            print(f"  Created: {record.get('created_at')}\n")

        # Try to fetch latest frame
        print("Checking annotated frame availability...")
        frame_resp = requests.get(
            f"{backend_url}/api/pothole/latest-frame/",
            params={"source_id": source_id},
            timeout=5
        )

        if frame_resp.status_code == 200:
            frame_size = len(frame_resp.content)
            print(f"✓ Latest pothole frame available: {frame_size} bytes")
        elif frame_resp.status_code == 404:
            print("✗ No pothole frames available yet")
        else:
            print(f"✗ Error fetching frame: {frame_resp.status_code}")

        return True
    except Exception as e:
        print(f"✗ Pothole status check failed: {e}")
        return False

def check_fog_frames(backend_url, source_id):
    print_header(f"Fog Detection Status - Source: {source_id}")

    try:
        resp = requests.get(
            f"{backend_url}/api/fog/status/",
            params={"source_id": source_id},
            timeout=5
        )
        data = resp.json()

        print(f"Total fog frames: {data.get('count', 0)}\n")

        for record in data.get("items", [])[:3]:
            print(f"Fog Detection #{record.get('id') if 'id' in record else 'N/A'}")
            print(f"  Fog Probability: {record.get('fog_probability', 'N/A'):.3f}")
            print(f"  Fog Level: {record.get('fog_label', 'N/A')}")
            print(f"  Visibility: {record.get('visibility_meters', 'N/A')}m")
            print(f"  Latency: {record.get('latency_ms', 0):.1f}ms")
            print(f"  Updated: {record.get('updated_at', 'N/A')}\n")

        # Try to fetch latest frame
        print("Checking annotated fog frame availability...")
        frame_resp = requests.get(
            f"{backend_url}/api/fog/latest-frame/",
            params={"source_id": source_id},
            timeout=5
        )

        if frame_resp.status_code == 200:
            frame_size = len(frame_resp.content)
            print(f"✓ Latest fog frame available: {frame_size} bytes")
        elif frame_resp.status_code == 404:
            print("✗ No fog frames available yet")
        else:
            print(f"✗ Error fetching frame: {frame_resp.status_code}")

        return True
    except Exception as e:
        print(f"✗ Fog status check failed: {e}")
        return False

def check_mjpeg_streams(backend_url, source_id):
    print_header(f"MJPEG Stream Status - Source: {source_id}")

    pothole_url = f"{backend_url}/api/pothole/stream/?source_id={source_id}"
    fog_url = f"{backend_url}/api/fog/stream/?source_id={source_id}"

    print("Testing pothole MJPEG stream...")
    try:
        resp = requests.get(pothole_url, stream=True, timeout=3)
        if resp.status_code == 200:
            # Try to read first frame boundary
            for line in resp.iter_content(chunk_size=1024):
                if b"--frame" in line or b"Content-Type" in line or b"jpeg" in line:
                    print(f"✓ Pothole MJPEG stream is responding")
                    break
            resp.close()
        else:
            print(f"✗ Pothole stream returned: {resp.status_code}")
    except Exception as e:
        print(f"✗ Pothole stream error: {e}")

    print("\nTesting fog MJPEG stream...")
    try:
        resp = requests.get(fog_url, stream=True, timeout=3)
        if resp.status_code == 200:
            for line in resp.iter_content(chunk_size=1024):
                if b"--frame" in line or b"Content-Type" in line or b"jpeg" in line:
                    print(f"✓ Fog MJPEG stream is responding")
                    break
            resp.close()
        else:
            print(f"✗ Fog stream returned: {resp.status_code}")
    except Exception as e:
        print(f"✗ Fog stream error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Diagnose fog-alert-platform streams")
    parser.add_argument(
        "--backend-url",
        default="http://127.0.0.1:8000",
        help="Backend URL (default: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--pothole-source",
        default="phone_pothole_01",
        help="Pothole source ID (default: phone_pothole_01)"
    )
    parser.add_argument(
        "--fog-source",
        default="phone_fog_01",
        help="Fog source ID (default: phone_fog_01)"
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=1,
        help="Loop every N seconds (0 = run once, default: 1)"
    )

    args = parser.parse_args()
    backend_url = args.backend_url.rstrip('/')

    print("\n" + "="*70)
    print("  FOG-ALERT-PLATFORM DIAGNOSTICS")
    print("="*70)

    try:
        iteration = 0
        while True:
            iteration += 1
            if args.loop == 0:
                print(f"\nDiagnostics Run #{iteration}")
            else:
                print(f"\nDiagnostics Run #{iteration} (refreshing every {args.loop}s)")

            check_health(backend_url)
            check_sources_status(backend_url)
            check_pothole_frames(backend_url, args.pothole_source)
            check_fog_frames(backend_url, args.fog_source)
            check_mjpeg_streams(backend_url, args.pothole_source)

            if args.loop == 0:
                break

            print(f"\n[Press Ctrl+C to stop] Next check in {args.loop}s...")
            time.sleep(args.loop)

    except KeyboardInterrupt:
        print("\n\nDiagnostics stopped by user.")

if __name__ == "__main__":
    main()
