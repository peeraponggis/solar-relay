"""GoodWe local adapter using the `goodwe` library (UDP 8899 / Modbus TCP 502 on newer WiFi kits).

options:
  host, family (ET | ES | DT | auto), port(8899), timeout(2), retries(3)
Works for ET/EH/BH/BT/EHB, ES/EM/BP, DT/MS/D-NS/XS families.
"""
from __future__ import annotations

from typing import Any

from ..schema import Alarm, Reading, clamp_soc
from .base import BaseAdapter


class GoodWeLocalAdapter(BaseAdapter):
    name = "goodwe"
    default_brand = "goodwe"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 30, **options: Any):
        super().__init__(device_id, brand or "goodwe", interval_s, **options)
        self.host = options["host"]
        self.family = options.get("family")
        self.port = int(options.get("port", 8899))
        self.timeout = int(options.get("timeout", 2))
        self.retries = int(options.get("retries", 3))
        self._inv = None

    async def start(self) -> None:
        import goodwe
        if self.family and self.family.lower() != "auto":
            self._inv = await goodwe.connect(self.host, port=self.port, family=self.family.upper(),
                                             timeout=self.timeout, retries=self.retries)
        else:
            self._inv = await goodwe.connect(self.host, port=self.port, timeout=self.timeout, retries=self.retries)

    async def read(self) -> list[Reading]:
        if self._inv is None:
            await self.start()
        d = await self._inv.read_runtime_data()
        r = self.new_reading()
        g = d.get
        r.pv_w = g("ppv")
        r.ac_w = g("active_power") if g("active_power") is not None else g("pgrid")
        r.load_w = g("house_consumption") or g("load_p1")
        meter = g("meter_active_power_total") if g("meter_active_power_total") is not None else g("active_power_total")
        if meter is not None:
            r.grid_w = -float(meter)        # GoodWe meter: + export
        bp = g("pbattery1")
        if bp is not None:
            r.batt_w = -float(bp)           # GoodWe: + discharge
        r.soc = clamp_soc(g("battery_soc"))
        r.soh = g("battery_soh")
        r.batt_v, r.batt_a, r.batt_temp_c = g("vbattery1"), g("ibattery1"), g("battery_temperature")
        r.grid_v, r.grid_hz, r.temp_c = g("vgrid"), g("fgrid"), g("temperature") or g("temperature2")
        r.energy_day_kwh, r.energy_total_kwh = g("e_day"), g("e_total")
        r.grid_import_day_kwh, r.grid_export_day_kwh = g("e_day_imp"), g("e_day_exp")
        r.batt_charge_day_kwh, r.batt_discharge_day_kwh = g("e_bat_charge_day"), g("e_bat_discharge_day")
        r.load_day_kwh = g("e_load_day")
        r.status = str(g("work_mode_label") or g("work_mode") or "")
        for i in (1, 2, 3, 4):
            if g(f"vpv{i}") is not None:
                r.strings[f"pv{i}"] = {"v": g(f"vpv{i}"), "a": g(f"ipv{i}"), "w": g(f"ppv{i}")}
        for key in ("error_codes", "errors", "diagnose_result_label", "warning_code"):
            val = g(key)
            if val:
                r.alarms.append(Alarm(code=f"goodwe.{key}", message=str(val), severity="fault" if "error" in key else "warning"))
        r.extra.update(model=getattr(self._inv, "model_name", None), sn=getattr(self._inv, "serial_number", None))
        return [r]
