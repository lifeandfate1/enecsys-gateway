import logging
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.sensor import (
    SensorEntity,  # <--- THIS WAS MISSING
    SensorDeviceClass, 
    SensorStateClass
)
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfTemperature

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors from a config entry."""
    known_devices = set()

    @callback
    def handle_update(data):
        device_id = data["device_id"]
        # Use a composite key so we don't duplicate sensors for the same device
        # (Though device_id should be unique enough)
        if device_id not in known_devices:
            _LOGGER.info("CREATING SENSORS for New Inverter: %s", device_id)
            known_devices.add(device_id)
            new_sensors = [
                EnecsysSensor(device_id, "Power", UnitOfPower.WATT, SensorDeviceClass.POWER, "dc_power"),
                EnecsysSensor(device_id, "Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, "ac_voltage"),
                EnecsysSensor(device_id, "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, "temperature"),
            ]
            async_add_entities(new_sensors)

    # Listen for updates from __init__.py
    async_dispatcher_connect(hass, f"{DOMAIN}_update", handle_update)

class EnecsysSensor(SensorEntity): # <--- CHANGED FROM Entity TO SensorEntity
    """Representation of an Enecsys Sensor."""

    def __init__(self, device_id, name_suffix, unit, device_class, data_key):
        """Initialize the sensor."""
        self._device_id = device_id
        self._attr_name = f"Enecsys {device_id} {name_suffix}"
        self._attr_unique_id = f"enecsys_{device_id}_{data_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._data_key = data_key
        self._attr_native_value = None
        self._attr_available = True

    async def async_added_to_hass(self):
        """Register callbacks when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update", self._update_state
            )
        )

    @callback
    def _update_state(self, data):
        """Update the sensor state if the data is for this device."""
        if data["device_id"] != self._device_id:
            return
            
        new_value = data.get(self._data_key)
        
        if new_value is not None:
            # Modern HA way: update the attribute directly
            self._attr_native_value = new_value
            self.async_write_ha_state()
            
            # Log successful update for the first few times
            if self._data_key == "dc_power":
                _LOGGER.debug("Updated %s to %s", self._attr_unique_id, new_value)