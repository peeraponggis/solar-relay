"""SunSpec Modbus adapter (pysunspec2) - one adapter for every SunSpec-compliant inverter.

Covers: SolarEdge (unit 1, meters follow), Fronius (unit 1 inverter, 240 meter; enable "SunSpec Modbus"
int+SF or float), SMA (unit 3 for SunSpec on Sunny Boy/Tripower; enable Modbus TCP in the web UI),
Delta RPI/M-series, SolaX (X3-Hybrid G4 with SunSpec on), GoodWe (ET/EH with SunSpec), Solis (S5/S6
via SunSpec-capable loggers), Sungrow (SG string models with SunSpec map), Huawei (only a few models).

options:
  host, port(502), unit(1), timeout(5)
  extra_units: [240]      additional unit ids to scan (e.g. Fronius meter)

Models parsed: 1 common, 101-103 / 111-113 inverter, 160 MPPT, 201-204 / 211-214 meter,
124 storage control, 802 battery (SOC).
"""
from __future__ import annotations

import logging
from typing import Any

from ..schema import Alarm, Reading, clamp_soc
from .base import BaseAdapter

log = logging.getLogger("solar_relay.sunspec")

INVERTER_MODELS = {101, 102, 103, 111, 112, 113}
METER_MODELS = {201, 202, 203, 204, 211, 212, 213, 214}
INV_STATES = {1: "Off", 2: "Sleeping", 3: "Starting", 4: "MPPT", 5: "Throttled", 6: "Shutting down", 7: "Fault", 8: "Standby"}
EVT1_BITS = {0: "Ground fault", 1: "DC over voltage", 2: "AC disconnect", 3: "DC disconnect", 4: "Grid disconnect",
             5: "Cabinet open", 6: "Manual shutdown", 7: "Over temperature", 8: "Over frequency", 9: "Under frequency",
             10: "AC over voltage", 11: "AC under voltage", 12: "Blown string fuse", 13: "Under temperature",
             14: "Memory loss", 15: "HW test failure"}


def _val(model: Any, point: str) -> float | None:
    """Return scaled value of a point or None if absent / not implemented."""
    p = getattr(model, point, None)
    if p is None:
        return None
    try:
        v = p.cvalue if p.cvalue is not None else p.value
    except Exception:  # noqa: BLE001
        return None
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class SunSpecAdapter(BaseAdapter):
    name = "sunspec"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 30, **options: Any):
        super().__init__(device_id, brand, interval_s, **options)
        self.host = options["host"]
        self.port = int(options.get("port", 502))
        self.unit = int(options.get("unit", 1))
        self.timeout = float(options.get("timeout", 5))
        self.extra_units = [int(u) for u in options.get("extra_units", [])]
        self._devices: list[Any] = []

    async def start(self) -> None:
        await self.run_blocking(self._connect)

    def _connect(self) -> None:
        import sunspec2.modbus.client as client
        self._devices = []
        for unit in [self.unit, *self.extra_units]:
            d = client.SunSpecModbusClientDeviceTCP(slave_id=unit, ipaddr=self.host, ipport=self.port, timeout=self.timeout)
            d.scan()
            self._devices.append(d)
            log.info("[%s] SunSpec unit %d models: %s", self.device_id, unit, sorted(d.models.keys()))

    async def stop(self) -> None:
        for d in self._devices:
            try:
                d.close()
            except Exception:  # noqa: BLE001
                pass

    async def read(self) -> list[Reading]:
        if not self._devices:
            await self.start()
        return await self.run_blocking(self._read_sync)

    def _read_sync(self) -> list[Reading]:
        r = self.new_reading()
        meter_seen = False
        for d in self._devices:
            for mid, models in d.models.items():
                if not isinstance(mid, int):
                    continue
                for m in models:
                    m.read()
                    if mid == 1:
                        r.extra.update(manufacturer=getattr(m.Mn, "value", None), model=getattr(m.Md, "value", None),
                                       sn=getattr(m.SN, "value", None))
                        if not self.brand and getattr(m.Mn, "value", None):
                            r.brand = str(m.Mn.value).strip().lower().split()[0]
                    elif mid in INVERTER_MODELS:
                        r.ac_w = _val(m, "W")
                        r.pv_w = _val(m, "DCW") if _val(m, "DCW") is not None else r.ac_w
                        r.reactive_var = _val(m, "VAr")
                        r.grid_hz = _val(m, "Hz")
                        r.grid_v = _val(m, "PhVphA") or _val(m, "PPVphAB")
                        r.temp_c = _val(m, "TmpCab") or _val(m, "TmpSnk")
                        wh = _val(m, "WH")
                        if wh is not None:
                            r.energy_total_kwh = wh / 1000.0
                        st = _val(m, "St")
                        if st is not None:
                            r.status = INV_STATES.get(int(st), f"state {int(st)}")
                            if int(st) == 7:
                                r.alarms.append(Alarm(code="sunspec.St.7", message="Fault", severity="fault"))
                        evt = _val(m, "Evt1")
                        if evt:
                            for bit, text in EVT1_BITS.items():
                                if int(evt) & (1 << bit):
                                    r.alarms.append(Alarm(code=f"sunspec.Evt1.b{bit}", message=text, severity="fault"))
                        for k in ("EvtVnd1", "EvtVnd2", "EvtVnd3", "EvtVnd4"):
                            ev = _val(m, k)
                            if ev:
                                r.alarms.append(Alarm(code=f"sunspec.{k}.0x{int(ev):08X}", message="vendor event bits", severity="warning"))
                    elif mid == 160:  # MPPT modules
                        try:
                            total = 0.0
                            for i, mod in enumerate(m.module, start=1):
                                w = _val(mod, "DCW")
                                r.strings[f"pv{i}"] = {"v": _val(mod, "DCV"), "a": _val(mod, "DCA"), "w": w}
                                total += w or 0.0
                            if total:
                                r.pv_w = total
                        except Exception:  # noqa: BLE001
                            pass
                    elif mid in METER_MODELS and not meter_seen:
                        meter_seen = True
                        w = _val(m, "W")
                        if w is not None:
                            # SunSpec meter: +W = import from grid when installed at the grid connection point
                            r.grid_w = w if not self.options.get("meter_inverted") else -w
                        exp, imp = _val(m, "TotWhExp"), _val(m, "TotWhImp")
                        r.extra.update(meter_export_total_kwh=(exp or 0) / 1000.0, meter_import_total_kwh=(imp or 0) / 1000.0)
                    elif mid == 802:
                        r.soc = clamp_soc(_val(m, "SoC"))
                        r.soh = _val(m, "SoH")
                        r.batt_v = _val(m, "V")
                        r.batt_a = _val(m, "A")
                        w = _val(m, "W")
                        if w is not None:
                            r.batt_w = -w      # 802: +W = discharging -> relay wants +charge
                    elif mid == 124:
                        r.extra.update(storage_ctl=_val(m, "StorCtl_Mod"), chastate=_val(m, "ChaState"))
                        if r.soc is None:
                            r.soc = clamp_soc(_val(m, "ChaState"))
        return [r]
