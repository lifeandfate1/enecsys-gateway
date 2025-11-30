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
        
        try:
            writer.write(KEEP_ALIVE_RESPONSE)
            await writer.drain()
        except Exception as e:
            _LOGGER.error("Failed to send Keep-Alive: %s", e)
            return

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                # Decode and clean buffer
                message = data.decode('utf-8', errors='ignore').strip()
                
                for line in message.split('\r'):
                    if "WS=" in line:
                        process_data(hass, line)

        except Exception as e:
            _LOGGER.error("Connection error: %s", e)
        finally:
            _LOGGER.info("Closing connection from %s", addr)
            writer.close()

    def process_data(hass, line):
        try:
            # 1. Extract Payload
            # Format is usually GarbageHeaderWS=Payload
            clean_payload = line.split("WS=")[1].strip()
            
            # 2. Handle "URL Safe" Base64 (The fix for your logs)
            # Your logs showed characters like '-' which standard Base64 hates
            clean_payload = clean_payload.replace('-', '+').replace('_', '/')
            
            # 3. Handle Truncation (Remove explicit Device ID if present)
            if "=" in clean_payload:
                 clean_payload = clean_payload.split("=")[0]

            # 4. Fix Padding (The fix for "Incorrect padding")
            # Base64 length must be divisible by 4. Add '=' until it is.
            padding_needed = len(clean_payload) % 4
            if padding_needed:
                clean_payload += "=" * (4 - padding_needed)

            # 5. Decode
            buf = base64.b64decode(clean_payload)
            
            # 6. Safety Check (The fix for "Index out of range")
            # We need at least 40 bytes to read temperature at index 37
            if len(buf) < 40:
                # This is likely a fragmented packet or Zigbee noise. Skip it.
                return

            # --- ID EXTRACTION ---
            # In Gen 1, ID is usually the first 4 bytes
            device_id = buf[0:4].hex().upper()

            # --- DECODING LOGIC (Gen 1 Standard) ---
            dc_power = (buf[25] << 8) | buf[26]
            efficiency = ((buf[27] << 8) | buf[28]) * 0.001
            ac_volts = (buf[31] << 8) | buf[32]
            temp_c = buf[37]

            # Filter out crazy values (Encryption artifacts)
            if dc_power > 500 or ac_volts > 300:
                return

            payload = {
                "device_id": device_id,
                "dc_power": dc_power,
                "efficiency": efficiency,
                "ac_voltage": ac_volts,
                "temperature": temp_c
            }
            
            _LOGGER.debug("Decoded %s: %s W", device_id, dc_power)
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
        except Exception as e:
            # Log as debug to avoid flooding logs with packet errors
            _LOGGER.debug("Packet decode failed: %s", e)

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