import asyncio
import logging
import base64
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

DOMAIN = "enecsys_gateway"
PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)

KEEP_ALIVE_RESPONSE = b"0E0000000000cgAD83\r"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
                if not data: break
                message = data.decode('utf-8', errors='ignore').strip()
                for line in message.split('\r'):
                    if "WS=" in line:
                        process_data(hass, line)
        except Exception as e:
            _LOGGER.error("Connection error: %s", e)
        finally:
            writer.close()

    def process_data(hass, line):
        try:
            clean_payload = line.split("WS=")[1].strip()
            clean_payload = clean_payload.replace('-', '+').replace('_', '/')
            if "=" in clean_payload:
                 clean_payload = clean_payload.split("=")[0]
            
            padding_needed = len(clean_payload) % 4
            if padding_needed:
                clean_payload += "=" * (4 - padding_needed)

            buf = base64.b64decode(clean_payload)
            
            # Diagnostic: Log buffer length
            if len(buf) < 32:
                _LOGGER.debug("Buffer too short: %s", len(buf))
                return

            # --- ID EXTRACTION ---
            # Reversing ID based on your debug.htm confirmation
            device_id = buf[0:4][::-1].hex().upper()

            # --- DIAGNOSTIC DECODING ---
            # We are trying Bytes 24/25 for Power
            dc_power = buf[24] + (buf[25] << 8)
            
            # We are trying Bytes 30/31 for Volts (Your logs suggest 28/29 was wrong)
            # In your log: ... 32 32 00 EE ... 
            # 00 EE (Little Endian) = 238 Volts. This looks correct.
            ac_volts = buf[30] + (buf[31] << 8)
            
            # Temperature
            temp_c = 0
            if len(buf) > 37:
                temp_c = buf[37]

            payload = {
                "device_id": device_id,
                "dc_power": dc_power,
                "efficiency": 0, # Ignored for now
                "ac_voltage": ac_volts,
                "temperature": temp_c
            }
            
            # FORCE LOGGING: Print the values so we can see what's happening
            _LOGGER.warning("INVERTER %s -> Power: %s W | Volts: %s V | Temp: %s C", device_id, dc_power, ac_volts, temp_c)
            
            # SEND UPDATE: No safety filter. Just send it.
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
        except Exception as e:
            _LOGGER.error("Decode fail: %s", e)

    try:
        server = await asyncio.start_server(handle_connection, '0.0.0.0', port)
        _LOGGER.info("Enecsys Server listening on port %s", port)
        hass.data[DOMAIN][entry.entry_id] = server
        asyncio.create_task(server.serve_forever())
    except OSError as err:
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
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)