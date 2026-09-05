"""On-site probe: find out how to talk to an inverter before writing config.yaml.

    python -m solar_relay.probe 192.168.1.30                # scan ports, SunSpec, every brand map
    python -m solar_relay.probe 192.168.1.50 --serial 2712345678   # Solarman logger (tcp/8899)
    python -m solar_relay.probe --rtu COM3 --baud 9600      # RS485 (Solis / Deye / Growatt direct)
    python -m solar_relay.probe 192.168.1.30 --maps huawei,solis --units 1,2,3

For every candidate it prints the decoded key values (pv_w, ac_w, grid_w, batt_w, soc, energy_day_kwh,
status) and a plausibility score, then a ready-to-paste `devices:` entry for the best match.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
from dataclasses import dataclass, field
from typing import Any

from .adapters.modbus_maps import MAPS
from .schema import Reading

PORTS = {502: "modbus-tcp", 1502: "modbus-tcp (SolarEdge)", 6607: "modbus-tcp (Huawei SDongle old fw)", 8899: "solarman-v5 / goodwe-udp"}
SUNSPEC_UNITS = [1, 3, 126, 2, 100, 247]
DEFAULT_UNITS = [1, 2, 3, 247]


@dataclass
class Candidate:
    kind: str                     # sunspec | modbus:<map> | solarman:<map>
    unit: int
    port: int | None
    score: int = 0
    values: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
def plausibility(r: Reading) -> tuple[int, list[str]]:
    """Score a decoded Reading: each sane, non-trivial field adds points; nonsense subtracts."""
    score, notes = 0, []

    def ok(name: str, v: float | None, lo: float, hi: float, weight: int = 2) -> None:
        nonlocal score
        if v is None:
            return
        if lo <= v <= hi:
            score += weight
            if v != 0:
                score += 1
            notes.append(f"{name}={v:g}")
        else:
            score -= 3
            notes.append(f"{name}={v:g} OUT OF RANGE")

    ok("pv_w", r.pv_w, 0, 500_000)
    ok("ac_w", r.ac_w, -500_000, 500_000)
    ok("grid_w", r.grid_w, -500_000, 500_000)
    ok("load_w", r.load_w, 0, 500_000)
    ok("batt_w", r.batt_w, -200_000, 200_000)
    ok("soc", r.soc, 0, 100, 3)
    ok("grid_v", r.grid_v, 90, 500, 3)
    ok("grid_hz", r.grid_hz, 45, 65, 3)
    ok("temp_c", r.temp_c, -20, 120)
    ok("energy_day_kwh", r.energy_day_kwh, 0, 100_000)
    ok("energy_total_kwh", r.energy_total_kwh, 0, 1e8)
    if r.status and not str(r.status).startswith("status "):
        score += 2
        notes.append(f"status='{r.status}'")
    if r.strings:
        score += 1
    return score, notes


def tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
async def probe_sunspec(host: str, port: int, units: list[int], timeout: float) -> list[Candidate]:
    out: list[Candidate] = []
    try:
        from pymodbus.client import AsyncModbusTcpClient
    except ImportError:
        return [Candidate("sunspec", 0, port, error="pymodbus not installed")]
    client = AsyncModbusTcpClient(host, port=port, timeout=timeout)
    await client.connect()
    if not client.connected:
        return [Candidate("sunspec", 0, port, error="tcp connect failed")]
    try:
        for unit in units:
            for base in (40000, 50000, 0):
                try:
                    try:
                        rr = await client.read_holding_registers(base, count=4, device_id=unit)
                    except TypeError:
                        rr = await client.read_holding_registers(base, count=4, slave=unit)
                    if rr.isError():
                        continue
                    marker = b"".join(x.to_bytes(2, "big") for x in rr.registers[:2])
                    if marker == b"SunS":
                        c = Candidate("sunspec", unit, port, score=10, notes=[f"'SunS' marker at {base}, first model id {rr.registers[2]}"])
                        out.append(c)
                        break
                except Exception:  # noqa: BLE001
                    continue
    finally:
        client.close()
    return out


async def probe_modbus_maps(host: str, port: int, maps: list[str], units: list[int], timeout: float) -> list[Candidate]:
    from .adapters.modbus_generic import ModbusMapAdapter
    out: list[Candidate] = []
    for key in maps:
        for unit in units:
            c = Candidate(f"modbus:{key}", unit, port)
            adapter = ModbusMapAdapter("probe", key.split("_")[0], 5, map=key, host=host, port=port, unit=unit, timeout=timeout, max_block=60)
            try:
                await adapter.start()
                reading = (await adapter.read())[0]
                c.score, c.notes = plausibility(reading)
                c.values = {k: v for k, v in reading.to_dict().items()
                            if k in ("pv_w", "ac_w", "grid_w", "load_w", "batt_w", "soc", "energy_day_kwh", "energy_total_kwh", "grid_v", "grid_hz", "temp_c", "status")
                            and v is not None}
                if reading.extra.get("model") or reading.extra.get("sn"):
                    c.notes.append(f"model={reading.extra.get('model')} sn={reading.extra.get('sn')}")
                    c.score += 3
            except Exception as exc:  # noqa: BLE001
                c.error = str(exc)[:120]
            finally:
                await adapter.stop()
            out.append(c)
    return out


async def probe_solarman(host: str, port: int, serial: int, maps: list[str], unit: int, timeout: float) -> list[Candidate]:
    from .adapters.solarman import SolarmanAdapter
    out: list[Candidate] = []
    for key in maps:
        c = Candidate(f"solarman:{key}", unit, port)
        adapter = SolarmanAdapter("probe", key.split("_")[0], 5, map=key, host=host, port=port, serial=serial, unit=unit)
        try:
            await asyncio.wait_for(adapter.start(), timeout)
            reading = (await asyncio.wait_for(adapter.read(), timeout * 4))[0]
            c.score, c.notes = plausibility(reading)
            c.values = {k: v for k, v in reading.to_dict().items() if k in ("pv_w", "ac_w", "grid_w", "load_w", "batt_w", "soc", "energy_day_kwh", "status") and v is not None}
        except Exception as exc:  # noqa: BLE001
            c.error = str(exc)[:120]
        finally:
            await adapter.stop()
        out.append(c)
    return out


async def probe_rtu(port: str, baud: int, maps: list[str], units: list[int], timeout: float) -> list[Candidate]:
    from .adapters.modbus_generic import ModbusMapAdapter
    out: list[Candidate] = []
    for key in maps:
        for unit in units:
            c = Candidate(f"modbus:{key}", unit, None)
            adapter = ModbusMapAdapter("probe", key.split("_")[0], 5, map=key, serial=port, baudrate=baud, unit=unit, timeout=timeout, max_block=40)
            try:
                await adapter.start()
                reading = (await adapter.read())[0]
                c.score, c.notes = plausibility(reading)
                c.values = {k: v for k, v in reading.to_dict().items() if k in ("pv_w", "ac_w", "grid_w", "load_w", "batt_w", "soc", "energy_day_kwh", "status") and v is not None}
            except Exception as exc:  # noqa: BLE001
                c.error = str(exc)[:120]
            finally:
                await adapter.stop()
            out.append(c)
    return out


# ---------------------------------------------------------------------------
def config_snippet(host: str | None, c: Candidate, serial: int | None, rtu: str | None, baud: int) -> str:
    dev_id = f"{c.kind.split(':')[-1]}-{(host or rtu or 'dev').replace('.', '-').replace('/', '')}"
    if c.kind == "sunspec":
        opts = f"{{host: {host}, port: {c.port}, unit: {c.unit}}}"
        return f"  - id: {dev_id}\n    adapter: sunspec\n    options: {opts}"
    key = c.kind.split(":")[1]
    brand = key.split("_")[0]
    if c.kind.startswith("solarman:"):
        return (f"  - id: {dev_id}\n    adapter: solarman\n    brand: {brand}\n"
                f"    options: {{map: {key}, host: {host}, port: {c.port}, serial: {serial}, unit: {c.unit}}}")
    if rtu:
        return (f"  - id: {dev_id}\n    adapter: modbus\n    brand: {brand}\n"
                f"    options: {{map: {key}, serial: {rtu}, baudrate: {baud}, unit: {c.unit}}}")
    return (f"  - id: {dev_id}\n    adapter: modbus\n    brand: {brand}\n"
            f"    options: {{map: {key}, host: {host}, port: {c.port}, unit: {c.unit}, max_block: 60}}")


async def run(args: argparse.Namespace) -> int:
    maps = args.maps.split(",") if args.maps else list(MAPS)
    units = [int(u) for u in args.units.split(",")] if args.units else DEFAULT_UNITS
    results: list[Candidate] = []

    if args.rtu:
        print(f"== RS485 {args.rtu} @ {args.baud} 8N1, maps={maps}, units={units}")
        results += await probe_rtu(args.rtu, args.baud, maps, units, args.timeout)
    else:
        host = args.host
        open_ports = [p for p in PORTS if tcp_open(host, p)]
        print(f"== {host}: open TCP ports: " + (", ".join(f"{p} ({PORTS[p]})" for p in open_ports) or "none of 502/1502/6607/8899"))
        if args.serial and (8899 in open_ports or args.port == 8899):
            print("-- Solarman V5 logger probe")
            results += await probe_solarman(host, 8899, int(args.serial), maps, units[0], args.timeout)
        for port in ([args.port] if args.port else [p for p in open_ports if p != 8899]):
            print(f"-- SunSpec scan on {port} units {SUNSPEC_UNITS}")
            results += await probe_sunspec(host, port, SUNSPEC_UNITS, args.timeout)
            print(f"-- brand maps on {port}: {maps} units {units}")
            results += await probe_modbus_maps(host, port, maps, units, args.timeout)
        if 8899 in open_ports and not args.serial:
            print("!! port 8899 open but no --serial given: Solarman loggers need the 10-digit serial printed on the stick "
                  "(GoodWe uses 8899/UDP -> try adapter: goodwe instead)")

    results.sort(key=lambda c: c.score, reverse=True)
    print("\n== results (best first)")
    for c in results:
        where = f"unit {c.unit}" + (f" port {c.port}" if c.port else "")
        if c.error:
            print(f"  x {c.kind:18s} {where:16s} ERROR {c.error}")
        else:
            print(f"  {'*' if c.score >= 8 else ' '} {c.kind:18s} {where:16s} score {c.score:3d}  {', '.join(c.notes)}")
    good = [c for c in results if not c.error and c.score >= 8]
    if good:
        best = good[0]
        print("\n== suggested config.yaml entry (verify grid/battery sign with a known import/export moment!)\ndevices:")
        print(config_snippet(args.host, best, int(args.serial) if args.serial else None, args.rtu, args.baud))
        if args.json:
            print(json.dumps({"best": best.__dict__, "all": [c.__dict__ for c in results]}, ensure_ascii=False, default=str, indent=2))
        return 0
    print("\n!! nothing plausible. Checklist: Modbus TCP enabled on the logger? static IP? correct unit id? "
          "another master (vendor logger) holding the RS485 bus? try --units 1,2,3,100,247 or --maps <brand>")
    return 1


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    p = argparse.ArgumentParser(prog="solar_relay.probe", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("host", nargs="?", help="inverter / logger IP")
    p.add_argument("--port", type=int, help="force a Modbus TCP port instead of scanning")
    p.add_argument("--serial", help="Solarman logger serial (10 digits) for tcp/8899")
    p.add_argument("--rtu", help="serial port for RS485 direct, e.g. COM3 or /dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--maps", help="comma list of brand maps to try (default: all)")
    p.add_argument("--units", help="comma list of unit ids (default 1,2,3,247)")
    p.add_argument("--timeout", type=float, default=3.0)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if not args.host and not args.rtu:
        p.error("give a host IP or --rtu <serial port>")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
