"""The provisioned dashboard must stay in sync with the generator and only query fields the relay writes."""
import importlib.util
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str, path: pathlib.Path):
    # grafana/ and homeassistant/ both have a build_dashboard.py -> load under distinct module names
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build_dashboard = _load("grafana_build_dashboard", ROOT / "grafana" / "build_dashboard.py")

from solar_relay.schema import NUMERIC_FIELDS  # noqa: E402

WRITTEN_FIELDS = set(NUMERIC_FIELDS) | {"online", "status", "alarm_count", "active", "message", "severity"}


def test_committed_json_matches_generator():
    committed = json.loads((ROOT / "grafana/provisioning/dashboards/solar-relay-overview.json").read_text(encoding="utf-8"))
    assert committed == build_dashboard.build(), "run: python grafana/build_dashboard.py"


def test_queries_only_reference_known_fields():
    dash = build_dashboard.build()
    queries = [t["query"] for p in dash["panels"] for t in p["targets"]]
    referenced = set()
    for q in queries:
        referenced |= set(re.findall(r'r\._field == "([a-z_0-9]+)"', q))
        for m in re.findall(r'set: \[([^\]]+)\]', q):
            referenced |= set(re.findall(r'"([a-z_0-9]+)"', m))
    unknown = referenced - WRITTEN_FIELDS
    assert not unknown, unknown


def test_every_panel_has_datasource_uid_and_unique_id():
    dash = build_dashboard.build()
    ids = [p["id"] for p in dash["panels"]]
    assert len(ids) == len(set(ids))
    for p in dash["panels"]:
        assert p["datasource"]["uid"] == "influx-solar"
        for t in p["targets"]:
            assert "${device:regex}" in t["query"] and "${brand:regex}" in t["query"]
