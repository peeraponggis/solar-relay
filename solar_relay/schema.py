"""Normalized data model shared by every adapter and output.

Sign conventions (fixed for the whole relay, adapters must convert):
  * ``pv_w``      >= 0  DC / PV production
  * ``grid_w``    > 0 import from grid, < 0 export to grid
  * ``batt_w``    > 0 charging,      < 0 discharging
  * ``load_w``    >= 0  household / plant consumption
  * ``ac_w``      inverter AC active power (> 0 producing)
Energies are kWh, temperatures degC, SOC in percent 0-100.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Alarm:
    code: str                      # vendor alarm / fault code (string so bitfields + ids both fit)
    message: str = ""              # human-readable text if the vendor supplies one
    severity: str = "warning"      # info | warning | fault
    active: bool = True            # False = recovery event
    raised_at: Optional[datetime] = None
    advice: str = ""               # repair guidance, filled by alarm_catalog.enrich_alarm
    category: str = ""             # grid_overvoltage | insulation | leakage | overtemp | arc | battery | comm | ...
    raw: dict[str, Any] = field(default_factory=dict)


NUMERIC_FIELDS = (
    "pv_w", "ac_w", "grid_w", "load_w", "batt_w", "reactive_var",
    "soc", "soh", "batt_v", "batt_a", "batt_temp_c",
    "energy_day_kwh", "energy_total_kwh", "grid_import_day_kwh", "grid_export_day_kwh",
    "batt_charge_day_kwh", "batt_discharge_day_kwh", "load_day_kwh",
    "grid_v", "grid_hz", "temp_c",
)


@dataclass
class Reading:
    """One snapshot of one device (inverter, plant, meter)."""

    device_id: str                 # stable id used for topics / measurement tags
    brand: str                     # huawei | sigen | solis | solaredge | fronius | sma | sungrow | goodwe | solax | delta | deye | sofar | ...
    source: str                    # adapter name that produced it (sunspec, modbus, solarman, sigen_openapi, cloud:*)
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # power (W)
    pv_w: Optional[float] = None
    ac_w: Optional[float] = None
    grid_w: Optional[float] = None
    load_w: Optional[float] = None
    batt_w: Optional[float] = None
    reactive_var: Optional[float] = None

    # battery
    soc: Optional[float] = None
    soh: Optional[float] = None
    batt_v: Optional[float] = None
    batt_a: Optional[float] = None
    batt_temp_c: Optional[float] = None

    # energy (kWh)
    energy_day_kwh: Optional[float] = None
    energy_total_kwh: Optional[float] = None
    grid_import_day_kwh: Optional[float] = None
    grid_export_day_kwh: Optional[float] = None
    batt_charge_day_kwh: Optional[float] = None
    batt_discharge_day_kwh: Optional[float] = None
    load_day_kwh: Optional[float] = None

    # AC side
    grid_v: Optional[float] = None
    grid_hz: Optional[float] = None
    temp_c: Optional[float] = None
    status: Optional[str] = None       # vendor status text / code
    online: bool = True

    # per-string DC data: {"pv1": {"v": .., "a": .., "w": ..}, ...}
    strings: dict[str, dict[str, float]] = field(default_factory=dict)
    # anything vendor specific you still want to keep (goes to InfluxDB fields / MQTT json)
    extra: dict[str, Any] = field(default_factory=dict)
    alarms: list[Alarm] = field(default_factory=list)

    # ---- helpers -------------------------------------------------------
    def numeric_fields(self) -> dict[str, float]:
        """Only the non-null numeric metrics (what time-series outputs care about)."""
        out: dict[str, float] = {}
        for name in NUMERIC_FIELDS:
            v = getattr(self, name)
            if v is not None:
                out[name] = float(v)
        for sname, sv in self.strings.items():
            for k, v in sv.items():
                if v is not None:
                    out[f"{sname}_{k}"] = float(v)
        return out

    def derive_missing(self) -> Reading:
        """Fill load or grid from the power balance when the vendor omits one of them.

        Balance used:  load = pv + grid_import - batt_charge  (W, relay sign convention)
        """
        pv = self.pv_w if self.pv_w is not None else self.ac_w
        if self.load_w is None and pv is not None and self.grid_w is not None:
            self.load_w = max(0.0, pv + self.grid_w - (self.batt_w or 0.0))
        elif self.grid_w is None and pv is not None and self.load_w is not None:
            self.grid_w = self.load_w - pv + (self.batt_w or 0.0)
        return self

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        for a in d["alarms"]:
            if a.get("raised_at") is not None:
                a["raised_at"] = a["raised_at"].isoformat()
        return d


def clamp_soc(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return max(0.0, min(100.0, float(v)))
