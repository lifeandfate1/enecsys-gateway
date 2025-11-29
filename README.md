Integration# Enecsys Gateway Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A local-only Home Assistant integration that acts as a server for the **Enecsys Gen 1 Gateway**. It listens for incoming data and automatically creates sensors for your solar inverters.

## 📥 Installation (HACS)

1.  Open **HACS** > **Integrations**.
2.  Click the menu (3 dots) > **Custom repositories**.
3.  Add the URL: `https://github.com/lifeandfate1/enecsys-gateway`
4.  Category: **Integration**.
5.  Click **Add** then **Download**.
6.  Restart Home Assistant.

## ⚙️ Configuration

1.  Add the following line to your `configuration.yaml` file:

```yaml
enecsys_gateway:
```

2.  Restart Home Assistant again.

## 🔌 Hardware Setup

1.  Log into your **Enecsys Gateway** web interface (usually `admin`/`password`).
2.  Go to **Connection Settings** (or Remote Server).
3.  Set the **Server URL** to your Home Assistant IP address.
4.  Set the **Port** to `5040`.
5.  Save and Reboot.

Sensors (e.g., `sensor.enecsys_12345_power`) will appear automatically as soon as the Gateway sends data.