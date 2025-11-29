import asyncio
import logging
import base64
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)
PORT = 5040

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Enecsys Gateway component."""
    hass.data[DOMAIN] = {}

    async def handle_connection(reader, writer):
        """Handle incoming TCP connections from the Gateway."""
        addr = writer.get_extra_info('peername')
        _LOGGER.debug(f"New connection from {addr}")

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                message = data.decode('utf-8', errors='ignore').strip()
                # Process each line (Gateway sometimes sends multiples)
                for line in message.split('\r'):
                    if line.startswith("WS="):
                        process_data(hass, line)
                        
        except Exception as e:
            _LOGGER.error(f"Connection error: {e}")
        finally:
            writer.close()

    def process_data(hass, data_str):
        """Decode the Enecsys string and dispatch update to sensors."""
        try:
            parts = data_str.split("=")
            if len(parts) < 2: return

            b64_payload = parts[1]
            # Device ID is usually at the end, or we parse it from the payload
            device_id = parts[2] if len(parts) > 2 else "Unknown"
            
            # Base64 Decode
            buf = base64.b64decode(b64_payload)
            
            # --- Binary Map (Gen 1 Standard) ---
            # Adjust offsets here if your specific inverter differs
            dc_power = (buf[25] << 8) | buf[26]
            efficiency = ((buf[27] << 8) | buf[28]) * 0.001
            ac_volts = (buf[31] << 8) | buf[32]
            temp_c = buf[37]

            payload = {
                "device_id": device_id,
                "dc_power": dc_power,
                "efficiency": efficiency,
                "ac_voltage": ac_volts,
                "temperature": temp_c
            }
            
            # Send data to sensors
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
            # If this is a new device, trigger platform setup (simplified for this custom component)
            # For this MVP, we assume sensors are created dynamically or via config. 
            # To keep it simple: We just log it for now, sensors will pick it up if they exist.
            _LOGGER.debug(f"Processed data for {device_id}: {payload}")

        except Exception as e:
            _LOGGER.error(f"Decode error: {e} | Raw: {data_str}")

    # Start the TCP Server
    server = await asyncio.start_server(handle_connection, '0.0.0.0', PORT)
    hass.data[DOMAIN]['server'] = server
    
    # Start the Server in the background
    asyncio.create_task(server.serve_forever())
    _LOGGER.info(f"Enecsys TCP Server listening on port {PORT}")

    # Load the sensor platform
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))

    # Cleanup on shutdown
    async def cleanup(event):
        server.close()
        await server.wait_closed()
        _LOGGER.info("Enecsys TCP Server stopped")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    return True