import base64
import json

import httpx
import pytest

from solar_relay.adapters.cloud.sigen_cloud import SigenCloudAdapter, encrypt_password, kw, parse_energyflow


def test_encrypt_password_matches_web_app_scheme():
    # AES-128-CBC, key = iv = b"sigensigensigenp", PKCS7, base64 (same as the `sigen` PyPI package)
    enc = encrypt_password("example-pass1")          # 13 bytes -> one padded 16-byte block
    raw = base64.b64decode(enc)
    assert len(raw) % 16 == 0 and len(raw) == 16
    assert encrypt_password("abc") == encrypt_password("abc")
    assert encrypt_password("abc") != encrypt_password("abd")


def test_kw_guard_and_energyflow_mapping():
    assert kw(1.74) == 1740 and kw(-2.464) == -2464 and kw(4207) == 4207 and kw(None) is None and kw("x") is None
    p = parse_energyflow({"pvPower": 1.74, "loadPower": 0.06, "buySellPower": -4.151, "batteryPower": -2.464, "batterySoc": 24.4,
                          "pvDayNrg": 7.7, "onGrid": True, "stationStatus": 0})
    assert p["pv_w"] == 1740 and p["load_w"] == 60 and p["grid_w"] == -4151 and p["batt_w"] == -2464 and p["soc"] == 24.4
    assert p["energy_day_kwh"] == 7.7 and p["extra"]["onGrid"] is True
    q = parse_energyflow({"buySellPower": 1.0, "batteryPower": 1.0}, grid_import_positive=False, batt_charge_positive=False)
    assert q["grid_w"] == -1000 and q["batt_w"] == -1000


@pytest.mark.asyncio
async def test_adapter_login_home_energyflow_with_mock_server():
    calls: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        if req.url.path == "/auth/oauth/token":
            body = req.content.decode()
            assert "grant_type=password" in body and "username=user%40x.com" in body and "password=" in body
            assert req.headers["Authorization"].startswith("Basic ") and req.headers["client-server"] == "aus"
            return httpx.Response(200, json={"code": 0, "data": {"access_token": "T", "refresh_token": "R", "expires_in": 3600}})
        assert req.headers.get("Authorization") == "Bearer T"
        if req.url.path == "/device/owner/station/home":
            return httpx.Response(200, json={"code": 0, "data": {"stationId": 1001, "stationName": "บ้าน Sigen", "pvCapacity": 10.2, "batteryCapacity": 8, "onGrid": True}})
        if req.url.path == "/device/sigen/station/energyflow":
            assert req.url.params["id"] == "1001"
            return httpx.Response(200, json={"code": 0, "data": {"pvPower": 3.2, "loadPower": 1.1, "buySellPower": -2.0, "batteryPower": 0.1,
                                                                    "batterySoc": 88, "pvDayNrg": 12.5, "stationStatus": 0}})
        if req.url.path == "/data-process/sigen/station/statistics/energy":
            b = json.loads(req.content)
            assert b["stationId"] == "1001" and b["dateFlag"] == "1"
            return httpx.Response(200, json={"code": 0, "data": [{"powerGeneration": 12.5, "powerUse": 9.0, "powerFromGrid": 1.0, "powerToGrid": 4.5,
                                                                     "esCharging": 3.0, "esDischarging": 2.0}]})
        return httpx.Response(404)

    a = SigenCloudAdapter("sigen-cloud", username="user@x.com", password="secret", region="apac")
    await a._http.aclose()
    a._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await a.start()
    readings = await a.read()
    r = readings[0]
    assert r.device_id == "sigen-cloud" and r.brand == "sigen" and r.online
    assert r.pv_w == 3200 and r.load_w == 1100 and r.grid_w == -2000 and r.batt_w == 100 and r.soc == 88
    assert r.energy_day_kwh == 12.5 and r.grid_export_day_kwh == 4.5 and r.batt_charge_day_kwh == 3.0 and r.load_day_kwh == 9.0
    assert r.status == "Normal" and r.extra["name"] == "บ้าน Sigen" and r.extra["pv_capacity_kw"] == 10.2
    assert calls[0] == ("POST", "/auth/oauth/token") and ("GET", "/device/owner/station/home") in calls
    await a.stop()


@pytest.mark.asyncio
async def test_adapter_reports_login_rejection():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad credentials")

    a = SigenCloudAdapter("s", username="u", password="p", region="eu")
    await a._http.aclose()
    a._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(PermissionError):
        await a.start()
    await a.stop()
