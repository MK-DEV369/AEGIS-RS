import argparse
import sys
import time
import requests
import json
import serial
import serial.tools.list_ports

def get_serial_ports():
    """Detect all connected USB-to-UART ports."""
    ports = serial.tools.list_ports.comports()
    esp_ports = []
    for p in ports:
        # CP210x, CH340, CH341, FTDI, USB Serial are common ESP32 USB chips
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        # Include all COM ports unless they are known non-COM devices
        esp_ports.append(p.device)
    return esp_ports

def get_worst_severity(item):
    """Scan pothole detections for the highest severity level."""
    worst_severity = "LOW"
    severity_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    
    # 1. Check detections list
    detections_list = item.get("detections", {})
    if isinstance(detections_list, dict):
        detections_items = detections_list.get("items", [])
        if isinstance(detections_items, list):
            for det in detections_items:
                sev = str(det.get("severity", "LOW")).upper()
                if severity_order.get(sev, 0) > severity_order.get(worst_severity, 0):
                    worst_severity = sev

    # 2. Check metrics fallback
    metrics = item.get("pothole_metrics", {}) or {}
    if worst_severity == "LOW":
        if metrics.get("critical_count", 0) > 0:
            worst_severity = "CRITICAL"
        elif metrics.get("high_count", 0) > 0:
            worst_severity = "HIGH"
        elif metrics.get("max_risk", 0.0) > 0.6:
            worst_severity = "MEDIUM"
            
    return worst_severity

def main():
    parser = argparse.ArgumentParser(description="Relay pothole detections to ESP32 over serial.")
    parser.add_argument("--backend-base", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--interval", type=float, default=0.5, help="Polling interval in seconds")
    args = parser.parse_args()
    
    base_url = args.backend_base.rstrip("/")
    status_url = f"{base_url}/api/pothole/status/"
    fog_status_url = f"{base_url}/api/fog/status/"
    
    print("==================================================")
    print(" AEGIS-RS ESP32 Serial Relay Daemon")
    print(f" Backend Pothole URL: {status_url}")
    print(f" Backend Fog URL:     {fog_status_url}")
    print(f" Baud Rate:           {args.baud}")
    print(f" Interval:            {args.interval}s")
    print("==================================================")
    
    last_processed_id = None
    last_processed_total_potholes = None
    last_processed_fog_request_id = None
    last_sent_fog_level = None
    last_sent_fog_time = 0.0
    open_connections = {}
    
    last_scan_time = 0
    
    while True:
        current_time = time.time()
        
        # Periodically scan and refresh serial ports every 5 seconds
        if current_time - last_scan_time > 5.0:
            last_scan_time = current_time
            available_ports = get_serial_ports()
            
            # Close disconnected ports
            for port in list(open_connections.keys()):
                if port not in available_ports:
                    print(f"[-] Port {port} disconnected. Closing connection.")
                    try:
                        open_connections[port].close()
                    except Exception:
                        pass
                    del open_connections[port]
            
            # Open newly connected ports
            for port in available_ports:
                if port not in open_connections:
                    print(f"[+] Found COM port {port}. Opening connection...")
                    try:
                        ser = serial.Serial(port, args.baud, timeout=1)
                        # Allow ESP32 reset time
                        time.sleep(1.5)
                        open_connections[port] = ser
                        print(f"[+] COM port {port} successfully connected.")
                    except Exception as e:
                        print(f"[!] Failed to open port {port}: {e}")
                        
        # Read incoming logs/messages from ESP32s (like warnings received via ESP-NOW)
        for port, ser in list(open_connections.items()):
            try:
                while ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"[{port} ESP32] {line}")
                        # Check if line is from RSU Receiver and formatted as JSON
                        # Expected: {"type":"RSU_Pothole","lat":...,"lng":...,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};
                        if line.startswith('{"type":') and line.endswith('};'):
                            json_str = line.rstrip(';').strip()
                            try:
                                data = json.loads(json_str)
                                print(f"[+] Parsed RSU disseminated alert from {port}: {data}")
                                
                                # POST to telemetry ingest endpoint
                                ingest_url = f"{base_url}/api/telemetry/ingest/"
                                lat = float(data.get("lat", 0.0))
                                lng = float(data.get("lng", 0.0))
                                event_type = data.get("type", "RSU_Pothole")
                                
                                # Use dynamic source_id to prevent overwriting different events/locations
                                dynamic_source = f"RSU_{event_type}_{lat:.6f}_{lng:.6f}"
                                
                                payload = {
                                    "source_id": dynamic_source,
                                    "lat": lat,
                                    "lng": lng,
                                    "speed_kmph": float(data.get("speed", 35.0)),
                                    "event": event_type,
                                    "status": data.get("status", "DISSEMINATED"),
                                    "device_ts": int(time.time()),
                                    "seq": 1
                                }
                                
                                print(f"[*] Posting RSU telemetry to backend: {payload}")
                                ingest_response = requests.post(ingest_url, json=payload, timeout=2)
                                if ingest_response.status_code == 200:
                                    print(f"[+] Successfully registered RSU alert on backend.")
                                else:
                                    print(f"[!] Failed to ingest RSU alert: HTTP {ingest_response.status_code}")
                            except Exception as parse_err:
                                print(f"[!] Failed to parse RSU JSON: {parse_err}")
            except Exception as e:
                print(f"[!] Error reading serial from {port}: {e}")
                
        # 1. Poll backend for latest pothole status
        try:
            response = requests.get(status_url, timeout=2)
            if response.status_code == 200:
                payload = response.json()
                items = payload.get("items", [])
                
                if items:
                    latest = items[0]
                    latest_id = latest.get("id")
                    current_total = int(latest.get("total_potholes", 0))
                    
                    # Initialize last_processed_total_potholes and last_processed_id on startup
                    if last_processed_total_potholes is None:
                        last_processed_total_potholes = current_total
                        last_processed_id = latest_id
                        print(f"[*] Initialized pothole tracking: latest_id={latest_id}, total_potholes={current_total}")
                    
                    # Process new detections only if total_potholes has incremented (meaning a new unique pothole is detected)
                    elif current_total > last_processed_total_potholes:
                        pothole_count = latest.get("pothole_count", 0)
                        source_id = latest.get("source_id", "unknown_source")
                        coords = latest.get("coordinates") or {}
                        lat = float(coords.get("lat") or 0.0)
                        lng = float(coords.get("lng") or 0.0)
                        
                        severity = get_worst_severity(latest)
                        
                        # Build protocol message: POTHOLE:severity,lat,lng,count,source
                        msg = f"POTHOLE:{severity},{lat:.6f},{lng:.6f},{pothole_count},{source_id}\n"
                        
                        print(f"\n[EVENT] New UNIQUE pothole detected! total_potholes increased from {last_processed_total_potholes} to {current_total}. count={pothole_count}")
                        last_processed_total_potholes = current_total
                        last_processed_id = latest_id
                        
                        if not open_connections:
                            print(f"[!] No ESP32 COM ports connected. Output: {msg.strip()}")
                        else:
                            for port, ser in open_connections.items():
                                try:
                                    ser.write(msg.encode("utf-8"))
                                    print(f"[*] Sent to {port} -> {msg.strip()}")
                                except Exception as e:
                                    print(f"[!] Failed to write to {port}: {e}")
                    
                    # Fallback update to keep last_processed_id fresh even if no new unique potholes
                    elif latest_id != last_processed_id:
                        last_processed_id = latest_id
            else:
                print(f"[!] Backend pothole status request failed ({response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"[!] Backend request error: {e}")
            
        # 2. Poll backend for latest fog status
        try:
            fog_response = requests.get(fog_status_url, timeout=2)
            if fog_response.status_code == 200:
                fog_payload = fog_response.json()
                fog_items = fog_payload.get("items", [])
                
                if fog_items:
                    latest_fog = fog_items[0]
                    fog_req_id = latest_fog.get("request_id")
                    
                    if last_processed_fog_request_id is None:
                        last_processed_fog_request_id = fog_req_id
                        print(f"[*] Initialized fog tracking: latest_request_id={fog_req_id}")
                    
                    elif fog_req_id != last_processed_fog_request_id:
                        last_processed_fog_request_id = fog_req_id
                        
                        fog_level = str(latest_fog.get("fog_level", "none")).upper()
                        risk_score = float(latest_fog.get("risk_score", 0.0))
                        source_id = latest_fog.get("source_id", "unknown_fog_source")
                        coords = latest_fog.get("coordinates") or {}
                        lat = float(coords.get("lat") or 0.0)
                        lng = float(coords.get("lng") or 0.0)
                        
                        warning_levels = ["MEDIUM", "HIGH", "CRITICAL"]
                        
                        # Determine if we should send a FOG alert
                        should_alert = False
                        msg = None
                        
                        if fog_level in warning_levels or risk_score > 0.4:
                            # Alert if fog level changed or if it has been > 10 seconds since the last alert to keep it alive
                            if fog_level != last_sent_fog_level or (current_time - last_sent_fog_time > 10.0):
                                should_alert = True
                                msg = f"FOG:{fog_level},{lat:.6f},{lng:.6f},{int(risk_score * 100)},{source_id}\n"
                                last_sent_fog_level = fog_level
                                last_sent_fog_time = current_time
                                print(f"\n[EVENT] Fog alert active! Level={fog_level} Risk={risk_score:.2f}")
                        else:
                            # Fog is low/none. If we were previously alerting, send a FOG:none clear message once
                            if last_sent_fog_level is not None and last_sent_fog_level != "NONE":
                                should_alert = True
                                msg = f"FOG:NONE,{lat:.6f},{lng:.6f},0,{source_id}\n"
                                last_sent_fog_level = "NONE"
                                last_sent_fog_time = current_time
                                print(f"\n[EVENT] Fog cleared. Level={fog_level}")
                        
                        if should_alert and msg:
                            if not open_connections:
                                print(f"[!] No ESP32 COM ports connected. Output: {msg.strip()}")
                            else:
                                for port, ser in open_connections.items():
                                    try:
                                        ser.write(msg.encode("utf-8"))
                                        print(f"[*] Sent to {port} -> {msg.strip()}")
                                    except Exception as e:
                                        print(f"[!] Failed to write to {port}: {e}")
            else:
                print(f"[!] Backend fog status request failed ({fog_response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"[!] Backend fog request error: {e}")
            
        time.sleep(args.interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nRelay daemon stopped.")
        sys.exit(0)
