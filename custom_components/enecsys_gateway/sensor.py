import logging
from datetime import timedelta
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass
)
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfTemperature

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

# Config: How long before we consider an inverter "dead" (night time)
TIMEOUT_THRESHOLD = timedelta(minutes=5)
# Config: How often the Janitor checks for dead inverters
CHECK_INTERVAL = timedelta(seconds=60)

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
        
        # Data structure: { 'device_id': {'power': 50, 'last_seen': datetime object} }
        self._inverter_data = {} 
        self._attr_native_value = 0
        self._attr_available = True

    async def async_added_to_hass(self):
        """Start the 'Janitor' timer when added to HA."""
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._check_stale_data, CHECK_INTERVAL
            )
        )

    def update_inverter_power(self, device_id, power):
        """Update a specific inverter's value and timestamp."""
        self._inverter_data[device_id] = {
            "power": power,
            "last_seen": dt_util.now()
        }
        self._recalculate_total()

    @callback
    def _check_stale_data(self, now):
        """The Janitor: Checks for inverters that stopped reporting."""
        data_changed = False
        limit = now - TIMEOUT_THRESHOLD

        for device_id, data in self._inverter_data.items():
            # If data is old and power is not already 0
            if data["last_seen"] < limit and data["power"] > 0:
                _LOGGER.debug("Inverter %s timed out (Total Sensor). Setting contribution to 0W.", device_id)
                data["power"] = 0
                data_changed = True
        
        if data_changed:
            self._recalculate_total()

    def _recalculate_total(self):
        """Sum up the power values from the data dictionary."""
        total = sum(item["power"] for item in self._inverter_data.values())
        self._attr_native_value = total
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
        self._last_update = dt_util.now()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Inverter {self._device_id}",
            manufacturer="Enecsys",
            model="Micro Inverter Gen 1",
        )

    async def async_added_to_hass(self):
        """Subscribe to updates and start the local Janitor."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update", self._update_state
            )
        )
        # Each sensor watches itself for timeouts
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._check_stale_data, CHECK_INTERVAL
            )
        )

    @callback
    def _update_state(self, data):
        """Handle new data from the gateway."""
        if data["device_id"] != self._device_id:
            return
        
        new_value = data.get(self._data_key)
        if new_value is not None:
            self._attr_native_value = new_value
            self._last_update = dt_util.now() # Reset the timer
            self._attr_available = True # Mark as available
            self.async_write_ha_state()

    @callback
    def _check_stale_data(self, now):
        """Check if this specific sensor has gone stale."""
        # If we are already unavailable or 0, do nothing
        if not self._attr_available and self._attr_native_value is None:
            return

        if now - self._last_update > TIMEOUT_THRESHOLD:
            _LOGGER.debug("Sensor %s timed out. Resetting state.", self.entity_id)
            
            if self.device_class == SensorDeviceClass.POWER:
                # Power sensors go to 0W at night
                if self._attr_native_value != 0:
                    self._attr_native_value = 0
                    self.async_write_ha_state()
            else:
                # Voltage and Temp go to Unavailable
                if self._attr_native_value is not None:
                    self._attr_native_value = None
                    # We could also set self._attr_available = False if you prefer strict unavailability
                    self.async_write_ha_state()
