"""Adapter / output registries. Import is lazy so optional dependencies
(pymodbus, pysunspec2, pysolarmanv5, goodwe, influxdb-client, paho-mqtt ...)
are only required for the adapters you actually configure."""
from __future__ import annotations

import importlib
from typing import Any

# key -> "module:Class"
ADAPTERS: dict[str, str] = {
    # ---- local, multi-brand ----
    "sunspec":          "solar_relay.adapters.sunspec:SunSpecAdapter",          # SolarEdge, Fronius, SMA, Delta, SolaX, GoodWe, Solis (SunSpec models)
    "modbus":           "solar_relay.adapters.modbus_generic:ModbusMapAdapter",  # huawei, solis, sungrow, solax, deye_1p, deye_3p, sofar, sigen_local
    "solarman":         "solar_relay.adapters.solarman:SolarmanAdapter",         # Deye / Sofar / Solis DLS-W, DLS-L via Solarman V5 logger (tcp/8899)
    "goodwe":           "solar_relay.adapters.goodwe_local:GoodWeLocalAdapter",  # GoodWe UDP 8899 (goodwe lib)
    "fronius_solarapi": "solar_relay.adapters.fronius_solarapi:FroniusSolarApiAdapter",  # Fronius local JSON API
    # ---- Sigenergy official OpenAPI (push over MQTT) ----
    "sigen_openapi":    "solar_relay.adapters.sigen_openapi:SigenOpenApiAdapter",
    # ---- vendor clouds (fallback when no local access) ----
    "cloud:huawei":     "solar_relay.adapters.cloud.huawei_northbound:HuaweiNorthboundAdapter",
    "cloud:soliscloud": "solar_relay.adapters.cloud.soliscloud:SolisCloudAdapter",
    "cloud:solarman":   "solar_relay.adapters.cloud.solarman_smart:SolarmanSmartAdapter",   # Deye Cloud / Solarman Smart
    "cloud:goodwe":     "solar_relay.adapters.cloud.goodwe_sems:GoodWeSemsAdapter",
    "cloud:growatt":    "solar_relay.adapters.cloud.growatt:GrowattAdapter",
    "cloud:sungrow":    "solar_relay.adapters.cloud.sungrow_isolarcloud:SungrowISolarCloudAdapter",
    "cloud:solaredge":  "solar_relay.adapters.cloud.solaredge_monitoring:SolarEdgeMonitoringAdapter",
    "cloud:fronius":    "solar_relay.adapters.cloud.fronius_solarweb:FroniusSolarWebAdapter",
    "cloud:sma":        "solar_relay.adapters.cloud.sma_sunnyportal:SmaSunnyPortalAdapter",
}

OUTPUTS: dict[str, str] = {
    "influxdb":      "solar_relay.outputs.influxdb:InfluxDBOutput",
    "mqtt":          "solar_relay.outputs.mqtt:MqttOutput",
    "homeassistant": "solar_relay.outputs.homeassistant:HomeAssistantOutput",
    "pvoutput":      "solar_relay.outputs.pvoutput:PVOutputOutput",
    "console":       "solar_relay.outputs.console:ConsoleOutput",
    "web":           "solar_relay.web.server:WebOutput",          # built-in Thai web UI + JSON API
}


def _load(spec: str) -> Any:
    mod_name, cls_name = spec.split(":")
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


def get_adapter_class(key: str) -> Any:
    if key not in ADAPTERS:
        raise KeyError(f"unknown adapter '{key}'. Known: {', '.join(sorted(ADAPTERS))}")
    return _load(ADAPTERS[key])


def get_output_class(key: str) -> Any:
    if key not in OUTPUTS:
        raise KeyError(f"unknown output '{key}'. Known: {', '.join(sorted(OUTPUTS))}")
    return _load(OUTPUTS[key])
