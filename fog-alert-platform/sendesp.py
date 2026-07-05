import serial
import time

try:
    print("Opening connection to Transmitter ESP32 on COM5...")
    ser = serial.Serial('COM5', 115200, timeout=1)
    time.sleep(1.5) # Wait for auto-reset

    # Write the protocol message to trigger ESP-NOW send
    alert_msg = "POTHOLE:HIGH,12.924285,77.499673,1,phone_pothole_01\n"
    message = input("Enter message:")
    print(message)
    ser.write(alert_msg.encode('utf-8'))
    
    # Read the serial response from the transmitter for a couple seconds to see status
    print("Reading serial feedback from Tx board (checking delivery status)...")
    start_time = time.time()
    while time.time() - start_time < 3.0:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  [Tx Board] {line}")
                
    ser.close()
    print("Serial port closed. Test complete.")
except Exception as e:
    print(f"Error during serial execution: {e}")