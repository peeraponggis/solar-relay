"""On-site probe: find out how to talk to an inverter before writing config.yaml.

    python -m solar_relay.probe 192.168.1.30                # scan ports, SunSpec, every brand map
    python -m solar_relay.probe 192.168.1.50 --serial 2712345678   # Solarman logger (tcp/8899)
    python -m solar_relay.probe --rtu COM3 --baud 9600      # RS485 (Solis / Deye / Growatt direct)
    python -m solar_relay.probe 192.168.1.30 --maps huawei,solis --units 1,2,3
    python -m solar_relay.probe --scan                      # sweep this PC's /24 for Modbus/Solarman ports, probe every hit
    python -m solar_relay.probe --scan 192.168.10.0/24 --ports 502,6607

For every candidate it prints the decoded key values (pv_w, ac_w, grid_w, batt_w, soc, energy_day_kwh,
status) and a plausibility score, then a ready-to-paste `devices:` entry for the best match.
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures as cf
import ipaddress
import json
import re
import socket
import subprocess
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
    host: str | None = None       # filled by --scan (one probe run covers many hosts)


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
# subnet sweep (--scan)
# ---------------------------------------------------------------------------
def local_ip() -> str | None:
    """Primary IPv4 of this machine (the one that would route to the internet / LAN)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))      # no packet is sent for UDP connect
            return s.getsockname()[0]
    except OSError:
        return None


def local_subnet() -> str | None:
    ip = local_ip()
    return str(ipaddress.ip_network(f"{ip}/24", strict=False)) if ip else None


def sweep(cidr: str, ports: tuple[int, ...] = (502, 1502, 6607, 8899), timeout: float = 0.6, workers: int = 200) -> dict[str, list[int]]:
    """TCP-connect every host in ``cidr`` on ``ports``; returns {ip: [open ports]} sorted by address."""
    net = ipaddress.ip_network(cidr, strict=False)
    hosts = [str(h) for h in (net.hosts() if net.num_addresses > 1 else [net.network_address])]
    jobs = [(h, p) for h in hosts for p in ports]
    found: dict[str, list[int]] = {}
    with cf.ThreadPoolExecutor(min(workers, max(1, len(jobs)))) as ex:
        for (h, p), ok in zip(jobs, ex.map(lambda j: tcp_open(j[0], j[1], timeout), jobs)):
            if ok:
                found.setdefault(h, []).append(p)
    return {ip: sorted(ps) for ip, ps in sorted(found.items(), key=lambda kv: ipaddress.ip_address(kv[0]))}


_ARP_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)\)?\s+(?:at\s+)?([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})")


def parse_arp(text: str, cidr: str) -> dict[str, str]:
    """ip -> mac for entries inside cidr (works on `arp -a` output from Windows, Linux and macOS)."""
    net = ipaddress.ip_network(cidr, strict=False)
    out: dict[str, str] = {}
    for ip, mac in _ARP_RE.findall(text):
        try:
            if ipaddress.ip_address(ip) in net and not ip.endswith(".255") and not mac.lower().startswith(("ff-ff", "ff:ff", "01-00-5e", "01:00:5e")):
                out[ip] = mac.lower().replace("-", ":")
        except ValueError:
            continue
    return out


def arp_neighbours(cidr: str) -> dict[str, str]:
    try:
        text = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return {}
    return parse_arp(text, cidr)


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
    host = c.host or host
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


async def probe_host(host: str, open_ports: list[int], args: argparse.Namespace, maps: list[str], units: list[int]) -> list[Candidate]:
    """Probe one host on its open ports: Solarman (if serial), SunSpec, then every brand map."""
    results: list[Candidate] = []
    if args.serial and (8899 in open_ports or args.port == 8899):
        print(f"-- {host}: Solarman V5 logger probe")
        results += await probe_solarman(host, 8899, int(args.serial), maps, units[0], args.timeout)
    for port in ([args.port] if args.port else [p for p in open_ports if p != 8899]):
        if port == 6607:
            # Huawei-only port (inverter Wi-Fi hotspot / old SDongle): no SunSpec there, unit 0 on the hotspot, 1 via dongle
            hw_maps = [m for m in maps if m == "huawei"] or ["huawei"]
            hw_units = units if args.units else [0, 1]
            print(f"-- {host}:{port} Huawei port -> skip SunSpec, map huawei units {hw_units} (ปิดแอป SUN2000 ก่อน inverter รับ Modbus ได้ทีละ 1 client)")
            results += await probe_modbus_maps(host, port, hw_maps, hw_units, args.timeout)
            continue
        print(f"-- {host}:{port} SunSpec scan units {SUNSPEC_UNITS}")
        results += await probe_sunspec(host, port, SUNSPEC_UNITS, args.timeout)
        print(f"-- {host}:{port} brand maps {maps} units {units}")
        results += await probe_modbus_maps(host, port, maps, units, args.timeout)
    if 8899 in open_ports and not args.serial:
        print(f"!! {host}: port 8899 open but no --serial given: Solarman loggers need the 10-digit serial printed on the stick "
              "(GoodWe uses 8899/UDP -> try adapter: goodwe instead)")
    for c in results:
        c.host = host
    return results


async def run(args: argparse.Namespace) -> int:
    maps = args.maps.split(",") if args.maps else list(MAPS)
    units = [int(u) for u in args.units.split(",")] if args.units else DEFAULT_UNITS
    scan = getattr(args, "scan", None)
    results: list[Candidate] = []

    if args.rtu:
        print(f"== RS485 {args.rtu} @ {args.baud} 8N1, maps={maps}, units={units}")
        results += await probe_rtu(args.rtu, args.baud, maps, units, args.timeout)
    elif scan:
        cidr = scan if scan not in ("auto", "", True) else local_subnet()
        if not cidr:
            print("!! cannot determine this PC's subnet, give one: --scan 192.168.1.0/24")
            return 2
        ports = tuple(int(p) for p in str(getattr(args, "ports", "") or "").split(",") if p) or tuple(PORTS)
        print(f"== sweeping {cidr} on ports {list(ports)} (this PC: {local_ip()})")
        found = await asyncio.get_running_loop().run_in_executor(None, lambda: sweep(cidr, ports, min(args.timeout, 1.0)))
        if found:
            for ip, ps in found.items():
                print(f"   {ip:16s} open: " + ", ".join(f"{p} ({PORTS.get(p, '?')})" for p in ps))
        else:
            print("   no host answers on those ports")
        neigh = arp_neighbours(cidr)
        silent = [ip for ip in neigh if ip not in found and ip != local_ip()]
        if silent:
            print(f"-- hosts alive on the LAN but with none of those ports open: {', '.join(f'{ip} ({neigh[ip]})' for ip in silent)}")
            print("   ถ้า inverter/dongle เป็นหนึ่งในนี้ แสดงว่ายังไม่เปิด Modbus TCP ที่ตัวอุปกรณ์ (Huawei SDongle ปิดเป็นค่าเริ่มต้น -> แอป SUN2000 > "
                  "Dongle parameter > Modbus TCP = Enable) หรือเป็น Solarman stick ที่ต้องใช้ --serial")
        for ip, ps in found.items():
            results += await probe_host(ip, ps, args, maps, units)
    else:
        host = args.host
        open_ports = [p for p in PORTS if tcp_open(host, p, min(max(args.timeout, 1.5), 8.0))]   # inverter Wi-Fi APs answer slowly
        print(f"== {host}: open TCP ports: " + (", ".join(f"{p} ({PORTS[p]})" for p in open_ports) or "none of 502/1502/6607/8899"))
        results += await probe_host(host, open_ports, args, maps, units)

    results.sort(key=lambda c: c.score, reverse=True)
    print("\n== results (best first)")
    for c in results:
        where = (f"{c.host} " if scan and c.host else "") + f"unit {c.unit}" + (f" port {c.port}" if c.port else "")
        if c.error:
            print(f"  x {c.kind:18s} {where:16s} ERROR {c.error}")
        else:
            print(f"  {'*' if c.score >= 8 else ' '} {c.kind:18s} {where:16s} score {c.score:3d}  {', '.join(c.notes)}")
    good = [c for c in results if not c.error and c.score >= 8]
    if good:
        print("\n== suggested config.yaml entry (verify grid/battery sign with a known import/export moment!)\ndevices:")
        shown: set[str | None] = set()
        for c in good:                      # with --scan: one entry per host
            if c.host in shown:
                continue
            shown.add(c.host)
            print(config_snippet(args.host, c, int(args.serial) if args.serial else None, args.rtu, args.baud))
        best = good[0]
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
    p.add_argument("--scan", nargs="?", const="auto", metavar="CIDR",
                   help="sweep a subnet (default: this PC's /24) for open Modbus/Solarman ports and probe every hit")
    p.add_argument("--ports", help="comma list of ports for --scan (default 502,1502,6607,8899)")
    args = p.parse_args(argv)
    if not args.host and not args.rtu and not args.scan:
        p.error("give a host IP, --rtu <serial port> or --scan [CIDR]")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
