import time

import pytest

from solar_relay import netinfo


def test_random_mac_detection():
    assert netinfo.is_random_mac("22:87:12:48:be:65") and netinfo.is_random_mac("6a:5d:80:2b:cb:a2") and netinfo.is_random_mac("5a:5a:00:01:20:5c")
    assert not netinfo.is_random_mac("98:44:ce:93:06:d0") and not netinfo.is_random_mac("14:11:5d:49:63:98") and not netinfo.is_random_mac(None)
    assert "สุ่ม" in netinfo.vendor_for("22:87:12:48:be:65", online=False)


def test_vendor_local_table_and_hints():
    assert netinfo.vendor_for("98:44:CE:93:06:D0", online=False) == "Huawei"
    assert netinfo.vendor_for("98-44-ce-00-00-01", online=False) == "Huawei"
    assert netinfo.vendor_for("00:11:22:33:44:55", online=False) is None
    assert "6607" in netinfo.hint_for("Huawei", [], "192.168.200.1")
    assert "serial" in netinfo.hint_for("Solarman / IGEN", [], "192.168.1.50")
    assert "502" in netinfo.hint_for(None, [502], "192.168.1.30")
    assert "router" in netinfo.hint_for(None, [], "192.168.1.1")


def test_local_info_shape():
    info = netinfo.local_info()
    assert set(info) >= {"addresses", "primary", "subnet", "ssid", "hotspots", "platform"}
    for a in info["addresses"]:
        assert a["subnet"].endswith("/24") and not a["ip"].startswith("127.")


def test_discover_loopback_marks_open_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        t0 = time.time()
        d = netinfo.discover("127.0.0.1/32", online_vendor=False, ports=(port,))
    assert d["cidr"] == "127.0.0.1/32"
    assert d["hosts"] and d["hosts"][0]["ip"] == "127.0.0.1" and d["hosts"][0]["ports"] == [port]
    assert d["hosts"][0]["likely_inverter"] is True
    assert time.time() - t0 < 30


def test_web_net_and_probe_job_endpoints():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from solar_relay.web.server import create_app
    from solar_relay.web.state import State
    c = TestClient(create_app(State()))
    assert "addresses" in c.get("/api/net").json()
    r = c.post("/api/probe/start", json={"scan": "127.0.0.1/32", "ports": "1"})
    assert r.status_code == 200
    job = r.json()["job"]
    for _ in range(100):
        log = c.get(f"/api/probe/log?job={job}").json()
        if log["done"]:
            break
        time.sleep(0.1)
    assert log["done"] and log["rc"] == 1
    assert any("sweeping 127.0.0.1/32" in ln for ln in log["lines"])
    assert c.get("/api/probe/log?job=nope").status_code == 404
    assert c.post("/api/probe/start", json={}).status_code == 400
    # a long job: second start attaches to the running one, cancel stops it
    r = c.post("/api/probe/start", json={"host": "127.0.0.1", "ports": "1", "timeout": 30, "maps": "huawei"}).json()
    r2 = c.post("/api/probe/start", json={"scan": "127.0.0.1/32", "ports": "1"}).json()
    assert r2["job"] == r["job"] and r2.get("already_running") is True
    assert c.post(f"/api/probe/cancel?job={r['job']}").json()["ok"] is True
    for _ in range(100):
        log = c.get(f"/api/probe/log?job={r['job']}").json()
        if log["done"]:
            break
        time.sleep(0.1)
    assert log["done"] and log["rc"] == 3 and any("ยกเลิก" in ln for ln in log["lines"])
