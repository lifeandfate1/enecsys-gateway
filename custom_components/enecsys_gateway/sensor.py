import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfTemperature

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Enecsys sensors."""
    # We need a way to discover devices. 
    # For this simple version, we will create sensors automatically when data arrives.
    # To do this cleanly, we use a listener that adds entities dynamically.
    
    known_devices = set()

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

    # Listen for updates from __init__.py
    async_dispatcher_connect(hass, f"{DOMAIN}_update", handle_update)
    return True

class EnecsysSensor(Entity):
    def __init__(self, device_id, name_suffix, unit, device_class, data_key):
        self._device_id = device_id
        self._attr_name = f"Enecsys {device_id} {name_suffix}"
        self._attr_unique_id = f"enecsys_{device_id}_{data_key}"
        self._unit = unit
        self._device_class = device_class
        self._data_key = data_key
        self._state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update", self._update_state
            )
        )

    def _update_state(self, data):
        """Update the sensor state if the data is for this device."""
        if data["device_id"] != self._device_id:
            return
            
        new_value = data.get(self._data_key)
        if new_value is not None:
            self._state = new_value
            self.async_write_ha_state()

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class
        
    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT