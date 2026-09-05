"""End-to-end: in-process pymodbus TCP server populated with Huawei / Solis registers -> ModbusMapAdapter."""
import asyncio
import socket

import pytest

pymodbus = pytest.importorskip("pymodbus")

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext  # noqa: E402
from pymodbus.server import ModbusTcpServer  # noqa: E402

try:
    from pymodbus.datastore import ModbusDeviceContext as _DevCtx  # pymodbus >= 3.10
except ImportError:  # pragma: no cover
    from pymodbus.datastore import ModbusSlaveContext as _DevCtx  # pymodbus 3.7 - 3.9

from solar_relay.adapters.modbus_generic import ModbusMapAdapter  # noqa: E402
from solar_relay.adapters.modbus_maps import HUAWEI, SOLIS  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _u32(v: int) -> list[int]:
    v &= 0xFFFFFFFF
    return [(v >> 16) & 0xFFFF, v & 0xFFFF]


class _Space:
    """Plain register image (fc -> list) filled by the test, then turned into pymodbus data blocks."""

    def __init__(self) -> None:
        self.regs = {3: [0] * 40000, 4: [0] * 40000}

    def setValues(self, fc: int, addr: int, values: list[int]) -> None:  # noqa: N802 - mirrors old pymodbus API
        self.regs[fc][addr: addr + len(values)] = values

    def context(self):
        # pymodbus data blocks take a 1-based start address (legacy); 1 == protocol address 0
        return _DevCtx(hr=ModbusSequentialDataBlock(1, self.regs[3]), ir=ModbusSequentialDataBlock(1, self.regs[4]))


def _slave_context() -> _Space:
    return _Space()


def _server_context(unit: int, slave) -> ModbusServerContext:
    slave = slave.context()
    try:
        return ModbusServerContext(devices={unit: slave}, single=False)   # pymodbus >= 3.9
    except TypeError:
        return ModbusServerContext(slaves={unit: slave}, single=False)    # pymodbus 3.7 / 3.8


async def _run_adapter(map_key: str, unit: int, fill, brand: str):
    slave = _slave_context()
    fill(slave)
    port = _free_port()
    server = ModbusTcpServer(_server_context(unit, slave), address=("127.0.0.1", port))
    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.3)
    try:
        adapter = ModbusMapAdapter("dev", brand, 5, map=map_key, host="127.0.0.1", port=port, unit=unit)
        await adapter.start()
        try:
            return (await adapter.read())[0]
        finally:
            await adapter.stop()
    finally:
        await server.shutdown()
        task.cancel()


def _huawei_fill(slave: _Space) -> None:
    by = {r.name: r for r in HUAWEI}
    slave.setValues(3, by["input_power_w"].addr, _u32(6100))
    slave.setValues(3, by["active_power_w"].addr, _u32(5900))
    slave.setValues(3, by["device_status"].addr, [0x0200])
    slave.setValues(3, by["energy_day_kwh"].addr, _u32(2345))       # 23.45 kWh
    slave.setValues(3, by["meter_status"].addr, [1])
    slave.setValues(3, by["meter_active_power_w"].addr, _u32(-2000))   # Huawei meter: -2000 = importing
    slave.setValues(3, by["ess_running_status"].addr, [2])
    slave.setValues(3, by["ess_charge_discharge_w"].addr, _u32(-1500))  # discharging
    slave.setValues(3, by["ess_soc"].addr, [732])
    slave.setValues(3, by["pv1_v"].addr, [6000, 850])                # 600.0 V, 8.50 A
    slave.setValues(3, by["alarm2"].addr, [1 << 3])                  # Overtemperature


def _solis_fill(slave: _Space) -> None:
    by = {r.name: r for r in SOLIS}
    slave.setValues(4, by["pv_w"].addr, _u32(4200))
    slave.setValues(4, by["ac_w"].addr, _u32(4000))
    slave.setValues(4, by["meter_w"].addr, _u32(900))                # importing
    slave.setValues(4, by["load_w"].addr, [4900])
    slave.setValues(4, by["batt_w"].addr, _u32(0))
    slave.setValues(4, by["soc"].addr, [88])
    slave.setValues(4, by["status"].addr, [3])
    slave.setValues(4, by["energy_day_kwh"].addr, [123])             # 12.3 kWh
    slave.setValues(4, by["fault1"].addr, [0])


async def test_huawei_over_real_modbus_tcp():
    r = await _run_adapter("huawei", 1, _huawei_fill, "huawei")
    assert r.pv_w == 6100 and r.ac_w == 5900
    assert r.grid_w == 2000          # importing -> positive
    assert r.batt_w == -1500 and r.soc == 73.2
    assert r.energy_day_kwh == 23.45
    assert r.status == "On-grid"
    assert r.strings["pv1"] == {"v": 600.0, "a": 8.5, "w": 5100.0}
    assert [a.message for a in r.alarms] == ["Overtemperature"]


async def test_solis_over_real_modbus_tcp_input_registers():
    r = await _run_adapter("solis", 1, _solis_fill, "solis")
    assert r.pv_w == 4200 and r.ac_w == 4000 and r.grid_w == 900 and r.load_w == 4900
    assert r.soc == 88 and r.batt_w == 0 and r.energy_day_kwh == 12.3
    assert r.status == "Generating" and r.alarms == []
