import socket
import base64
import struct
import json
import os
import time
import sys
import paho.mqtt.client as mqtt

# --- Configuration ---
# In an Add-on, these come from the Supervisor or standard HA networking
MQTT_HOST = os.getenv('MQTT_HOST', 'core-mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER', '')
MQTT_PASS = os.getenv('MQTT_PASS', '')
LISTEN_PORT = 5040

# --- MQTT Setup ---
client = mqtt.Client()
if MQTT_USER and MQTT_PASS:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

def connect_mqtt():
    while True:
        try:
            print(f"Connecting to MQTT Broker at {MQTT_HOST}...")
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_start()
            print("MQTT Connected.")
            return
        except Exception as e:
            print(f"MQTT Connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

# --- Enecsys Decoding Logic ---
def decode_enecsys(data_str):
    try:
        # Expected Format: WS=...payload...=DeviceID
        clean_str = data_str.strip()
        if not clean_str.startswith("WS"):
            return None
            
        parts = clean_str.split("=")
        if len(parts) < 2: 
            return None

        # Base64 Decode
        b64_payload = parts[1]
        buf = base64.b64decode(b64_payload)
        
        # Device ID (Backup if not in string)
        device_id = parts[2] if len(parts) > 2 else "Unknown"
        
        # --- Binary Map (Gen 1 Standard) ---
        # Adjust these offsets if your specific model differs
        # This maps the Node-RED buffer logic to Python struct
        
        # Data is usually Big Endian
        # 23: DC Current, 25: DC Power, 27: Efficiency, 31: AC Volts, 37: Temp
        
        # struct format 'H' is unsigned short (2 bytes), 'B' is unsigned char (1 byte)
        # We access buffer by index to be safe against varying lengths
        
        dc_power = (buf[25] << 8) | buf[26]
        efficiency = ((buf[27] << 8) | buf[28]) * 0.001
        ac_volts = (buf[31] << 8) | buf[32]
        temp_c = buf[37]

        payload = {
            "device_id": device_id,
            "dc_power_w": dc_power,
            "efficiency": efficiency,
            "ac_voltage": ac_volts,
            "temperature_c": temp_c
        }
        return payload

    except Exception as e:
        print(f"Decode Error: {e} | Raw: {data_str}")
        return None

# --- Main Listener ---
def main():
    connect_mqtt()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow port reuse immediately after crash/restart
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind(('0.0.0.0', LISTEN_PORT))
        sock.listen(5)
        print(f"Enecsys Gateway Listener active on port {LISTEN_PORT}")
    except Exception as e:
        print(f"Failed to bind port {LISTEN_PORT}: {e}")
        sys.exit(1)

    while True:
        try:
            conn, addr = sock.accept()
            with conn:
                # print(f"Connection from {addr}")
                while True:
                    data = conn.recv(1024)
                    if not data: break
                    
                    try:
                        data_str = data.decode('utf-8', errors='ignore')
                        # Handle multiple packets in one stream (split by newline)
                        for line in data_str.split('\r'):
                            if "WS=" in line:
                                result = decode_enecsys(line)
                                if result:
                                    # Publish to HA Discovery friendly topic or raw data
                                    topic = f"enecsys/{result['device_id']}/status"
                                    client.publish(topic, json.dumps(result))
                                    print(f"Published: {result}")
                                else:
                                    # Useful for debugging new inverters
                                    client.publish("enecsys/debug/raw", line)
                    except Exception as e:
                        print(f"Packet processing error: {e}")

        except Exception as e:
            print(f"Socket loop error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
