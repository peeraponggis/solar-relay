"""Home Assistant MQTT discovery on top of MqttOutput.

Publishes one `homeassistant/sensor/<device>/<field>/config` per numeric field (once per process),
a binary_sensor for "any alarm active", and uses the MQTT state topic as the sensor source.
options: same as mqtt + discovery_prefix (homeassistant)
"""
from __future__ import annotations

from typing import Any

from ..schema import Reading
from .mqtt import MqttOutput, topic_safe

FIELD_META: dict[str, tuple[str, str | None, str | None]] = {
    # field: (unit, device_class, state_class)
    "pv_w": ("W", "power", "measurement"), "ac_w": ("W", "power", "measurement"),
    "grid_w": ("W", "power", "measurement"), "load_w": ("W", "power", "measurement"),
    "batt_w": ("W", "power", "measurement"), "reactive_var": ("var", "reactive_power", "measurement"),
    "soc": ("%", "battery", "measurement"), "soh": ("%", None, "measurement"),
    "batt_v": ("V", "voltage", "measurement"), "batt_a": ("A", "current", "measurement"),
    "batt_temp_c": ("°C", "temperature", "measurement"),
    "energy_day_kwh": ("kWh", "energy", "total_increasing"), "energy_total_kwh": ("kWh", "energy", "total_increasing"),
    "grid_import_day_kwh": ("kWh", "energy", "total_increasing"), "grid_export_day_kwh": ("kWh", "energy", "total_increasing"),
    "batt_charge_day_kwh": ("kWh", "energy", "total_increasing"), "batt_discharge_day_kwh": ("kWh", "energy", "total_increasing"),
    "load_day_kwh": ("kWh", "energy", "total_increasing"),
    "grid_v": ("V", "voltage", "measurement"), "grid_hz": ("Hz", "frequency", "measurement"),
    "temp_c": ("°C", "temperature", "measurement"),
}


def discovery_payload(reading: Reading, field: str, state_topic: str, avail_topic: str, unique_prefix: str) -> dict[str, Any]:
    unit, dev_class, state_class = FIELD_META.get(field, (None, None, "measurement"))
    if field.startswith("pv") and field not in FIELD_META:
        unit = {"v": "V", "a": "A", "w": "W"}.get(field.rsplit("_", 1)[-1])
        dev_class = {"V": "voltage", "A": "current", "W": "power"}.get(unit or "")
    payload: dict[str, Any] = {
        "name": field.replace("_", " "),
        "unique_id": f"{unique_prefix}_{field}",
        "state_topic": state_topic,
        "value_template": f"{{{{ value_json.{field} }}}}",
        "availability_topic": avail_topic,
        "device": {"identifiers": [unique_prefix], "name": reading.device_id, "manufacturer": reading.brand,
                   "model": str(reading.extra.get("model") or reading.source)},
    }
    if unit:
        payload["unit_of_measurement"] = unit
    if dev_class:
        payload["device_class"] = dev_class
    if state_class:
        payload["state_class"] = state_class
    return payload


class HomeAssistantOutput(MqttOutput):
    name = "homeassistant"

    def __init__(self, discovery_prefix: str = "homeassistant", **options: Any):
        options.setdefault("per_field", False)
        super().__init__(**options)
        self.discovery_prefix = discovery_prefix.strip("/")
        self._announced: dict[str, set[str]] = {}

    async def write(self, reading: Reading) -> None:
        base = self.device_topic(reading)
        uid = f"solar_relay_{topic_safe(reading.device_id)}"
        seen = self._announced.setdefault(reading.device_id, set())
        fields = list(reading.numeric_fields().keys())
        for f in fields:
            if f in seen:
                continue
            seen.add(f)
            self.publish(f"{self.discovery_prefix}/sensor/{uid}/{f}/config",
                         discovery_payload(reading, f, f"{base}/state", f"{base}/availability", uid))
        if "alarm" not in seen:
            seen.add("alarm")
            self.publish(f"{self.discovery_prefix}/binary_sensor/{uid}/alarm/config", {
                "name": "alarm", "unique_id": f"{uid}_alarm", "device_class": "problem",
                "state_topic": f"{base}/state", "availability_topic": f"{base}/availability",
                "value_template": "{{ 'ON' if (value_json.alarms | selectattr('active') | list | length) > 0 else 'OFF' }}",
                "device": {"identifiers": [uid], "name": reading.device_id, "manufacturer": reading.brand},
            })
            self.publish(f"{self.discovery_prefix}/sensor/{uid}/status/config", {
                "name": "status", "unique_id": f"{uid}_status", "state_topic": f"{base}/state",
                "availability_topic": f"{base}/availability", "value_template": "{{ value_json.status }}",
                "device": {"identifiers": [uid], "name": reading.device_id, "manufacturer": reading.brand},
            })
        await super().write(reading)
