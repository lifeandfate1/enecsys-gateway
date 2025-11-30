# Enecsys Gateway Integration

![Banner](images/banner.png)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.1.0-blue)

A local-only Home Assistant integration that acts as a "resurrection" server for the defunct **Enecsys Gen 1 Gateway**. It listens for incoming data, automatically decodes the proprietary format, and creates sensors for your solar inverters.

## 🌟 Features

* **Zero Cloud Dependency:** Runs entirely on your local Home Assistant instance.
* **Automatic Discovery:** Just plug it in; sensors appear as soon as data arrives.
* **Total System Power:** Automatically sums up all your inverters into a single `Total System Power` entity.
* **Detailed Sensors:** Real-time Watts, Volts, and Temperature for every microinverter.

## ℹ️ How it Works

This integration runs a lightweight TCP server inside Home Assistant. Your physical gateway sends its data to this server instead of the dead Enecsys cloud.

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

You must redirect your physical Enecsys Gateway to talk to your Home Assistant IP address.

1.  Find your **Home Assistant IP address**.
2.  Log into your **Enecsys Gateway** web interface (default: `admin`/`password`).
3.  Navigate to **Connection Settings** (or Remote Server).
4.  Set the **Server URL** to your Home Assistant IP.
5.  Set the **Port** to `5040` (or whatever you configured in the previous step).
6.  **Save and Reboot** the Gateway.

---

## ⚡ Energy Dashboard Setup

To use this with the **Home Assistant Energy Dashboard**, you need to convert "Power" (Watts now) into "Energy" (kWh over time).

### Step 1: Create a Helper
1.  Go to **Settings** > **Devices & Services** > **Helpers**.
2.  Click **+ Create Helper** and select **Integration - Riemann sum integral**.
3.  Fill in the details:
    * **Name:** `Solar Lifetime Energy`
    * **Input Sensor:** `sensor.enecsys_total_system_power`
    * **Integration Method:** `Left` (Recommended for solar spikes)
    * **Precision:** `2`
    * **Metric Prefix:** `kilo` (Result will be kWh)
    * **Time unit:** `Hours`
4.  Click **Submit**.

### Step 2: Configure Dashboard
1.  Go to **Settings** > **Dashboards** > **Energy**.
2.  Under **Solar Production**, click **Add Solar Production**.
3.  Select the helper you just created (`sensor.solar_lifetime_energy`).
4.  Click **Save**.

*Note: It will take about 1-2 hours for data to start populating the graph.*

---

## 📊 Available Sensors

* `sensor.enecsys_total_system_power` (Sum of all inverters)
* `sensor.enecsys_SERIAL_power` (Watts)
* `sensor.enecsys_SERIAL_voltage` (Volts)
* `sensor.enecsys_SERIAL_temperature` (°C)

---

## 🐛 Troubleshooting

**"Sensors aren't showing up."**
* Check the Home Assistant logs. You should see `New connection from...` when the Gateway tries to connect.
* Ensure your firewall allows traffic on port 5040.

**"My log says 'Address already in use'."**
* You might have another service (like an old script or another add-on) using port 5040. Change the port in the Integration options and on the Gateway.

---
*This is a community project and is not affiliated with Enecsys.*