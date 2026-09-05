"""Home Assistant MQTT discovery on top of MqttOutput.

Publishes one `homeassistant/sensor/<device>/<field>/config` per numeric field (once per process),
a binary_sensor "alarm" (any alarm active), a text sensor "alarms" (codes, with the full alarm list
and vendor extras as attributes) and a "status" sensor.  Entity ids are deterministic so the
generated Lovelace dashboard (homeassistant/build_dashboard.py) can reference them:

    sensor.<device_slug>_<field>          e.g. sensor.huawei_sun2000_pv_w
    binary_sensor.<device_slug>_alarm
    sensor.<device_slug>_alarms / _status

options: same as mqtt + discovery_prefix (homeassistant)
"""
from __future__ import annotations

import re
from typing import Any

from ..schema import Reading
from .mqtt import MqttOutput, topic_safe

FIELD_META: dict[str, tuple[str, str | None, str | None, str]] = {
    # field: (unit, device_class, state_class, friendly name)
    "pv_w": ("W", "power", "measurement", "PV power"), "ac_w": ("W", "power", "measurement", "AC power"),
    "grid_w": ("W", "power", "measurement", "Grid power"), "load_w": ("W", "power", "measurement", "Load power"),
    "batt_w": ("W", "power", "measurement", "Battery power"), "reactive_var": ("var", "reactive_power", "measurement", "Reactive power"),
    "soc": ("%", "battery", "measurement", "Battery SOC"), "soh": ("%", None, "measurement", "Battery SOH"),
    "batt_v": ("V", "voltage", "measurement", "Battery voltage"), "batt_a": ("A", "current", "measurement", "Battery current"),
    "batt_temp_c": ("°C", "temperature", "measurement", "Battery temperature"),
    "energy_day_kwh": ("kWh", "energy", "total_increasing", "Energy today"),
    "energy_total_kwh": ("kWh", "energy", "total_increasing", "Energy total"),
    "grid_import_day_kwh": ("kWh", "energy", "total_increasing", "Grid import today"),
    "grid_export_day_kwh": ("kWh", "energy", "total_increasing", "Grid export today"),
    "batt_charge_day_kwh": ("kWh", "energy", "total_increasing", "Battery charge today"),
    "batt_discharge_day_kwh": ("kWh", "energy", "total_increasing", "Battery discharge today"),
    "load_day_kwh": ("kWh", "energy", "total_increasing", "Load today"),
    "grid_v": ("V", "voltage", "measurement", "Grid voltage"), "grid_hz": ("Hz", "frequency", "measurement", "Grid frequency"),
    "temp_c": ("°C", "temperature", "measurement", "Inverter temperature"),
}


def ha_slug(device_id: str) -> str:
    """Home Assistant style slug (what slugify() does to the device name)."""
    s = re.sub(r"[^a-z0-9]+", "_", device_id.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def entity_id(device_id: str, field: str, domain: str = "sensor") -> str:
    return f"{domain}.{ha_slug(device_id)}_{field}"


def friendly_name(field: str) -> str:
    if field in FIELD_META:
        return FIELD_META[field][3]
    m = re.fullmatch(r"(pv\d+)_(v|a|w)", field)
    if m:
        return f"{m.group(1).upper()} {dict(v='voltage', a='current', w='power')[m.group(2)]}"
    return field.replace("_", " ")


def discovery_payload(reading: Reading, field: str, state_topic: str, avail_topic: str, unique_prefix: str) -> dict[str, Any]:
    unit, dev_class, state_class, _ = FIELD_META.get(field, (None, None, "measurement", ""))
    if field.startswith("pv") and field not in FIELD_META:
        unit = {"v": "V", "a": "A", "w": "W"}.get(field.rsplit("_", 1)[-1])
        dev_class = {"V": "voltage", "A": "current", "W": "power"}.get(unit or "")
    slug = ha_slug(reading.device_id)
    payload: dict[str, Any] = {
        "name": friendly_name(field),
        "has_entity_name": True,
        "object_id": f"{slug}_{field}",
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


def diagnostic_payloads(reading: Reading, state_topic: str, avail_topic: str, unique_prefix: str) -> dict[str, dict[str, Any]]:
    """binary_sensor alarm, sensor alarms (text + attributes), sensor status  ->  {discovery_subpath: payload}"""
    slug = ha_slug(reading.device_id)
    device = {"identifiers": [unique_prefix], "name": reading.device_id, "manufacturer": reading.brand}
    common = {"has_entity_name": True, "state_topic": state_topic, "availability_topic": avail_topic, "device": device}
    return {
        f"binary_sensor/{unique_prefix}/alarm": {
            **common, "name": "Alarm", "object_id": f"{slug}_alarm", "unique_id": f"{unique_prefix}_alarm",
            "device_class": "problem",
            "value_template": "{{ 'ON' if (value_json.alarms | selectattr('active') | list | length) > 0 else 'OFF' }}",
        },
        f"sensor/{unique_prefix}/alarms": {
            **common, "name": "Alarms", "object_id": f"{slug}_alarms", "unique_id": f"{unique_prefix}_alarms",
            "icon": "mdi:alert-circle-outline",
            "value_template": "{{ (value_json.alarms | selectattr('active') | map(attribute='code') | list | join(', ')) or 'OK' }}",
            "json_attributes_topic": state_topic,
            "json_attributes_template": "{{ {'alarms': value_json.alarms, 'extra': value_json.extra, 'online': value_json.online, 'ts': value_json.ts} | tojson }}",
        },
        f"sensor/{unique_prefix}/status": {
            **common, "name": "Status", "object_id": f"{slug}_status", "unique_id": f"{unique_prefix}_status",
            "icon": "mdi:solar-power-variant", "value_template": "{{ value_json.status }}",
        },
    }


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
        for f in reading.numeric_fields():
            if f in seen:
                continue
            seen.add(f)
            self.publish(f"{self.discovery_prefix}/sensor/{uid}/{f}/config",
                         discovery_payload(reading, f, f"{base}/state", f"{base}/availability", uid))
        if "_diag" not in seen:
            seen.add("_diag")
            for sub, payload in diagnostic_payloads(reading, f"{base}/state", f"{base}/availability", uid).items():
                self.publish(f"{self.discovery_prefix}/{sub}/config", payload)
        await super().write(reading)
