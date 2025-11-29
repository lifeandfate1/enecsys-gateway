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
        _LOGGER.debug("New connection from %s", addr)
        
        # Send initial Keep-Alive to acknowledge connection
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
                message = data.decode('utf-8', errors='ignore').strip()
                for line in message.split('\r'):
                    if line.startswith("WS="):
                        process_data(hass, line)
                        
                        # OPTIONAL: Some gateways like a Keep-Alive after every valid data packet
                        # Uncomment if connection drops frequently:
                        # writer.write(KEEP_ALIVE_RESPONSE)
                        # await writer.drain()

        except Exception as e:
            _LOGGER.error("Connection error: %s", e)
        finally:
            _LOGGER.debug("Closing connection from %s", addr)
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
            # Based on community reverse engineering (Node-RED flow & e2pv)
            # 18 bytes minimum usually expected
            
            # DC Power (Watts) - Bytes 25-26
            dc_power = (buf[25] << 8) | buf[26]
            
            # Efficiency (0.001 scale) - Bytes 27-28
            efficiency = ((buf[27] << 8) | buf[28]) * 0.001
            
            # AC Volts - Bytes 31-32
            ac_volts = (buf[31] << 8) | buf[32]
            
            # Temperature (Celsius) - Byte 37
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
    """Unload a config entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        server = hass.data[DOMAIN][entry.entry_id]
        server.close()
        await server.wait_closed()
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Enecsys Server stopped")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)