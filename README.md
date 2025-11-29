# Enecsys Gateway Integration

![Banner](images/banner.png)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.1.0-blue)

A local-only Home Assistant integration that acts as a "resurrection" server for the defunct **Enecsys Gen 1 Gateway**. It listens for incoming data and automatically creates sensors for your solar inverters.

## ℹ️ How it Works

This integration runs a lightweight TCP server inside Home Assistant that emulates the old Enecsys cloud. Your physical gateway sends its data to this server, which decodes the proprietary format and updates Home Assistant sensors in real-time.

![Architecture Diagram](images/diagram.png)

## 📥 Installation

### 1. Install via HACS
1.  Open **HACS** > **Integrations**.
2.  Click the menu (3 dots) > **Custom repositories**.
3.  Add the URL: `https://github.com/lifeandfate1/enecsys-gateway`
4.  Category: **Integration**.
5.  Click **Add** then **Download**.
6.  **Restart Home Assistant**.

### 2. Add Integration (UI)
1.  Go to **Settings** > **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for **Enecsys Gateway**.
4.  Enter the listening port (Default: `5040`).
5.  Click **Submit**.

## 🔌 Hardware Setup (Physical Gateway)

You must redirect your physical Enecsys Gateway to talk to your Home Assistant IP address instead of the dead Enecsys servers.

1.  Find your **Home Assistant IP address**.
2.  Log into your **Enecsys Gateway** web interface (default: `admin`/`password`).
3.  Navigate to **Connection Settings** (or Remote Server).
4.  Set the **Server URL** to your Home Assistant IP.
5.  Set the **Port** to `5040` (or whatever you configured in the previous step).
6.  **Save and Reboot** the Gateway.

## 📊 Sensors

Sensors will appear automatically in Home Assistant as soon as the Gateway sends its first packet of data.

* `sensor.enecsys_SERIAL_power` (Watts)
* `sensor.enecsys_SERIAL_efficiency` (%)
* `sensor.enecsys_SERIAL_voltage` (Volts)
* `sensor.enecsys_SERIAL_temperature` (°C)

## 🐛 Troubleshooting

**"Sensors aren't showing up."**
* Check the Home Assistant logs. You should see `New connection from...` when the Gateway tries to connect.
* Ensure your firewall allows traffic on port 5040.
* Ensure the Enecsys Gateway is actually rebooted and pointing to the correct IP.

**"My log says 'Address already in use'."**
* You might have another service (like an old script or another add-on) using port 5040. Change the port in the Integration options and on the Gateway.

---
*This is a community project and is not affiliated with Enecsys.*