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
            clean_payload = line.split("WS=")[1].strip()
            
            # 2. Handle URL Safe Base64
            clean_payload = clean_payload.replace('-', '+').replace('_', '/')
            
            # 3. Handle Truncation
            if "=" in clean_payload:
                 clean_payload = clean_payload.split("=")[0]

            # 4. Fix Padding
            padding_needed = len(clean_payload) % 4
            if padding_needed:
                clean_payload += "=" * (4 - padding_needed)

            # 5. Decode
            buf = base64.b64decode(clean_payload)
            
            # 6. Safety Check
            if len(buf) < 30:
                return

            # --- ID EXTRACTION (LITTLE ENDIAN FIX) ---
            # Data: 0F 9D 8F 06 -> ID: 068F9D0F
            # We reverse the first 4 bytes ([::-1]) then convert to Hex
            device_id = buf[0:4][::-1].hex().upper()

            # --- DECODING LOGIC (LITTLE ENDIAN + CORRECT OFFSETS) ---
            # Based on bulldog5046/Enecsys-Zigbee-HA documentation
            
            # DC Power (Watts) - Bytes 24 (LSB) & 25 (MSB)
            dc_power = buf[24] + (buf[25] << 8)
            
            # Efficiency (0.001 scale) - Bytes 26 (LSB) & 27 (MSB)
            efficiency = (buf[26] + (buf[27] << 8)) * 0.001
            
            # AC Volts - Bytes 28 (LSB) & 29 (MSB)
            ac_volts = buf[28] + (buf[29] << 8)
            
            # Temperature (Celsius) - Byte 37 (Optional)
            temp_c = 0
            if len(buf) > 37:
                temp_c = buf[37]

            # 7. Filter Garbage
            # Enecsys gen 1 microinverters max out around 300W-400W. 
            # If we get > 1000, the packet is likely Zigbee noise.
            if dc_power > 1000: 
                return

            payload = {
                "device_id": device_id,
                "dc_power": dc_power,
                "efficiency": efficiency,
                "ac_voltage": ac_volts,
                "temperature": temp_c
            }
            
            _LOGGER.info("Decoded %s | Power: %sW | Volts: %sV", device_id, dc_power, ac_volts)
            async_dispatcher_send(hass, f"{DOMAIN}_update", payload)
            
        except Exception as e:
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