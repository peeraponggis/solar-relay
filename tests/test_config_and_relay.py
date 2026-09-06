import json

import pytest

from solar_relay.adapters.base import BaseAdapter
from solar_relay.config import RelayConfig, expand_env
from solar_relay.outputs.base import BaseOutput
from solar_relay.outputs.homeassistant import discovery_payload
from solar_relay.outputs.pvoutput import PVOutputOutput
from solar_relay.registry import ADAPTERS, OUTPUTS, get_adapter_class, get_output_class
from solar_relay.scheduler import Relay
from solar_relay.schema import Reading


def test_expand_env(monkeypatch):
    monkeypatch.setenv("SR_HOST", "10.0.0.5")
    assert expand_env({"a": "${SR_HOST}", "b": "${SR_MISSING:8899}", "c": ["${SR_HOST}:1"]}) == \
        {"a": "10.0.0.5", "b": "8899", "c": ["10.0.0.5:1"]}
    with pytest.raises(KeyError):
        expand_env("${SR_NOPE}")


def test_config_rejects_duplicate_ids():
    raw = {"devices": [{"id": "a", "adapter": "modbus"}, {"id": "a", "adapter": "sunspec"}]}
    with pytest.raises(ValueError):
        RelayConfig.from_dict(raw)


def test_example_config_parses(tmp_path, monkeypatch):
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "config.example.yaml"
    for var in ("SIGEN_MQTT_HOST", "SIGEN_MQTT_USER", "SIGEN_MQTT_PASS", "SIGEN_TOPIC_TELEMETRY", "SIGEN_TOPIC_SYSTEM",
                "SIGEN_TOPIC_ALARM", "HUAWEI_NB_USER", "HUAWEI_NB_PASS", "SOLIS_KEY_ID", "SOLIS_KEY_SECRET",
                "SOLARMAN_APP_ID", "SOLARMAN_APP_SECRET", "SOLARMAN_EMAIL", "SOLARMAN_PASS", "SEMS_USER", "SEMS_PASS",
                "SEMS_PS_ID", "GROWATT_USER", "GROWATT_PASS", "SG_APP_KEY", "SG_ACCESS_KEY", "SG_USER", "SG_PASS",
                "SE_API_KEY", "SE_SITE_ID", "FRONIUS_KEY_ID", "FRONIUS_KEY_VALUE", "FRONIUS_SYSTEM_ID", "SMA_USER",
                "SMA_PASS", "PVOUTPUT_KEY", "INFLUX_TOKEN", "SIGEN_USER", "SIGEN_PASS"):
        monkeypatch.setenv(var, "x")
    cfg = RelayConfig.load(src)
    assert len(cfg.devices) > 20
    for d in cfg.devices:
        assert d.adapter in ADAPTERS, d.adapter
    for o in cfg.outputs:
        assert o.type in OUTPUTS


def test_registry_imports_every_pure_python_entry():
    # adapters whose modules import without optional deps
    for key in ("modbus", "solarman", "sunspec", "sigen_openapi", "fronius_solarapi", "goodwe",
                "cloud:huawei", "cloud:soliscloud", "cloud:solarman", "cloud:goodwe", "cloud:growatt",
                "cloud:sungrow", "cloud:solaredge", "cloud:fronius", "cloud:sma"):
        assert get_adapter_class(key)
    for key in ("console", "mqtt", "homeassistant", "influxdb", "pvoutput"):
        assert get_output_class(key)


class FakeAdapter(BaseAdapter):
    name = "fake"
    calls = 0

    async def read(self):
        FakeAdapter.calls += 1
        if self.options.get("fail"):
            raise OSError("boom")
        return [self.new_reading(pv_w=100, grid_w=-40)]


class CollectOutput(BaseOutput):
    name = "collect"
    seen: list = []

    async def write(self, reading):
        CollectOutput.seen.append(reading)


async def test_relay_once_end_to_end(monkeypatch):
    import solar_relay.registry as reg
    monkeypatch.setitem(reg.ADAPTERS, "fake", "tests.test_config_and_relay:FakeAdapter")
    monkeypatch.setitem(reg.OUTPUTS, "collect", "tests.test_config_and_relay:CollectOutput")
    cfg = RelayConfig.from_dict({"devices": [{"id": "d1", "adapter": "fake", "brand": "test"},
                                             {"id": "d2", "adapter": "fake", "options": {"fail": True}}],
                                 "outputs": [{"type": "collect"}]})
    CollectOutput.seen.clear()
    await Relay(cfg).build().run(once=True)
    assert [r.device_id for r in CollectOutput.seen] == ["d1"]
    assert CollectOutput.seen[0].load_w == 60          # derived from balance


def test_ha_discovery_payload():
    r = Reading(device_id="huawei-1", brand="huawei", source="modbus", pv_w=1)
    p = discovery_payload(r, "pv_w", "solar/huawei-1/state", "solar/huawei-1/availability", "uid")
    assert p["device_class"] == "power" and p["unit_of_measurement"] == "W"
    assert p["value_template"] == "{{ value_json.pv_w }}"
    json.dumps(p)


def test_pvoutput_payload():
    r = Reading(device_id="x", brand="b", source="s", energy_day_kwh=12.345, pv_w=2500.7, load_w=800, temp_c=41.23)
    p = PVOutputOutput.payload(r)
    assert p["v1"] == "12345" and p["v2"] == "2500" and p["v4"] == "800" and p["v5"] == "41.2"
