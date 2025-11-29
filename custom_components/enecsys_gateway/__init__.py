import asyncio
import logging
import base64
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_send

DOMAIN = "enecsys_gateway"
PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enecsys from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get port from options (if set) or initial data
    port = entry.options.get("port", entry.data.get("port", 5040))

    # --- THE TCP SERVER LOGIC ---
    async def handle_connection(reader, writer):
        addr = writer.get_extra_info('peername')
        _LOGGER.debug(f"New connection from {addr}")
        try:
            while True:
                data = await reader.read(1024)
                if not data: break
                
                message = data.decode('utf-8', errors='ignore').strip()
                for line in message.split('\r'):
                    if line.startswith("WS="):
                        process_data(hass, line)
        except Exception as e:
            _LOGGER.error(f"Connection error: {e}")
        finally:
            writer.close()

    def process_data(hass, data_str):
        try:
            parts = data_str.split("=")
            if len(parts) < 2: return
            b64_payload = parts[1]
            device_id = parts[2] if len(parts) > 2 else "Unknown"
            
            buf = base64.b64decode(b64_payload)
            
            # Decode Logic (Gen 1)
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
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
        except Exception as e:
            _LOGGER.error(f"Decode error: {e}")

    # Start Server
    try:
        server = await asyncio.start_server(handle_connection, '0.0.0.0', port)
        _LOGGER.info(f"Enecsys Server listening on port {port}")
        
        # Store server in hass.data to retrieve it later for unloading
        hass.data[DOMAIN][entry.entry_id] = server
        
        # Start serving in background
        asyncio.create_task(server.serve_forever())

    except OSError as err:
        _LOGGER.error(f"Failed to start server on port {port}: {err}")
        return False

    # Load Sensors
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Reload when options change (e.g. port change)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # 1. Stop the TCP Server
    if entry.entry_id in hass.data[DOMAIN]:
        server = hass.data[DOMAIN][entry.entry_id]
        server.close()
        await server.wait_closed()
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Enecsys Server stopped")

    # 2. Unload Sensors
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)