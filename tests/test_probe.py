import asyncio
import socket

import pytest

from solar_relay import probe
from solar_relay.schema import Reading


def test_plausibility_scores_sane_reading_high_and_garbage_low():
    good = Reading(device_id="d", brand="huawei", source="t", pv_w=3200, ac_w=3100, grid_w=-900, soc=63,
                   grid_v=231.2, grid_hz=50.01, temp_c=41, energy_day_kwh=12.3, status="On-grid")
    bad = Reading(device_id="d", brand="x", source="t", pv_w=6_000_000, soc=655.35, grid_hz=0.0, grid_v=6553.5, status="status 65535")
    gs, gnotes = probe.plausibility(good)
    bs, bnotes = probe.plausibility(bad)
    assert gs >= 20 and bs < 0
    assert any("OUT OF RANGE" in n for n in bnotes) and not any("OUT OF RANGE" in n for n in gnotes)


def test_all_zero_reading_is_not_convincing():
    zero = Reading(device_id="d", brand="x", source="t", pv_w=0, ac_w=0, grid_w=0, soc=0, energy_day_kwh=0)
    s, _ = probe.plausibility(zero)
    assert s < 12


def test_tcp_open_on_closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert probe.tcp_open("127.0.0.1", port, timeout=0.5) is False


def test_config_snippet_variants():
    c = probe.Candidate("modbus:deye_3p", 1, 502, score=12)
    snip = probe.config_snippet("192.168.1.34", c, None, None, 9600)
    assert "adapter: modbus" in snip and "map: deye_3p" in snip and "brand: deye" in snip and "host: 192.168.1.34" in snip
    s2 = probe.config_snippet("192.168.1.50", probe.Candidate("solarman:sofar", 1, 8899), 2798765432, None, 9600)
    assert "adapter: solarman" in s2 and "serial: 2798765432" in s2
    s3 = probe.config_snippet(None, probe.Candidate("modbus:solis", 1, None), None, "COM3", 9600)
    assert "serial: COM3" in s3 and "baudrate: 9600" in s3
    s4 = probe.config_snippet("10.0.0.5", probe.Candidate("sunspec", 3, 502), None, None, 9600)
    assert "adapter: sunspec" in s4 and "unit: 3" in s4


def test_probe_modbus_maps_reports_errors_for_dead_host():
    pytest.importorskip("pymodbus")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    res = asyncio.run(probe.probe_modbus_maps("127.0.0.1", port, ["huawei"], [1], 0.5))
    assert len(res) == 1 and res[0].error


def test_cli_requires_target(capsys):
    with pytest.raises(SystemExit):
        probe.main([])


def test_probe_end_to_end_picks_huawei_on_simulated_inverter(capsys):
    """Spin up the pymodbus simulator from test_modbus_integration with Huawei registers and let the
    full CLI scan it: SunSpec must not match, brand map 'huawei' must win, snippet must be printed."""
    pytest.importorskip("pymodbus")
    from pymodbus.server import ModbusTcpServer

    from tests.test_modbus_integration import _free_port, _huawei_fill, _server_context, _slave_context

    async def scenario() -> int:
        slave = _slave_context()
        _huawei_fill(slave)
        port = _free_port()
        server = ModbusTcpServer(_server_context(1, slave), address=("127.0.0.1", port))
        task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.3)
        try:
            args = probe.argparse.Namespace(host="127.0.0.1", port=port, serial=None, rtu=None, baud=9600,
                                            maps="huawei,solis,sungrow", units="1", timeout=1.0, json=False)
            return await probe.run(args)
        finally:
            await server.shutdown()
            task.cancel()

    rc = asyncio.run(scenario())
    out = capsys.readouterr().out
    assert rc == 0
    assert "* modbus:huawei" in out and "map: huawei" in out and "adapter: modbus" in out
    assert "status='On-grid'" in out
