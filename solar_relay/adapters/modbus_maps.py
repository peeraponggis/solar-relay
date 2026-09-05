"""Brand register maps for vendors that do NOT expose SunSpec (or where the vendor map is richer).

Every map is a list of :class:`Reg` plus a ``finalize`` function that converts the raw
decoded values into ``Reading`` fields with the relay sign conventions.

Address convention: ``addr`` is the PROTOCOL (0-based) address sent on the wire.
Where a vendor document lists 1-based register numbers the comment says so.

Sources (verify against the vendor PDF for your firmware before trusting a control loop):
  huawei     : SUN2000 "Modbus Interface Definitions" (same map as the huawei-solar PyPI lib)
  solis      : RS485_MODBUS Hybrid Inverter Protocol ESINV-33000ID, Pho3niX90/solis_modbus
  sungrow    : SH/SG "Communication Protocol" (mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant)
  solax      : X1/X3 Hybrid Modbus TCP (wills106/homeassistant-solax-modbus)
  deye_1p    : SUN-xK-SG0xLP1 (single-phase hybrid)   - via Solarman logger or Modbus TCP
  deye_3p    : SUN-xK-SG0xLP3 (three-phase hybrid)    - via Solarman logger or Modbus TCP
  sofar      : Sofar HYD-ES/KTL G3 (wills106 map)      - via Solarman logger
  sigen_local: Sigenergy Modbus-TCP protocol (TypQxQ/Sigenergy-Local-Modbus) plant unit 247
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..schema import Alarm, Reading


# ---------------------------------------------------------------------------
# decoding primitives (no pymodbus dependency -> unit-testable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Reg:
    name: str
    addr: int                 # protocol address (0-based)
    dtype: str = "u16"        # u16 | i16 | u32 | i32 | u64 | str<N>
    scale: float = 1.0
    fc: int = 3               # 3 = holding, 4 = input
    wordorder: str = "big"    # big = high word first (Modbus default), little = low word first

    @property
    def count(self) -> int:
        if self.dtype in ("u32", "i32"):
            return 2
        if self.dtype == "u64":
            return 4
        if self.dtype.startswith("str"):
            return int(self.dtype[3:])
        return 1


def decode(words: list[int], reg: Reg) -> float | str:
    w = list(words[: reg.count])
    if reg.dtype.startswith("str"):
        b = b"".join(x.to_bytes(2, "big") for x in w)
        return b.decode("ascii", "ignore").strip("\x00 ")
    if reg.wordorder == "little" and len(w) > 1:
        w = w[::-1]
    raw = 0
    for x in w:
        raw = (raw << 16) | (x & 0xFFFF)
    bits = 16 * len(w)
    if reg.dtype in ("i16", "i32") and raw >= 1 << (bits - 1):
        raw -= 1 << bits
    return round(raw * reg.scale, 6)


def plan_blocks(regs: list[Reg], max_block: int = 100) -> list[tuple[int, int, int, list[Reg]]]:
    """Group registers into contiguous read blocks: (fc, start, count, regs)."""
    blocks: list[tuple[int, int, int, list[Reg]]] = []
    for fc in sorted({r.fc for r in regs}):
        rs = sorted((r for r in regs if r.fc == fc), key=lambda r: r.addr)
        cur: list[Reg] = []
        for r in rs:
            if cur and (r.addr + r.count - cur[0].addr > max_block or r.addr - (cur[-1].addr + cur[-1].count) > 8):
                blocks.append((fc, cur[0].addr, cur[-1].addr + cur[-1].count - cur[0].addr, cur))
                cur = []
            cur.append(r)
        if cur:
            blocks.append((fc, cur[0].addr, cur[-1].addr + cur[-1].count - cur[0].addr, cur))
    return blocks


def decode_block(words: list[int], start: int, regs: list[Reg]) -> dict[str, float | str]:
    out: dict[str, float | str] = {}
    for r in regs:
        off = r.addr - start
        out[r.name] = decode(words[off: off + r.count], r)
    return out


def bit_alarms(value: float | str | None, prefix: str, table: dict[int, str] | None = None) -> list[Alarm]:
    """Expand a 16/32-bit fault word into Alarm objects (bit index + optional text)."""
    if value is None or isinstance(value, str):
        return []
    v = int(value)
    alarms = []
    for bit in range(32):
        if v & (1 << bit):
            text = (table or {}).get(bit, "")
            alarms.append(Alarm(code=f"{prefix}.b{bit}", message=text, severity="fault"))
    return alarms


def coded_alarms(value: float | str | None, brand: str, table: dict[int, tuple[str, str]], fallback_prefix: str) -> list[Alarm]:
    """Expand a fault word using a bit -> (vendor code, text) table so the alarm code matches the
    vendor manual and alarm_catalog.yaml (e.g. huawei.2032, deye.F16, sofar.ID01).  Bits missing from
    the table fall back to <fallback_prefix>.b<bit>."""
    if value is None or isinstance(value, str):
        return []
    v = int(value)
    alarms = []
    for bit in range(32):
        if v & (1 << bit):
            code, text = table.get(bit, (f"{fallback_prefix}.b{bit}".split(".", 1)[1], ""))
            alarms.append(Alarm(code=f"{brand}.{code}", message=text, severity="fault"))
    return alarms


def numbered_alarms(value: float | str | None, brand: str, prefix: str, first: int, width: int = 2,
                    names: dict[str, str] | None = None) -> list[Alarm]:
    """Fault word where bit n of word k means code <prefix><first + n> (Deye F01.., Sofar ID01..)."""
    if value is None or isinstance(value, str):
        return []
    v = int(value)
    alarms = []
    for bit in range(16):
        if v & (1 << bit):
            code = f"{prefix}{first + bit:0{width}d}"
            alarms.append(Alarm(code=f"{brand}.{code}", message=(names or {}).get(code, ""), severity="fault"))
    return alarms


# ---------------------------------------------------------------------------
# HUAWEI SUN2000 (Modbus TCP 502 direct, or SDongle 502 / 6607; unit id 1, meter/battery on same unit)
# ---------------------------------------------------------------------------
HUAWEI: list[Reg] = [
    Reg("model", 30000, "str15"),
    Reg("sn", 30015, "str10"),
    Reg("state1", 32000),
    Reg("alarm1", 32008), Reg("alarm2", 32009), Reg("alarm3", 32010),
    Reg("pv1_v", 32016, "i16", 0.1), Reg("pv1_a", 32017, "i16", 0.01),
    Reg("pv2_v", 32018, "i16", 0.1), Reg("pv2_a", 32019, "i16", 0.01),
    Reg("pv3_v", 32020, "i16", 0.1), Reg("pv3_a", 32021, "i16", 0.01),
    Reg("pv4_v", 32022, "i16", 0.1), Reg("pv4_a", 32023, "i16", 0.01),
    Reg("input_power_w", 32064, "i32"),
    Reg("grid_v_ab", 32066, "u16", 0.1),
    Reg("phase_a_v", 32069, "u16", 0.1),
    Reg("active_power_w", 32080, "i32"),
    Reg("reactive_var", 32082, "i32", 1.0),
    Reg("grid_hz", 32085, "u16", 0.01),
    Reg("efficiency", 32086, "u16", 0.01),
    Reg("temp_c", 32087, "i16", 0.1),
    Reg("device_status", 32089),
    Reg("energy_total_kwh", 32106, "u32", 0.01),
    Reg("energy_day_kwh", 32114, "u32", 0.01),
    # smart power sensor (grid meter)
    Reg("meter_status", 37100),
    Reg("meter_active_power_w", 37113, "i32"),         # +import / -export as seen by the Huawei meter
    # LUNA2000 / ESS
    Reg("ess_running_status", 37000),
    Reg("ess_charge_discharge_w", 37001, "i32"),         # + charge / - discharge
    Reg("ess_soc", 37004, "u16", 0.1),
    Reg("ess_total_charge_kwh", 37066, "u32", 0.01),
    Reg("ess_total_discharge_kwh", 37068, "u32", 0.01),
    Reg("ess_day_charge_kwh", 37015, "u32", 0.01),
    Reg("ess_day_discharge_kwh", 37017, "u32", 0.01),
]

HUAWEI_STATUS = {
    0x0000: "Standby: initializing", 0x0001: "Standby: insulation detecting", 0x0002: "Standby: irradiation too weak",
    0x0003: "Standby: grid detecting", 0x0100: "Starting", 0x0200: "On-grid", 0x0201: "Grid: power limited",
    0x0202: "Grid: self-derating", 0x0300: "Shutdown: fault", 0x0301: "Shutdown: command", 0x0302: "Shutdown: OVGR",
    0x0303: "Shutdown: communication disconnected", 0x0304: "Shutdown: power limited", 0x0305: "Shutdown: manual startup required",
    0x0306: "Shutdown: DC switches disconnected", 0x0307: "Shutdown: rapid cutoff", 0x0308: "Shutdown: input underpower",
    0x0401: "Grid scheduling: cosphi-P curve", 0x0402: "Grid scheduling: Q-U curve", 0x0403: "Grid scheduling: PF-U curve",
    0x0404: "Grid scheduling: dry contact", 0x0405: "Grid scheduling: Q-P curve", 0x0500: "Spot-check ready", 0x0501: "Spot-checking",
    0x0600: "Inspecting", 0x0700: "AFCI self check", 0x0800: "I-V scanning", 0x0900: "DC input detection",
    0x0A00: "Running: off-grid charging", 0xA000: "Standby: no irradiation",
}

# bit -> (Huawei alarm ID as shown in FusionSolar / manual, text)   [SUN2000 Modbus Interface Definitions, registers 32008-32010]
HUAWEI_ALARM1 = {0: ("2001", "High string input voltage"), 1: ("2002", "DC arc fault"), 2: ("2011", "String reverse connection"),
                 3: ("2012", "String current backfeed"), 4: ("2013", "Abnormal string power"), 5: ("2021", "AFCI self-check fail"),
                 6: ("2031", "Phase wire short-circuited to PE"), 7: ("2032", "Grid loss"), 8: ("2033", "Grid undervoltage"),
                 9: ("2034", "Grid overvoltage"), 10: ("2035", "Grid voltage imbalance"), 11: ("2036", "Grid overfrequency"),
                 12: ("2037", "Grid underfrequency"), 13: ("2038", "Unstable grid frequency"), 14: ("2039", "Output overcurrent"),
                 15: ("2040", "Output DC component overhigh")}
HUAWEI_ALARM2 = {0: ("2051", "Abnormal residual current"), 1: ("2061", "Abnormal grounding"), 2: ("2062", "Low insulation resistance"),
                 3: ("2063", "Overtemperature"), 4: ("2064", "Device fault"), 5: ("2065", "Upgrade failed or version mismatch"),
                 6: ("2066", "License expired"), 7: ("61440", "Faulty monitoring unit"), 8: ("2067", "Faulty power collector"),
                 9: ("2068", "Battery abnormal"), 10: ("2070", "Active islanding"), 11: ("2071", "Passive islanding"),
                 12: ("2072", "Transient AC overvoltage"), 13: ("2075", "Peripheral port short circuit"),
                 14: ("2077", "Abnormal grounding or AC wiring"), 15: ("2080", "Abnormal PV module configuration")}
HUAWEI_ALARM3 = {0: ("2081", "Optimizer fault"), 1: ("2085", "Built-in PID operation abnormal"), 2: ("2014", "High input string voltage to ground"),
                 3: ("2086", "External fan abnormal"), 4: ("2069", "Battery reverse connection"), 5: ("2082", "On-grid/off-grid controller abnormal"),
                 6: ("2015", "PV string loss"), 7: ("2087", "Internal fan abnormal"), 8: ("2088", "DC protection unit abnormal"),
                 9: ("2089", "EL unit abnormal"), 10: ("2090", "Active adjustment instruction abnormal"),
                 11: ("2091", "Reactive adjustment instruction abnormal"), 12: ("2092", "CT wiring abnormal"), 13: ("2003", "DC arc fault (manual clear)")}


def finalize_huawei(v: dict, r: Reading) -> Reading:
    r.pv_w = v.get("input_power_w")
    r.ac_w = v.get("active_power_w")
    r.reactive_var = v.get("reactive_var")
    r.grid_hz = v.get("grid_hz")
    r.grid_v = v.get("phase_a_v")
    r.temp_c = v.get("temp_c")
    r.energy_total_kwh = v.get("energy_total_kwh")
    r.energy_day_kwh = v.get("energy_day_kwh")
    st = int(v.get("device_status", -1))
    r.status = HUAWEI_STATUS.get(st, f"status 0x{st:04X}")
    if v.get("meter_status", 0):
        r.grid_w = v.get("meter_active_power_w")
        if r.grid_w is not None:
            r.grid_w = -r.grid_w  # Huawei meter reports +export; relay wants +import
    if v.get("ess_running_status", 0) not in (0, 4):   # 0 offline, 4 fault
        r.batt_w = v.get("ess_charge_discharge_w")
        r.soc = v.get("ess_soc")
        r.batt_charge_day_kwh = v.get("ess_day_charge_kwh")
        r.batt_discharge_day_kwh = v.get("ess_day_discharge_kwh")
    for i in range(1, 5):
        pv_v, pv_a = v.get(f"pv{i}_v"), v.get(f"pv{i}_a")
        if pv_v:
            r.strings[f"pv{i}"] = {"v": pv_v, "a": pv_a, "w": round(pv_v * pv_a, 1)}
    r.alarms += coded_alarms(v.get("alarm1"), "huawei", HUAWEI_ALARM1, "huawei.alarm1")
    r.alarms += coded_alarms(v.get("alarm2"), "huawei", HUAWEI_ALARM2, "huawei.alarm2")
    r.alarms += coded_alarms(v.get("alarm3"), "huawei", HUAWEI_ALARM3, "huawei.alarm3")
    r.extra.update(model=v.get("model"), sn=v.get("sn"), efficiency=v.get("efficiency"))
    return r


# ---------------------------------------------------------------------------
# SOLIS hybrid (RS485 9600 8N1 unit 1, or Modbus TCP 502 through DLS-L / S2-WL-ST / Waveshare)
# Protocol lists 1-based input registers 33xxx; wire address = number - 1.  FC04 (input).
# ---------------------------------------------------------------------------
def _s(n: int) -> int:           # 1-based -> protocol address
    return n - 1

SOLIS: list[Reg] = [
    Reg("energy_total_kwh", _s(33029), "u32", 1.0, 4),
    Reg("energy_month_kwh", _s(33031), "u32", 1.0, 4),
    Reg("energy_day_kwh", _s(33035), "u16", 0.1, 4),
    Reg("energy_yesterday_kwh", _s(33036), "u16", 0.1, 4),
    Reg("pv1_v", _s(33049), "u16", 0.1, 4), Reg("pv1_a", _s(33050), "u16", 0.1, 4),
    Reg("pv2_v", _s(33051), "u16", 0.1, 4), Reg("pv2_a", _s(33052), "u16", 0.1, 4),
    Reg("pv3_v", _s(33053), "u16", 0.1, 4), Reg("pv3_a", _s(33054), "u16", 0.1, 4),
    Reg("pv4_v", _s(33055), "u16", 0.1, 4), Reg("pv4_a", _s(33056), "u16", 0.1, 4),
    Reg("pv_w", _s(33057), "u32", 1.0, 4),
    Reg("grid_v_a", _s(33073), "u16", 0.1, 4),
    Reg("ac_w", _s(33079), "i32", 1.0, 4),
    Reg("reactive_var", _s(33081), "i32", 1.0, 4),
    Reg("temp_c", _s(33093), "i16", 0.1, 4),
    Reg("grid_hz", _s(33094), "u16", 0.01, 4),
    Reg("status", _s(33095), "u16", 1.0, 4),
    Reg("fault1", _s(33116), "u16", 1.0, 4), Reg("fault2", _s(33117), "u16", 1.0, 4),
    Reg("fault3", _s(33118), "u16", 1.0, 4), Reg("fault4", _s(33119), "u16", 1.0, 4),
    Reg("fault5", _s(33120), "u16", 1.0, 4), Reg("working_status", _s(33121), "u16", 1.0, 4),
    Reg("meter_w", _s(33130), "i32", 1.0, 4),          # + import / - export (meter at grid point)
    Reg("batt_v", _s(33133), "u16", 0.1, 4),
    Reg("batt_a", _s(33134), "u16", 0.1, 4),
    Reg("batt_dir", _s(33135), "u16", 1.0, 4),         # 0 charge, 1 discharge
    Reg("soc", _s(33139), "u16", 1.0, 4),
    Reg("soh", _s(33140), "u16", 1.0, 4),
    Reg("load_w", _s(33147), "u16", 1.0, 4),
    Reg("backup_w", _s(33148), "u16", 1.0, 4),
    Reg("batt_w", _s(33149), "u32", 1.0, 4),
    Reg("batt_charge_total_kwh", _s(33161), "u32", 1.0, 4),
    Reg("batt_charge_day_kwh", _s(33163), "u16", 0.1, 4),
    Reg("batt_discharge_total_kwh", _s(33165), "u32", 1.0, 4),
    Reg("batt_discharge_day_kwh", _s(33167), "u16", 0.1, 4),
    Reg("grid_import_total_kwh", _s(33169), "u32", 1.0, 4),
    Reg("grid_import_day_kwh", _s(33171), "u16", 0.1, 4),
    Reg("grid_export_total_kwh", _s(33173), "u32", 1.0, 4),
    Reg("grid_export_day_kwh", _s(33175), "u16", 0.1, 4),
    Reg("load_total_kwh", _s(33177), "u32", 1.0, 4),
    Reg("load_day_kwh", _s(33179), "u16", 0.1, 4),
]

SOLIS_STATUS = {0: "Waiting", 1: "Open loop operation", 2: "Soft start", 3: "Generating", 4000: "Fault/standby (4000+)",
                4100: "Grid surge", 4110: "Fan fault", 4116: "Grid off", 4117: "Grid overvoltage", 4118: "Grid undervoltage",
                4120: "Grid overfrequency", 4121: "Grid underfrequency", 8010: "Standby", 8011: "Initializing"}
# bit of "Fault status 01" (33116) -> (Solis display code, text); other fault words fall back to solis.fault<N>.b<bit>
SOLIS_FAULT1 = {0: ("NO-GRID", "No grid"), 1: ("OV-G-V", "Grid overvoltage"), 2: ("UN-G-V", "Grid undervoltage"),
                3: ("OV-G-F", "Grid overfrequency"), 4: ("UN-G-F", "Grid underfrequency"), 5: ("G-IMP", "Grid impedance too large"),
                6: ("G-PHASE", "Grid voltage unbalanced"), 7: ("GRID-INTF", "Grid frequency jitter / interference"),
                8: ("OV-G-I", "Grid overcurrent"), 9: ("DC-INTF", "Grid current sampling error"), 10: ("OV-BUS", "DC bus overvoltage"),
                11: ("UN-BUS", "DC bus undervoltage"), 12: ("OV-TEM", "Inverter overtemperature"), 13: ("PV ISO-PRO", "Insulation fault"),
                14: ("ILeak-PRO", "Leakage current"), 15: ("ARC-FAULT", "Arc fault")}


def finalize_solis(v: dict, r: Reading) -> Reading:
    r.pv_w = v.get("pv_w")
    r.ac_w = v.get("ac_w")
    r.reactive_var = v.get("reactive_var")
    r.grid_w = v.get("meter_w")
    r.load_w = v.get("load_w")
    r.temp_c = v.get("temp_c")
    r.grid_hz = v.get("grid_hz")
    r.grid_v = v.get("grid_v_a")
    r.soc, r.soh = v.get("soc"), v.get("soh")
    r.batt_v, r.batt_a = v.get("batt_v"), v.get("batt_a")
    bw = v.get("batt_w")
    if bw is not None:
        r.batt_w = bw if int(v.get("batt_dir", 0)) == 0 else -bw
    r.energy_day_kwh = v.get("energy_day_kwh")
    r.energy_total_kwh = v.get("energy_total_kwh")
    r.grid_import_day_kwh = v.get("grid_import_day_kwh")
    r.grid_export_day_kwh = v.get("grid_export_day_kwh")
    r.batt_charge_day_kwh = v.get("batt_charge_day_kwh")
    r.batt_discharge_day_kwh = v.get("batt_discharge_day_kwh")
    r.load_day_kwh = v.get("load_day_kwh")
    st = int(v.get("status", -1))
    r.status = SOLIS_STATUS.get(st, f"status {st}")
    for i in range(1, 5):
        pv_v, pv_a = v.get(f"pv{i}_v"), v.get(f"pv{i}_a")
        if pv_v:
            r.strings[f"pv{i}"] = {"v": pv_v, "a": pv_a, "w": round(pv_v * pv_a, 1)}
    r.alarms += coded_alarms(v.get("fault1"), "solis", SOLIS_FAULT1, "solis.fault1")
    for k in ("fault2", "fault3", "fault4", "fault5"):
        r.alarms += bit_alarms(v.get(k), f"solis.{k}")
    r.extra.update(backup_w=v.get("backup_w"), working_status=v.get("working_status"))
    return r


# ---------------------------------------------------------------------------
# SUNGROW SH (hybrid) / SG (string) - Modbus TCP 502 (WiNet-S) unit 1, FC04. Doc numbers are 1-based.
# ---------------------------------------------------------------------------
SUNGROW: list[Reg] = [
    Reg("energy_day_kwh", _s(5003), "u16", 0.1, 4),
    Reg("energy_total_kwh", _s(5004), "u32", 1.0, 4, "little"),
    Reg("temp_c", _s(5008), "i16", 0.1, 4),
    Reg("pv1_v", _s(5011), "u16", 0.1, 4), Reg("pv1_a", _s(5012), "u16", 0.1, 4),
    Reg("pv2_v", _s(5013), "u16", 0.1, 4), Reg("pv2_a", _s(5014), "u16", 0.1, 4),
    Reg("pv_w", _s(5017), "u32", 1.0, 4, "little"),
    Reg("grid_v_a", _s(5019), "u16", 0.1, 4),
    Reg("ac_w", _s(5031), "u32", 1.0, 4, "little"),
    Reg("grid_hz", _s(5036), "u16", 0.1, 4),
    Reg("status", _s(5038), "u16", 1.0, 4),
    Reg("fault_code", _s(5045), "u16", 1.0, 4),        # 3-digit fault code as shown on iSolarCloud (0 = none)
    # hybrid section
    Reg("running_state", _s(13001), "u16", 1.0, 4),
    Reg("load_w", _s(13008), "i32", 1.0, 4, "little"),
    Reg("export_w", _s(13010), "i32", 1.0, 4, "little"),      # + export / - import
    Reg("batt_charge_day_kwh", _s(13012), "u16", 0.1, 4),
    Reg("batt_v", _s(13020), "u16", 0.1, 4),
    Reg("batt_a", _s(13021), "u16", 0.1, 4),
    Reg("batt_w_abs", _s(13022), "u16", 1.0, 4),
    Reg("soc", _s(13023), "u16", 0.1, 4),
    Reg("soh", _s(13024), "u16", 0.1, 4),
    Reg("batt_temp_c", _s(13025), "i16", 0.1, 4),
    Reg("batt_discharge_day_kwh", _s(13026), "u16", 0.1, 4),
    Reg("grid_import_day_kwh", _s(13036), "u16", 0.1, 4),
    Reg("grid_export_day_kwh", _s(13045), "u16", 0.1, 4),
    Reg("load_day_kwh", _s(13017), "u16", 0.1, 4),
]

SUNGROW_STATUS = {0x0: "Run", 0x8000: "Stop", 0x1300: "Key stop", 0x1500: "Emergency stop", 0x1400: "Standby",
                  0x1200: "Initial standby", 0x1600: "Starting", 0x9100: "Alarm run", 0x8100: "Derating run",
                  0x8200: "Dispatch run", 0x5500: "Fault", 0x2500: "Communicate fault"}


def finalize_sungrow(v: dict, r: Reading) -> Reading:
    r.pv_w, r.ac_w = v.get("pv_w"), v.get("ac_w")
    r.temp_c, r.grid_hz, r.grid_v = v.get("temp_c"), v.get("grid_hz"), v.get("grid_v_a")
    r.energy_day_kwh, r.energy_total_kwh = v.get("energy_day_kwh"), v.get("energy_total_kwh")
    r.load_w = v.get("load_w")
    if v.get("export_w") is not None:
        r.grid_w = -v["export_w"]
    rs = int(v.get("running_state", 0))
    bw = v.get("batt_w_abs")
    if bw is not None:
        if rs & (1 << 1):      # charging
            r.batt_w = bw
        elif rs & (1 << 2):    # discharging
            r.batt_w = -bw
        else:
            r.batt_w = 0.0
    r.soc, r.soh = v.get("soc"), v.get("soh")
    r.batt_v, r.batt_a, r.batt_temp_c = v.get("batt_v"), v.get("batt_a"), v.get("batt_temp_c")
    r.batt_charge_day_kwh, r.batt_discharge_day_kwh = v.get("batt_charge_day_kwh"), v.get("batt_discharge_day_kwh")
    r.grid_import_day_kwh, r.grid_export_day_kwh = v.get("grid_import_day_kwh"), v.get("grid_export_day_kwh")
    r.load_day_kwh = v.get("load_day_kwh")
    st = int(v.get("status", -1))
    r.status = SUNGROW_STATUS.get(st, f"status 0x{st:04X}")
    fc = int(v.get("fault_code", 0) or 0)
    if fc:
        r.alarms.append(Alarm(code=f"sungrow.{fc:03d}", severity="fault"))
    elif st in (0x5500, 0x2500):
        r.alarms.append(Alarm(code=f"sungrow.state.{st:04X}", message=r.status, severity="fault"))
    for i in (1, 2):
        pv_v, pv_a = v.get(f"pv{i}_v"), v.get(f"pv{i}_a")
        if pv_v:
            r.strings[f"pv{i}"] = {"v": pv_v, "a": pv_a, "w": round(pv_v * pv_a, 1)}
    return r


# ---------------------------------------------------------------------------
# SOLAX X1/X3 hybrid (Modbus TCP 502 via Pocket LAN/WiFi 3.0, unit 1, FC04 input registers, 0-based)
# ---------------------------------------------------------------------------
SOLAX: list[Reg] = [
    Reg("grid_v", 0x0000, "u16", 0.1, 4),
    Reg("grid_a", 0x0001, "i16", 0.1, 4),
    Reg("ac_w", 0x0002, "i16", 1.0, 4),
    Reg("pv1_v", 0x0003, "u16", 0.1, 4), Reg("pv2_v", 0x0004, "u16", 0.1, 4),
    Reg("pv1_a", 0x0005, "u16", 0.1, 4), Reg("pv2_a", 0x0006, "u16", 0.1, 4),
    Reg("grid_hz", 0x0007, "u16", 0.01, 4),
    Reg("temp_c", 0x0008, "i16", 1.0, 4),
    Reg("run_mode", 0x0009, "u16", 1.0, 4),
    Reg("pv1_w", 0x000A, "u16", 1.0, 4), Reg("pv2_w", 0x000B, "u16", 1.0, 4),
    Reg("batt_v", 0x0014, "i16", 0.1, 4),
    Reg("batt_a", 0x0015, "i16", 0.1, 4),
    Reg("batt_w", 0x0016, "i16", 1.0, 4),          # + charge / - discharge
    Reg("batt_temp_c", 0x0018, "i16", 1.0, 4),
    Reg("soc", 0x001C, "u16", 1.0, 4),
    Reg("feedin_w", 0x0046, "i32", 1.0, 4, "little"),   # + export / - import
    # house load is not a register on Gen3/Gen4 firmware -> derived by Reading.derive_missing()
    Reg("energy_day_kwh", 0x0050, "u16", 0.1, 4),
    Reg("energy_total_kwh", 0x0052, "u32", 0.1, 4, "little"),
]
SOLAX_MODE = {0: "Waiting", 1: "Checking", 2: "Normal", 3: "Fault", 4: "Permanent fault", 5: "Update", 6: "EPS check",
              7: "EPS", 8: "Self test", 9: "Idle", 10: "Standby"}


def finalize_solax(v: dict, r: Reading) -> Reading:
    r.ac_w = v.get("ac_w")
    r.pv_w = (v.get("pv1_w") or 0) + (v.get("pv2_w") or 0)
    r.grid_v, r.grid_hz, r.temp_c = v.get("grid_v"), v.get("grid_hz"), v.get("temp_c")
    r.batt_v, r.batt_a, r.batt_w, r.batt_temp_c, r.soc = v.get("batt_v"), v.get("batt_a"), v.get("batt_w"), v.get("batt_temp_c"), v.get("soc")
    if v.get("feedin_w") is not None:
        r.grid_w = -v["feedin_w"]
    r.energy_day_kwh, r.energy_total_kwh = v.get("energy_day_kwh"), v.get("energy_total_kwh")
    m = int(v.get("run_mode", -1))
    r.status = SOLAX_MODE.get(m, f"mode {m}")
    if m in (3, 4):
        r.alarms.append(Alarm(code=f"solax.mode.{m}", message=r.status, severity="fault"))
    for i in (1, 2):
        if v.get(f"pv{i}_v"):
            r.strings[f"pv{i}"] = {"v": v[f"pv{i}_v"], "a": v.get(f"pv{i}_a"), "w": v.get(f"pv{i}_w")}
    return r


# ---------------------------------------------------------------------------
# DEYE single-phase hybrid SUN-xK-SG0xLP1 (holding regs FC03, 0-based as in the Deye doc)
# ---------------------------------------------------------------------------
DEYE_1P: list[Reg] = [
    Reg("energy_day_kwh", 108, "u16", 0.1),
    Reg("energy_total_kwh", 96, "u32", 0.1, 3, "little"),
    Reg("batt_charge_day_kwh", 70, "u16", 0.1),
    Reg("batt_discharge_day_kwh", 71, "u16", 0.1),
    Reg("grid_import_day_kwh", 76, "u16", 0.1),
    Reg("grid_export_day_kwh", 77, "u16", 0.1),
    Reg("load_day_kwh", 84, "u16", 0.1),
    Reg("grid_v", 150, "u16", 0.1),
    Reg("grid_w", 169, "i16", 1.0),          # + import / - export (Deye: "grid power")
    Reg("load_w", 178, "i16", 1.0),
    Reg("pv1_w", 186, "u16", 1.0), Reg("pv2_w", 187, "u16", 1.0),
    Reg("batt_temp_c", 182, "u16", 0.1),      # value - 100 after scaling (Deye offset)
    Reg("batt_v", 183, "u16", 0.01),
    Reg("soc", 184, "u16", 1.0),
    Reg("batt_w", 190, "i16", 1.0),          # + discharge / - charge (Deye convention)
    Reg("batt_a", 191, "i16", 0.01),
    Reg("grid_hz", 79, "u16", 0.01),
    Reg("temp_c", 90, "u16", 0.1),
    Reg("status", 59, "u16", 1.0),
    Reg("fault1", 103, "u16", 1.0), Reg("fault2", 104, "u16", 1.0), Reg("fault3", 105, "u16", 1.0), Reg("fault4", 106, "u16", 1.0),
]

# DEYE three-phase hybrid SUN-xK-SG0xLP3 / SG01HP3
DEYE_3P: list[Reg] = [
    Reg("energy_day_kwh", 529, "u16", 0.1),
    Reg("energy_total_kwh", 534, "u32", 0.1, 3, "little"),
    Reg("batt_charge_day_kwh", 514, "u16", 0.1),
    Reg("batt_discharge_day_kwh", 515, "u16", 0.1),
    Reg("grid_import_day_kwh", 520, "u16", 0.1),
    Reg("grid_export_day_kwh", 521, "u16", 0.1),
    Reg("load_day_kwh", 526, "u16", 0.1),
    Reg("status", 500, "u16", 1.0),
    Reg("temp_c", 541, "u16", 0.1),
    Reg("fault1", 553, "u16", 1.0), Reg("fault2", 554, "u16", 1.0), Reg("fault3", 555, "u16", 1.0), Reg("fault4", 556, "u16", 1.0),
    Reg("batt_temp_c", 586, "u16", 0.1),
    Reg("batt_v", 587, "u16", 0.01),
    Reg("soc", 588, "u16", 1.0),
    Reg("batt_w", 590, "i16", 1.0),          # + discharge / - charge
    Reg("batt_a", 591, "i16", 0.01),
    Reg("grid_v", 598, "u16", 0.1),
    Reg("grid_w", 625, "i16", 1.0),          # total grid power + import / - export
    Reg("grid_hz", 609, "u16", 0.01),
    Reg("load_w", 653, "i16", 1.0),
    Reg("pv1_v", 676, "u16", 0.1), Reg("pv1_a", 677, "u16", 0.1),
    Reg("pv2_v", 678, "u16", 0.1), Reg("pv2_a", 679, "u16", 0.1),
    Reg("pv1_w", 672, "u16", 1.0), Reg("pv2_w", 673, "u16", 1.0),
]
DEYE_STATUS = {0: "Standby", 1: "Self-check", 2: "Normal", 3: "Alarm", 4: "Fault"}


def finalize_deye(v: dict, r: Reading) -> Reading:
    r.pv_w = (v.get("pv1_w") or 0) + (v.get("pv2_w") or 0)
    r.grid_w, r.load_w = v.get("grid_w"), v.get("load_w")
    if v.get("batt_w") is not None:
        r.batt_w = -v["batt_w"]                          # flip to relay convention
    r.soc, r.batt_v, r.batt_a = v.get("soc"), v.get("batt_v"), v.get("batt_a")
    if v.get("batt_temp_c") is not None:
        r.batt_temp_c = v["batt_temp_c"] - 100.0
    if v.get("temp_c") is not None:
        r.temp_c = v["temp_c"] - 100.0
    r.grid_v, r.grid_hz = v.get("grid_v"), v.get("grid_hz")
    r.energy_day_kwh, r.energy_total_kwh = v.get("energy_day_kwh"), v.get("energy_total_kwh")
    r.batt_charge_day_kwh, r.batt_discharge_day_kwh = v.get("batt_charge_day_kwh"), v.get("batt_discharge_day_kwh")
    r.grid_import_day_kwh, r.grid_export_day_kwh, r.load_day_kwh = v.get("grid_import_day_kwh"), v.get("grid_export_day_kwh"), v.get("load_day_kwh")
    st = int(v.get("status", -1))
    r.status = DEYE_STATUS.get(st, f"status {st}")
    # Deye: fault word k bit n  ->  F(16*k + n + 1)   (F01..F64)
    for i, k in enumerate(("fault1", "fault2", "fault3", "fault4")):
        r.alarms += numbered_alarms(v.get(k), "deye", "F", 16 * i + 1)
    for i in (1, 2):
        if v.get(f"pv{i}_v"):
            r.strings[f"pv{i}"] = {"v": v[f"pv{i}_v"], "a": v.get(f"pv{i}_a"), "w": v.get(f"pv{i}_w")}
    return r


# ---------------------------------------------------------------------------
# SOFAR HYD-ES / HYD-KTL G3 (holding FC03, 0-based). Minimal set; extend from wills106 plugin_sofar.py.
# ---------------------------------------------------------------------------
SOFAR: list[Reg] = [
    Reg("status", 0x0404, "u16", 1.0),
    Reg("fault1", 0x0405, "u16", 1.0), Reg("fault2", 0x0406, "u16", 1.0),
    Reg("grid_hz", 0x0484, "u16", 0.01),
    Reg("ac_w", 0x0485, "i16", 10.0),
    Reg("grid_w", 0x0488, "i16", 10.0),           # + export / - import (Sofar "ActivePower_PCC")
    Reg("grid_v", 0x048D, "u16", 0.1),
    Reg("load_w", 0x04AF, "i16", 10.0),
    Reg("pv1_v", 0x0584, "u16", 0.1), Reg("pv1_a", 0x0585, "u16", 0.01), Reg("pv1_w", 0x0586, "u16", 10.0),
    Reg("pv2_v", 0x0587, "u16", 0.1), Reg("pv2_a", 0x0588, "u16", 0.01), Reg("pv2_w", 0x0589, "u16", 10.0),
    Reg("batt_v", 0x0604, "u16", 0.1), Reg("batt_a", 0x0605, "i16", 0.01), Reg("batt_w", 0x0606, "i16", 10.0),
    Reg("batt_temp_c", 0x0607, "i16", 1.0), Reg("soc", 0x0608, "u16", 1.0), Reg("soh", 0x0609, "u16", 1.0),
    Reg("energy_day_kwh", 0x0684, "u16", 0.01),
    Reg("energy_total_kwh", 0x0686, "u32", 0.1),
    Reg("load_day_kwh", 0x0688, "u16", 0.01),
    Reg("grid_import_day_kwh", 0x068C, "u16", 0.01),
    Reg("grid_export_day_kwh", 0x0690, "u16", 0.01),
    Reg("batt_charge_day_kwh", 0x0694, "u16", 0.01),
    Reg("batt_discharge_day_kwh", 0x0698, "u16", 0.01),
    Reg("temp_c", 0x0418, "i16", 1.0),
]
SOFAR_STATUS = {0: "Waiting", 1: "Detection", 2: "Grid-connected", 3: "Emergency power supply", 4: "Recoverable fault",
                5: "Permanent fault", 6: "Upgrade", 7: "Self-charging"}


def finalize_sofar(v: dict, r: Reading) -> Reading:
    r.ac_w = v.get("ac_w")
    r.pv_w = (v.get("pv1_w") or 0) + (v.get("pv2_w") or 0)
    if v.get("grid_w") is not None:
        r.grid_w = -v["grid_w"]
    r.load_w = v.get("load_w")
    if v.get("batt_w") is not None:
        r.batt_w = -v["batt_w"]                  # Sofar: + discharge
    r.soc, r.soh, r.batt_v, r.batt_a, r.batt_temp_c = v.get("soc"), v.get("soh"), v.get("batt_v"), v.get("batt_a"), v.get("batt_temp_c")
    r.grid_v, r.grid_hz, r.temp_c = v.get("grid_v"), v.get("grid_hz"), v.get("temp_c")
    r.energy_day_kwh, r.energy_total_kwh = v.get("energy_day_kwh"), v.get("energy_total_kwh")
    r.load_day_kwh = v.get("load_day_kwh")
    r.grid_import_day_kwh, r.grid_export_day_kwh = v.get("grid_import_day_kwh"), v.get("grid_export_day_kwh")
    r.batt_charge_day_kwh, r.batt_discharge_day_kwh = v.get("batt_charge_day_kwh"), v.get("batt_discharge_day_kwh")
    st = int(v.get("status", -1))
    r.status = SOFAR_STATUS.get(st, f"status {st}")
    if st in (4, 5):
        r.alarms.append(Alarm(code=f"sofar.state.{st}", message=r.status, severity="fault"))
    # Sofar: fault word 1 bit n -> ID(n+1), fault word 2 bit n -> ID(n+17)
    r.alarms += numbered_alarms(v.get("fault1"), "sofar", "ID", 1)
    r.alarms += numbered_alarms(v.get("fault2"), "sofar", "ID", 17)
    for i in (1, 2):
        if v.get(f"pv{i}_v"):
            r.strings[f"pv{i}"] = {"v": v[f"pv{i}_v"], "a": v.get(f"pv{i}_a"), "w": v.get(f"pv{i}_w")}
    return r


# ---------------------------------------------------------------------------
# SIGENERGY local Modbus-TCP (installer must enable; plant = unit 247, inverters unit 1..n). FC04, 0-based.
# Plant-level registers (Sigenergy Modbus Protocol V2.x, as used by TypQxQ / sigenergy2mqtt).
# ---------------------------------------------------------------------------
SIGEN_LOCAL: list[Reg] = [
    Reg("system_time", 30000, "u32", 1.0, 4),
    Reg("ems_work_mode", 30003, "u16", 1.0, 4),
    Reg("grid_sensor_status", 30004, "u16", 1.0, 4),
    Reg("grid_w", 30005, "i32", 1.0, 4),            # kW * 1000 -> W; + import / - export
    Reg("grid_var", 30007, "i32", 1.0, 4),
    Reg("on_off_grid", 30009, "u16", 1.0, 4),
    Reg("ess_max_charge_w", 30010, "u32", 1.0, 4),
    Reg("ess_max_discharge_w", 30012, "u32", 1.0, 4),
    Reg("soc", 30014, "u16", 0.1, 4),
    Reg("pv_w", 30015, "u32", 1.0, 4),
    Reg("batt_w", 30037, "i32", 1.0, 4),            # + charge / - discharge
    Reg("ess_available_charge_kwh", 30039, "u32", 0.01, 4),
    Reg("running_state", 30051, "u16", 1.0, 4),
]
SIGEN_EMS_MODE = {0: "Max self consumption", 1: "AI mode", 2: "TOU", 7: "Remote EMS"}
SIGEN_RUN = {0: "Standby", 1: "Running", 2: "Fault", 3: "Shutdown"}


def finalize_sigen_local(v: dict, r: Reading) -> Reading:
    # plant registers publish kW*1000 (== W) for power, so scale 1.0
    r.grid_w = v.get("grid_w")
    r.pv_w = v.get("pv_w")
    r.batt_w = v.get("batt_w")
    r.soc = v.get("soc")
    r.reactive_var = v.get("grid_var")
    rs = int(v.get("running_state", -1))
    r.status = SIGEN_RUN.get(rs, f"state {rs}")
    if rs == 2:
        r.alarms.append(Alarm(code="sigen.plant.fault", message="plant running state = fault", severity="fault"))
    r.extra.update(ems_mode=SIGEN_EMS_MODE.get(int(v.get("ems_work_mode", -1)), v.get("ems_work_mode")),
                   on_grid=int(v.get("on_off_grid", 0)) == 0,
                   ess_max_charge_w=v.get("ess_max_charge_w"), ess_max_discharge_w=v.get("ess_max_discharge_w"),
                   ess_available_charge_kwh=v.get("ess_available_charge_kwh"))
    return r


# ---------------------------------------------------------------------------
Finalizer = Callable[[dict, Reading], Reading]

MAPS: dict[str, tuple[list[Reg], Finalizer, dict]] = {
    # key: (registers, finalizer, defaults {unit, port})
    "huawei":      (HUAWEI,      finalize_huawei,      {"unit": 1,   "port": 502}),
    "solis":       (SOLIS,       finalize_solis,       {"unit": 1,   "port": 502}),
    "sungrow":     (SUNGROW,     finalize_sungrow,     {"unit": 1,   "port": 502}),
    "solax":       (SOLAX,       finalize_solax,       {"unit": 1,   "port": 502}),
    "deye_1p":     (DEYE_1P,     finalize_deye,        {"unit": 1,   "port": 502}),
    "deye_3p":     (DEYE_3P,     finalize_deye,        {"unit": 1,   "port": 502}),
    "sofar":       (SOFAR,       finalize_sofar,       {"unit": 1,   "port": 502}),
    "sigen_local": (SIGEN_LOCAL, finalize_sigen_local, {"unit": 247, "port": 502}),
}
