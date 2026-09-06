"""Network helpers for the web UI "ตรวจสอบ inverter" page and the probe:
this machine's addresses / Wi-Fi SSID, and a LAN discovery (ping sweep + ARP + MAC vendor + reverse DNS +
open Modbus ports) that tells the technician which box is probably the inverter and what to do next.
"""
from __future__ import annotations

import concurrent.futures as cf
import ipaddress
import platform
import re
import socket
import subprocess
from functools import lru_cache
from typing import Any

from .probe import PORTS, arp_neighbours, local_ip, local_subnet, sweep

IS_WIN = platform.system() == "Windows"

# OUI (first 3 bytes) -> vendor, for brands a solar technician meets on site (offline fallback; online lookup fills the rest)
OUI_LOCAL: dict[str, str] = {
    "98:44:ce": "Huawei", "00:e0:fc": "Huawei", "48:46:fb": "Huawei", "e4:0e:ee": "Huawei", "70:8a:09": "Huawei",
    "8c:ec:4b": "Huawei", "04:f9:38": "Huawei", "28:6e:d4": "Huawei", "d4:6a:a8": "Huawei", "2c:97:b1": "Huawei",
    "40:a5:ef": "Sungrow", "e8:6d:cb": "Sungrow",
    "34:4a:36": "SolarEdge", "b8:d8:12": "SolarEdge",
    "00:03:ac": "Fronius", "b0:f2:08": "Fronius",
    "00:40:ad": "SMA", "b0:7e:11": "SMA",
    "0c:73:eb": "GoodWe (Espressif)", "ec:fa:bc": "Espressif (WiFi dongle)", "24:6f:28": "Espressif (WiFi dongle)",
    "a4:cf:12": "Espressif (WiFi dongle)", "c8:2b:96": "Espressif (WiFi dongle)", "3c:71:bf": "Espressif (WiFi dongle)",
    "10:d5:61": "Solarman / IGEN (Solis, Deye, Sofar stick)", "d8:f1:5b": "Solarman / IGEN (Solis, Deye, Sofar stick)",
    "b8:27:eb": "Raspberry Pi", "dc:a6:32": "Raspberry Pi", "e4:5f:01": "Raspberry Pi",
    "00:0c:29": "VMware", "00:50:56": "VMware",
}

HINTS = {
    "huawei": "Huawei: SDongle เปิด Modbus TCP ในแอป SUN2000 (Dongle parameter > Modbus TCP = Enable) แล้วใช้ port 502 unit 1 "
              "ถ้าเป็น 192.168.200.1 (hotspot ของ inverter) ลอง port 6607 unit 0",
    "sungrow": "Sungrow: เปิด Modbus TCP ใน WiNet-S และ white-list IP ของเครื่องนี้ port 502 unit 1",
    "solaredge": "SolarEdge: เปิด Modbus TCP ใน SetApp port 1502 unit 1 (adapter sunspec)",
    "fronius": "Fronius: เปิด SunSpec Modbus TCP (int+SF) port 502 unit 1 หรือใช้ adapter fronius_solarapi",
    "sma": "SMA: เปิด Modbus TCP ใน web UI (installer) port 502 unit 3 (adapter sunspec)",
    "solarman": "Solarman stick (Solis DLS-W / Deye / Sofar): port 8899 ต้องใส่ serial 10 หลักบน stick",
    "espressif": "WiFi dongle (ESP): GoodWe ใช้ adapter goodwe (UDP 8899), SolaX Pocket WiFi 3.0 เปิด Modbus TCP port 502",
    "goodwe": "GoodWe: adapter goodwe (UDP 8899) ไม่ต้องตั้งค่า",
}


# ---------------------------------------------------------------------------
def local_addresses() -> list[dict[str, Any]]:
    """Every IPv4 of this machine with its /24 (best effort, no extra deps)."""
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    primary = local_ip()
    if primary:
        ips.add(primary)
    out = []
    for ip in sorted(ips, key=ipaddress.ip_address):
        if ip.startswith("127."):
            continue
        out.append({"ip": ip, "subnet": str(ipaddress.ip_network(f"{ip}/24", strict=False)), "primary": ip == primary})
    return out


def wifi_ssid() -> str | None:
    try:
        if IS_WIN:
            txt = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"^\s*SSID\s*:\s*(.+)$", txt, re.M)
            return m.group(1).strip() if m else None
        for cmd in (["iwgetid", "-r"], ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"]):
            try:
                txt = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
            except FileNotFoundError:
                continue
            if cmd[0] == "nmcli":
                for line in txt.splitlines():
                    if line.startswith("yes:"):
                        return line[4:]
            elif txt:
                return txt
    except Exception:  # noqa: BLE001
        return None
    return None


def visible_inverter_hotspots() -> list[str]:
    """SSIDs that look like inverter / dongle hotspots (Windows only, best effort)."""
    if not IS_WIN:
        return []
    try:
        txt = subprocess.run(["netsh", "wlan", "show", "networks"], capture_output=True, text=True, timeout=8).stdout
    except Exception:  # noqa: BLE001
        return []
    ssids = re.findall(r"^SSID \d+\s*:\s*(.+)$", txt, re.M)
    return sorted({s.strip() for s in ssids if re.search(r"sun2000|huawei|sdongle|solis|deye|sofar|solax|goodwe|sungrow|sg-|ap_|inverter|solarman|igen", s, re.I)})


# ---------------------------------------------------------------------------
def _ping(ip: str, timeout_ms: int = 400) -> bool:
    cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip] if IS_WIN else ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_ms / 1000 + 2)
        return r.returncode == 0 and ("TTL=" in r.stdout or "ttl=" in r.stdout)
    except Exception:  # noqa: BLE001
        return False


def ping_sweep(cidr: str, workers: int = 64) -> list[str]:
    net = ipaddress.ip_network(cidr, strict=False)
    hosts = [str(h) for h in net.hosts()] if net.num_addresses > 1 else [str(net.network_address)]
    with cf.ThreadPoolExecutor(min(workers, max(1, len(hosts)))) as ex:
        alive = [ip for ip, ok in zip(hosts, ex.map(_ping, hosts)) if ok]
    return alive


def reverse_name(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


def is_random_mac(mac: str | None) -> bool:
    """Locally-administered MAC (2nd hex digit 2/6/A/E) = privacy-randomised phone / laptop, never an inverter."""
    if not mac or len(mac) < 2:
        return False
    try:
        return bool(int(mac[1], 16) & 0x2)
    except ValueError:
        return False


@lru_cache(maxsize=512)
def vendor_for(mac: str, online: bool = True) -> str | None:
    if not mac:
        return None
    if is_random_mac(mac):
        return "MAC สุ่ม (มือถือ/โน้ตบุ๊ก)"
    oui = mac.lower().replace("-", ":")[:8]
    if oui in OUI_LOCAL:
        return OUI_LOCAL[oui]
    if not online:
        return None
    import time
    try:  # public OUI API allows ~1 req/s -> callers look up sequentially; retry once on 429
        import httpx
        for attempt in range(2):
            r = httpx.get(f"https://api.macvendors.com/{oui}", timeout=2.5)
            if r.status_code == 200 and r.text and "errors" not in r.text:
                return r.text.strip()[:60]
            if r.status_code == 429 and attempt == 0:
                time.sleep(1.2)
                continue
            break
    except Exception:  # noqa: BLE001
        pass
    return None


def hint_for(vendor: str | None, ports: list[int], ip: str) -> str:
    v = (vendor or "").lower()
    if ports:
        return "เปิด port " + ", ".join(f"{p} ({PORTS.get(p, '?')})" for p in ports) + " -> กด 'ตรวจสอบ' ที่ IP นี้ได้เลย"
    for key, text in HINTS.items():
        if key in v:
            return text
    if ip.endswith(".1"):
        return "น่าจะเป็น router/gateway"
    return "ไม่มี port Modbus เปิด ถ้าเป็น inverter/dongle ต้องเปิด Modbus TCP ที่ตัวอุปกรณ์ก่อน"


def discover(cidr: str | None = None, online_vendor: bool = True, ports: tuple[int, ...] = tuple(PORTS)) -> dict[str, Any]:
    """Full LAN discovery: ping sweep -> ARP -> vendor / hostname -> open Modbus ports -> hint."""
    cidr = cidr or local_subnet()
    if not cidr:
        return {"cidr": None, "hosts": [], "error": "cannot determine local subnet"}
    alive = set(ping_sweep(cidr))
    arp = arp_neighbours(cidr)
    open_ports = sweep(cidr, ports, timeout=0.8)
    ips = sorted(set(alive) | set(arp) | set(open_ports), key=ipaddress.ip_address)
    me = local_ip()
    with cf.ThreadPoolExecutor(16) as ex:
        names = dict(zip(ips, ex.map(reverse_name, ips)))
    vendors: dict[str, str | None] = {}
    import time
    for ip in ips:                          # sequential: the public OUI API rate-limits to ~1 request/s
        mac = arp.get(ip, "")
        needs_online = bool(mac) and online_vendor and not is_random_mac(mac) and mac[:8] not in OUI_LOCAL
        cached_before = vendor_for.cache_info().hits
        vendors[ip] = vendor_for(mac, online_vendor)
        if needs_online and vendor_for.cache_info().hits == cached_before:   # a real request went out
            time.sleep(1.1)
    hosts = []
    for ip in ips:
        ps = open_ports.get(ip, [])
        vendor = vendors.get(ip)
        random_mac = is_random_mac(arp.get(ip))
        hosts.append({
            "ip": ip, "mac": arp.get(ip), "vendor": vendor, "hostname": names.get(ip),
            "alive": ip in alive, "ports": ps, "this_pc": ip == me, "random_mac": random_mac,
            "likely_inverter": bool(ps) or any(k in (vendor or "").lower() for k in ("huawei", "sungrow", "solaredge", "fronius", "sma", "solarman", "igen", "espressif", "goodwe")),
            "hint": "เครื่องนี้" if ip == me else ("มือถือ/โน้ตบุ๊ก (MAC สุ่ม) ไม่ใช่ inverter" if random_mac and not ps else hint_for(vendor, ps, ip)),
        })
    hosts.sort(key=lambda h: (not h["likely_inverter"], ipaddress.ip_address(h["ip"])))
    return {"cidr": cidr, "this_pc": me, "hosts": hosts}


def local_info() -> dict[str, Any]:
    return {"addresses": local_addresses(), "primary": local_ip(), "subnet": local_subnet(), "ssid": wifi_ssid(),
            "hotspots": visible_inverter_hotspots(), "platform": platform.system()}
