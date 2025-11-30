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
                if not data:
                    break
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
            # 1. Clean Payload
            clean_payload = line.split("WS=")[1].strip()
            clean_payload = clean_payload.replace('-', '+').replace('_', '/')
            if "=" in clean_payload:
                 clean_payload = clean_payload.split("=")[0]
            
            # 2. Fix Padding
            padding = (4 - len(clean_payload) % 4) % 4
            clean_payload += "=" * padding

            # 3. Decode
            buf = base64.b64decode(clean_payload)
            
            # 4. Length Check (Packet must be at least 33 bytes for these offsets)
            if len(buf) < 33:
                return

            # --- ID EXTRACTION ---
            # Little Endian (Confirmed by your debug.htm)
            device_id = buf[0:4][::-1].hex().upper()

            # --- DECODING LOGIC (Verified for AU Data) ---
            
            # DC Power: Bytes 24-25 (Little Endian)
            dc_power = buf[24] + (buf[25] << 8)
            
            # Efficiency: Bytes 26-27 (Little Endian) -> Scale 0.001
            efficiency = (buf[26] + (buf[27] << 8)) * 0.001
            
            # AC Volts: Bytes 30-31 (Big Endian)
            ac_volts = (buf[30] << 8) + buf[31]
            
            # Temperature: Byte 32 (Single Byte)
            temp_c = buf[32]

            # 5. Sanity Filter (Adjusted for AU)
            if ac_volts < 150 or ac_volts > 300:
                return

            payload = {
                "device_id": device_id,
                "dc_power": dc_power,
                "efficiency": efficiency,
                "ac_voltage": ac_volts,
                "temperature": temp_c
            }
            
            _LOGGER.info("Decoded %s | Power: %sW | Volts: %sV | Temp: %sC", device_id, dc_power, ac_volts, temp_c)
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
        except Exception as e:
            _LOGGER.warning("Packet decode failed: %s", e)

    try:
        server = await asyncio.start_server(handle_connection, '0.0.0.0', port)
        _LOGGER.info("Enecsys Server listening on port %s", port)
        hass.data[DOMAIN][entry.entry_id] = server
        asyncio.create_task(server.serve_forever())
    except OSError:
        # Port likely in use
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