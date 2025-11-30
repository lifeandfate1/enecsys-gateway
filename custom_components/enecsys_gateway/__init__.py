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
                
                # Split by \r to handle multiple packets
                for line in message.split('\r'):
                    # The Critical Fix: Look for WS= anywhere, not just at start
                    if "WS=" in line:
                        process_data(hass, line)
                    elif "WZ=" in line:
                        # Log Zigbee status just for confirmation
                        _LOGGER.debug("Zigbee Status (WZ) packet received.")

        except Exception as e:
            _LOGGER.error("Connection error: %s", e)
        finally:
            _LOGGER.info("Closing connection from %s", addr)
            writer.close()

    def process_data(hass, line):
        try:
            # Clean up: "GarbageHeaderWS=Payload" -> "Payload"
            # We take the part AFTER 'WS='
            clean_payload = line.split("WS=")[1]
            
            # Sometimes there is junk at the end, or a Device ID. 
            # We assume standard Base64 characters only.
            # If there is an '=' at the end for padding, that's fine.
            # If there is '=DeviceID', we handle that.
            
            if "=" in clean_payload and len(clean_payload.split("=")) > 2:
                 # Standard format: Payload=DeviceID
                 b64_str = clean_payload.split("=")[0]
                 device_id = clean_payload.split("=")[1]
            else:
                 # "Dirty" format: Just Payload. We must extract ID from binary.
                 b64_str = clean_payload
                 device_id = None

            # Base64 Decode
            # We add padding just in case the string was truncated
            b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
            buf = base64.b64decode(b64_str)

            # --- ID EXTRACTION (The Fix) ---
            if not device_id:
                # In Gen 1 binary, the Device ID is often the first 4 bytes
                # We convert it to Hex to make it readable (e.g., 200001...)
                # Adjust this if your IDs look different on the sticker!
                device_id = buf[0:4].hex().upper()

            # --- DECODING LOGIC (Gen 1 Standard) ---
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
            
            _LOGGER.info("SUCCESS: Decoded Inverter %s | Power: %s W", device_id, dc_power)
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
        except Exception as e:
            _LOGGER.error("Decode error: %s | Line: %s", e, line)

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