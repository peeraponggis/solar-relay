"""solar-relay: central multi-brand PV / hybrid-inverter data relay.

Pipeline:  adapters (local Modbus / SunSpec / Solarman / vendor cloud / Sigen push)
           -> normalized ``Reading`` objects (see :mod:`solar_relay.schema`)
           -> outputs (InfluxDB, MQTT, Home Assistant discovery, PVOutput).
"""

__version__ = "0.1.0"
