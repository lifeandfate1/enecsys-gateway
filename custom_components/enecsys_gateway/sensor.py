import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfTemperature

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors from a config entry."""
    known_devices = set()

    @callback
    def handle_update(data):
        device_id = data["device_id"]
        if device_id not in known_devices:
            _LOGGER.info(f"New Enecsys Inverter found: {device_id}")
            known_devices.add(device_id)
            new_sensors = [
                EnecsysSensor(device_id, "Power", UnitOfPower.WATT, SensorDeviceClass.POWER, "dc_power"),
                EnecsysSensor(device_id, "Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, "ac_voltage"),
                EnecsysSensor(device_id, "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, "temperature"),
            ]
            async_add_entities(new_sensors)

    # Listen for updates
    async_dispatcher_connect(hass, f"{DOMAIN}_update", handle_update)