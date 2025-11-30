import logging
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfTemperature

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors from a config entry."""
    known_devices = set()
    
    # 1. Create the TOTAL System Power Sensor immediately
    total_sensor = EnecsysTotalSensor()
    async_add_entities([total_sensor])

    @callback
    def handle_update(data):
        device_id = data["device_id"]
        
        # 2. Update the Total Sensor with the new data
        total_sensor.update_inverter_power(device_id, data["dc_power"])

        # 3. Create individual sensors if new
        if device_id not in known_devices:
            _LOGGER.info("New Inverter Detected: %s", device_id)
            known_devices.add(device_id)
            new_sensors = [
                EnecsysSensor(device_id, "Power", UnitOfPower.WATT, SensorDeviceClass.POWER, "dc_power"),
                EnecsysSensor(device_id, "Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, "ac_voltage"),
                EnecsysSensor(device_id, "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, "temperature"),
            ]
            async_add_entities(new_sensors)

    async_dispatcher_connect(hass, f"{DOMAIN}_update", handle_update)

class EnecsysTotalSensor(SensorEntity):
    """Aggregates all inverters into one total power reading."""
    
    def __init__(self):
        self._attr_name = "Enecsys Total System Power"
        self._attr_unique_id = "enecsys_total_system_power"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._inverter_powers = {} # Store last known power of each inverter
        self._attr_native_value = 0
        self._attr_available = True

    def update_inverter_power(self, device_id, power):
        # Update the specific inverter's value in our cache
        self._inverter_powers[device_id] = power
        # Recalculate total
        self._attr_native_value = sum(self._inverter_powers.values())
        # Publish update
        self.async_write_ha_state()

class EnecsysSensor(SensorEntity):
    """Representation of an individual Enecsys Sensor."""

    def __init__(self, device_id, name_suffix, unit, device_class, data_key):
        self._device_id = device_id
        self._attr_name = f"Enecsys {device_id} {name_suffix}"
        self._attr_unique_id = f"enecsys_{device_id}_{data_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._data_key = data_key
        self._attr_native_value = None
        self._attr_available = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information to group entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Inverter {self._device_id}",
            manufacturer="Enecsys",
            model="Micro Inverter Gen 1",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update", self._update_state
            )
        )

    @callback
    def _update_state(self, data):
        if data["device_id"] != self._device_id:
            return
        new_value = data.get(self._data_key)
        if new_value is not None:
            self._attr_native_value = new_value
            self.async_write_ha_state()