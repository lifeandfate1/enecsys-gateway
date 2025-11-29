Enecsys Gateway Listener (Home Assistant Add-on)
A local-only "Resurrection" service for the defunct Enecsys Solar Inverter Gateway (Gen 1).

This Home Assistant Add-on emulates the original (now dead) Enecsys cloud server. It listens for incoming data connections from your physical Gateway, decodes the proprietary base64/binary protocol, and publishes the solar production data directly to your Home Assistant MQTT broker.

🌟 Features
Zero Cloud Dependency: Runs entirely on your local Home Assistant OS.

Automatic Discovery: Connects to the internal Home Assistant MQTT broker automatically.

Real-time Data: Decodes AC Volts, DC Power, Temperature, and Efficiency.

Hardware Support: Specifically designed for the Enecsys Gen 1 Gateway (LCD version).

🛠 Prerequisites
Home Assistant OS (HAOS) or Supervised installation.

MQTT Broker: You must have an MQTT broker running (e.g., the official Mosquitto broker Add-on).

Enecsys Gateway Gen 1: You must have admin access to the web interface of your physical Enecsys gateway.

📥 Installation
1. Add the Repository
Navigate to your Home Assistant instance.

Go to Settings > Add-ons > Add-on Store.

Click the three dots in the top-right corner and select Repositories.

Add the URL of this GitHub repository: ```text https://www.google.com/search?q=https://github.com/YOUR_GITHUB_USERNAME/enecsys-gateway ```

Click Add.

2. Install the Add-on
Refresh the Add-on Store page.

Scroll to the bottom; you should see Enecsys Gateway Listener.

Click on it and select Install.

Once installed, toggle Start on Boot and click Start.

Check the Log tab to confirm it says Connected to MQTT Broker.

⚙️ Configuration (The Physical Gateway)
You must redirect your physical Enecsys Gateway to talk to Home Assistant instead of the dead Enecsys servers.

Find the IP address of your Enecsys Gateway (look at the LCD screen on the device).

Open a web browser and go to http://<GATEWAY_IP>.

Log in (Default User: admin, Password: password).

Navigate to Remote Server Settings (or similar connection settings).

Change the Server URL/IP to the IP address of your Home Assistant instance.

Ensure the Port is set to 5040.

Save and Reboot the Gateway.

📊 Data & Sensors
Once the Gateway reboots and connects, data will appear in your MQTT broker under the following topic structure:

enecsys/<DEVICE_ID>/status

JSON Payload Example:
```json { "device_id": "100123456", "dc_power_w": 245, "efficiency": 0.94, "ac_voltage": 238, "temperature_c": 34 } ```

Adding to Home Assistant (configuration.yaml)
To see these as sensors, add this to your configuration.yaml (replace 100123456 with your actual inverter serial number found in the MQTT logs):

```yaml mqtt: sensor: - name: "Solar Panel 1 Power" state_topic: "enecsys/100123456/status" unit_of_measurement: "W" value_template: "{{ value_json.dc_power_w }}" device_class: power

- name: "Solar Panel 1 Temp"
  state_topic: "enecsys/100123456/status"
  unit_of_measurement: "°C"
  value_template: "{{ value_json.temperature_c }}"
  device_class: temperature
```

🐛 Troubleshooting
"I see raw data in the logs, but the numbers (Watts/Volts) are crazy." The binary format of Enecsys inverters varies slightly by firmware generation. This Add-on uses the standard "Gen 1" bit-mapping.

Fix: Check the Add-on logs. It will print the decoded values. If they look wrong (e.g., 50,000 Volts), please open an Issue on this repo with a copy of the Raw Data String from the logs. We can adjust the byte offsets to match your specific inverter firmware.

"The Gateway won't connect."

Ensure port 5040 is not blocked by a firewall.

Verify your Home Assistant IP address hasn't changed.

Ensure the "Server URL" in the Gateway does not include http://. It should just be the IP address (e.g., 192.168.1.10).

⚖️ License
MIT License. Use at your own risk. This project is not affiliated with Enecsys.
