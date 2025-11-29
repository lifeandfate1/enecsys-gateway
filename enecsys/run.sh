#!/usr/bin/with-contenv bashio

echo "Starting Enecsys Gateway Listener..."

# Extract MQTT credentials from Home Assistant Service
export MQTT_HOST=$(bashio::services mqtt "host")
export MQTT_PORT=$(bashio::services mqtt "port")
export MQTT_USER=$(bashio::services mqtt "username")
export MQTT_PASS=$(bashio::services mqtt "password")

# Run the python script
python3 -u /gateway.py
