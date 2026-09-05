import importlib.util
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str, path: pathlib.Path):
    # grafana/ and homeassistant/ both have a build_dashboard.py -> load under distinct module names
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hb = _load("ha_build_dashboard", ROOT / "homeassistant" / "build_dashboard.py")

from solar_relay.outputs.homeassistant import diagnostic_payloads, discovery_payload, entity_id, ha_slug  # noqa: E402
from solar_relay.schema import Reading  # noqa: E402

ENTITY_RE = re.compile(r"^(sensor|binary_sensor)\.[a-z0-9_]+$")


def _walk(node, found: set[str]):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "entity" and isinstance(v, str):
                found.add(v)
            else:
                _walk(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found)


def test_slug_and_entity_ids_match_discovery_object_id():
    r = Reading(device_id="Huawei-SUN2000 #1", brand="huawei", source="modbus", pv_w=1)
    assert ha_slug(r.device_id) == "huawei_sun2000_1"
    p = discovery_payload(r, "pv_w", "t/state", "t/avail", "uid")
    assert p["object_id"] == "huawei_sun2000_1_pv_w" and p["has_entity_name"] is True and p["name"] == "PV power"
    assert entity_id(r.device_id, "pv_w") == "sensor.huawei_sun2000_1_pv_w"
    diag = diagnostic_payloads(r, "t/state", "t/avail", "uid")
    assert {v["object_id"] for v in diag.values()} == {"huawei_sun2000_1_alarm", "huawei_sun2000_1_alarms", "huawei_sun2000_1_status"}


def test_dashboard_builds_and_only_references_known_entities():
    devices = ["huawei-sun2000", "solis-s6-hybrid"]
    dash = hb.build(devices)
    text = yaml.safe_dump(dash, allow_unicode=True)
    assert yaml.safe_load(text) == dash
    found: set[str] = set()
    _walk(dash, found)
    slugs = [ha_slug(d) for d in devices]
    for e in found:
        assert ENTITY_RE.match(e), e
        assert any(e.split(".", 1)[1].startswith(s + "_") for s in slugs), e
    assert len(dash["views"]) == 2 + len(devices)
    assert [v["path"] for v in dash["views"][2:]] == slugs


def test_committed_sample_matches_example_config():
    sample = ROOT / "homeassistant" / "solar-relay-dashboard.yaml"
    devices = hb.load_device_ids(ROOT / "config.example.yaml")
    assert yaml.safe_load(sample.read_text(encoding="utf-8")) == hb.build(devices), "run: python homeassistant/build_dashboard.py"
