import asyncio
import logging
import base64
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

DOMAIN = "enecsys_gateway"
PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)

# The magic string Enecsys Gen 1 Gateways expect to stay connected
KEEP_ALIVE_RESPONSE = b"0E0000000000cgAD83\r"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enecsys from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    port = entry.options.get("port", entry.data.get("port", 5040))

    async def handle_connection(reader, writer):
        addr = writer.get_extra_info('peername')
        _LOGGER.info("New connection from %s", addr)
        
        # Send initial Keep-Alive
        try:
            writer.write(KEEP_ALIVE_RESPONSE)
            await writer.drain()
            _LOGGER.debug("Sent initial Keep-Alive to %s", addr)
        except Exception as e:
            _LOGGER.error("Failed to send Keep-Alive: %s", e)
            return

        try:
            while True:
                # 1. Read data
                data = await reader.read(1024)
                if not data:
                    break
                
                # 2. Process data
                # SPY MODE: Log exactly what we received before processing
                message = data.decode('utf-8', errors='ignore').strip()
                _LOGGER.warning("RAW DATA RECEIVED: %s", message)

                for line in message.split('\r'):
                    if line.startswith("WS"):
                        process_data(hass, line)
                    # Handle Zigbee Status (WZ) just to acknowledge it's working
                    elif line.startswith("WZ"):
                         _LOGGER.info("Zigbee Status packet received (Ignored)")
                    else:
                         _LOGGER.debug("Unknown packet type: %s", line)

        except Exception as e:
            _LOGGER.error("Connection error: %s", e)
        finally:
            _LOGGER.info("Closing connection from %s", addr)
            writer.close()

    def process_data(hass, data_str):
        try:
            parts = data_str.split("=")
            if len(parts) < 2:
                return
            b64_payload = parts[1]
            device_id = parts[2] if len(parts) > 2 else "Unknown"
            
            buf = base64.b64decode(b64_payload)
            
            # --- DECODING LOGIC (Gen 1 Standard) ---
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
            # Log success so we know it worked
            _LOGGER.info("Successfully decoded data for Inverter %s: %s W", device_id, dc_power)
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
        except Exception as e:
            _LOGGER.error("Decode error: %s | Raw: %s", e, data_str)

    # Start Server
    try:
        server = await asyncio.start_server(handle_connection, '0.0.0.0', port)
        _LOGGER.info("Enecsys Server listening on port %s", port)
        
        hass.data[DOMAIN][entry.entry_id] = server
        asyncio.create_task(server.serve_forever())

    except OSError as err:
        _LOGGER.error("Failed to start server on port %s: %s", port, err)
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.entry_id in hass.data[DOMAIN]:
        server = hass.data[DOMAIN][entry.entry_id]
        server.close()
        await server.wait_closed()
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Enecsys Server stopped")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)