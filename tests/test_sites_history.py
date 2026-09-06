import time
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from solar_relay.config import RelayConfig
from solar_relay.schema import Reading
from solar_relay.web.state import State


def _cfg(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "devices:\n  - {id: hw, adapter: modbus, brand: huawei}\n  - {id: so, adapter: modbus, brand: solis}\n"
        "sites:\n  - {id: a, name: A, customer: C1, devices: [hw]}\n", encoding="utf-8")
    return RelayConfig.load(cfg_file)


def test_site_edit_persists_to_sites_yaml_and_overrides_config(tmp_path):
    cfg = _cfg(tmp_path)
    st = State()
    st.attach(cfg)
    r = st.save_site({"id": "a", "name": "บ้านคุณสมชาย", "customer": "สมชาย", "phone": "081", "devices": ["hw", "so"]})
    assert r["ok"] and r["saved_to"].endswith("sites.yaml")
    st.save_site({"id": "b", "name": "B", "devices": ["so"]})          # device moves to the new site
    data = yaml.safe_load((tmp_path / "sites.yaml").read_text(encoding="utf-8"))
    assert [s["id"] for s in data["sites"]] == ["a", "b"]
    assert data["sites"][0]["customer"] == "สมชาย" and data["sites"][0]["devices"] == ["hw"] and data["sites"][1]["devices"] == ["so"]
    reloaded = RelayConfig.load(tmp_path / "config.yaml")             # sites.yaml wins over config.yaml
    assert reloaded.site_of("so").id == "b" and reloaded.site_of("hw").name == "บ้านคุณสมชาย"
    assert st.remove_site("b") and not st.remove_site("b")
    assert RelayConfig.load(tmp_path / "config.yaml").site_of("so") is None


def test_site_save_requires_id(tmp_path):
    st = State()
    st.attach(_cfg(tmp_path))
    with pytest.raises(ValueError):
        st.save_site({"id": ""})


def test_history_series_buckets_and_sums(tmp_path):
    st = State()
    st.attach(_cfg(tmp_path))
    now = datetime.now(timezone.utc)
    for i in range(10):
        ts = now - timedelta(minutes=10 - i)
        st.update(Reading("hw", "huawei", "modbus", ts=ts, pv_w=1000, load_w=400, grid_w=-600, soc=None, energy_day_kwh=5))
        st.update(Reading("so", "solis", "modbus", ts=ts, pv_w=500, load_w=300, grid_w=-200, batt_w=100, soc=60, energy_day_kwh=2))
    h = st.history_series(["hw", "so"], hours=1, points=60)
    filled = [p for p in h["points"] if p["pv_w"] is not None]
    assert filled and all(p["pv_w"] == 1500 and p["grid_w"] == -800 and p["soc"] == 60 for p in filled)
    assert h["energy_day_kwh"] == 7
    assert st.history_series(["hw"], hours=1, points=30)["points"][-1]["pv_w"] in (1000, None)


def test_offline_reading_does_not_pollute_series(tmp_path):
    st = State()
    st.attach(_cfg(tmp_path))
    st.update(Reading("hw", "huawei", "modbus", online=False))
    assert "hw" not in st.series


def test_web_site_and_history_endpoints(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from solar_relay.web.server import create_app
    st = State()
    st.attach(_cfg(tmp_path))
    st.update(Reading("hw", "huawei", "modbus", pv_w=1200, load_w=300, grid_w=-900, energy_day_kwh=3))
    c = TestClient(create_app(st))
    assert c.post("/api/sites", json={"id": "a", "customer": "ลูกค้าใหม่", "phone": "02"}).json()["site"]["customer"] == "ลูกค้าใหม่"
    assert c.post("/api/sites", json={"id": ""}).status_code == 400
    assert c.get("/api/history?site=a&hours=1").json()["energy_day_kwh"] == 3
    assert c.get("/api/history?site=zzz").status_code == 404
    assert c.get("/api/history?device=hw&hours=1&points=30").json()["points"][-1]["pv_w"] == 1200
    assert c.delete("/api/sites/a").json() == {"ok": True} and c.delete("/api/sites/a").status_code == 404
    time.sleep(0)
