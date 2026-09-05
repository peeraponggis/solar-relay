from datetime import datetime, timezone

import pytest

from solar_relay.alarm_catalog import enrich_reading
from solar_relay.config import DeviceConfig, RelayConfig, SiteConfig
from solar_relay.schema import Alarm, Reading
from solar_relay.web.state import State


def _cfg() -> RelayConfig:
    return RelayConfig(
        devices=[DeviceConfig("hw", "modbus", "huawei"), DeviceConfig("so", "modbus", "solis"), DeviceConfig("loose", "modbus", "deye")],
        sites=[SiteConfig("a", "บ้าน A", "คุณเอ", "081", devices=["hw"]), SiteConfig("b", "โรงงาน B", "คุณบี", "02", devices=["so"])],
    )


def _state() -> State:
    st = State()
    st.attach(_cfg())
    r1 = Reading("hw", "huawei", "modbus", pv_w=5000, grid_w=-1500, load_w=3500, energy_day_kwh=10)
    r2 = Reading("so", "solis", "modbus", pv_w=2000, grid_w=300, batt_w=800, soc=60, energy_day_kwh=5,
                 alarms=[Alarm(code="solis.PV ISO-PRO", raised_at=datetime.now(timezone.utc))])
    enrich_reading(r2)
    st.update(r1)
    st.update(r2)
    return st


def test_config_sites_from_site_list_and_device_site_key():
    cfg = RelayConfig.from_dict({
        "devices": [{"id": "d1", "adapter": "modbus"}, {"id": "d2", "adapter": "modbus", "site": "s2"}],
        "sites": [{"id": "s1", "name": "S1", "customer": "C", "devices": ["d1"]}],
    })
    assert [s.id for s in cfg.sites] == ["s1", "s2"]
    assert cfg.site_of("d1").customer == "C" and cfg.site_of("d2").devices == ["d2"] and cfg.site_of("zz") is None


def test_snapshot_totals_sites_and_unassigned():
    snap = _state().snapshot()
    assert snap["totals"]["devices"] == 3 and snap["totals"]["online"] == 2 and snap["totals"]["alarms"] == 1
    assert snap["totals"]["pv_w"] == 7000 and snap["totals"]["grid_w"] == -1200
    ids = [s["id"] for s in snap["sites"]]
    assert ids == ["a", "b", "_unassigned"]
    b = snap["sites"][1]
    assert b["customer"] == "คุณบี" and b["alarms"] == 1 and b["faults"] == 1 and b["soc_avg"] == 60
    loose = snap["sites"][2]["devices"][0]
    assert loose["device_id"] == "loose" and loose["has_data"] is False and loose["online"] is False


def test_alarm_enriched_with_advice_and_site_info():
    a = _state().snapshot()["active_alarms"][0]
    assert a["code"] == "solis.PV ISO-PRO" and a["category"] == "insulation" and "ฉนวน" in a["advice"]
    assert a["site_name"] == "โรงงาน B" and a["phone"] == "02" and a["acked"] is False


def test_alarm_recovers_when_missing_from_next_poll_and_ack_flow():
    st = _state()
    assert st.ack("so", "solis.PV ISO-PRO", "ตรวจแล้ว", "ช่างเอก") and not st.ack("so", "nope")
    assert st.snapshot()["active_alarms"][0]["acked"] is True
    st.update(Reading("so", "solis", "modbus", pv_w=2100))          # full poll without the alarm
    snap = st.snapshot()
    assert snap["active_alarms"] == []
    events = [h["event"] for h in snap["history"]]
    assert events[:3] == ["recovered", "acked", "raised"]


def test_push_alarm_event_keeps_last_telemetry():
    st = _state()
    ev = Reading("hw", "huawei", "sigen_openapi", alarms=[Alarm(code="sigen.1001")])
    ev.extra["event"] = "alarm"
    st.update(ev)
    d = st.device_view("hw")
    assert d["pv_w"] == 5000 and d["alarm_count"] == 1
    off = Reading("hw", "huawei", "sigen_openapi", alarms=[Alarm(code="sigen.1001", active=False)])
    off.extra["event"] = "alarm"
    st.update(off)
    assert st.device_view("hw")["alarm_count"] == 0


def test_fastapi_endpoints():
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from solar_relay.web.server import create_app
    st = _state()
    c = TestClient(create_app(st))
    assert c.get("/").status_code == 200 and "ทีมบริการ" in c.get("/").text
    assert c.get("/api/health").json()["devices"] == 3
    assert len(c.get("/api/sites").json()) == 3
    assert c.get("/api/devices/hw").json()["site_name"] == "บ้าน A"
    assert c.get("/api/devices/none").status_code == 404
    assert c.post("/api/alarms/ack", json={"device_id": "so", "code": "solis.PV ISO-PRO", "note": "x"}).json() == {"ok": True}
    assert c.post("/api/alarms/ack", json={"device_id": "so", "code": "zzz"}).status_code == 404
    assert c.get("/api/catalog/huawei.2032").json()["category"] == "grid_loss"
    assert c.post("/api/probe", json={}).status_code == 400
