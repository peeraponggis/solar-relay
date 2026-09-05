"""Fronius local Solar API v1 (JSON over HTTP, enabled by default on Symo/Primo/Gen24).

Endpoints used:
  /solar_api/v1/GetPowerFlowRealtimeData.fcgi        site P_PV / P_Grid / P_Load / P_Akku / SOC
  /solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceId=<n>&DataCollection=CommonInverterData
options: host, device_id_fronius (default 1), scheme (http)
"""
from __future__ import annotations

from typing import Any

import httpx

from ..schema import Alarm, Reading, clamp_soc
from .base import BaseAdapter

FRONIUS_STATUS = {0: "Startup", 1: "Startup", 2: "Startup", 3: "Startup", 4: "Startup", 5: "Startup", 6: "Startup",
                  7: "Running", 8: "Standby", 9: "Bootloading", 10: "Error"}


class FroniusSolarApiAdapter(BaseAdapter):
    name = "fronius_solarapi"
    default_brand = "fronius"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 30, **options: Any):
        super().__init__(device_id, brand or "fronius", interval_s, **options)
        self.base = f"{options.get('scheme', 'http')}://{options['host']}/solar_api/v1"
        self.dev = int(options.get("device_id_fronius", 1))
        self._http = httpx.AsyncClient(timeout=10)

    async def stop(self) -> None:
        await self._http.aclose()

    async def read(self) -> list[Reading]:
        r = self.new_reading()
        flow = (await self._http.get(f"{self.base}/GetPowerFlowRealtimeData.fcgi")).json()["Body"]["Data"]
        site = flow.get("Site", {})
        r.pv_w = site.get("P_PV")
        grid = site.get("P_Grid")
        if grid is not None:
            r.grid_w = float(grid)                 # Fronius: + import
        load = site.get("P_Load")
        if load is not None:
            r.load_w = abs(float(load))            # Fronius: negative = consumption
        akku = site.get("P_Akku")
        if akku is not None:
            r.batt_w = -float(akku)                # Fronius: + discharge
        r.energy_day_kwh = (site.get("E_Day") or 0) / 1000.0 if site.get("E_Day") is not None else None
        r.energy_total_kwh = (site.get("E_Total") or 0) / 1000.0 if site.get("E_Total") is not None else None
        for inv in (flow.get("Inverters") or {}).values():
            if inv.get("SOC") is not None:
                r.soc = clamp_soc(inv["SOC"])
            if inv.get("P") is not None:
                r.ac_w = float(inv["P"])
        try:
            inv = (await self._http.get(
                f"{self.base}/GetInverterRealtimeData.cgi",
                params={"Scope": "Device", "DeviceId": self.dev, "DataCollection": "CommonInverterData"},
            )).json()["Body"]["Data"]
            r.grid_v = (inv.get("UAC") or {}).get("Value")
            r.grid_hz = (inv.get("FAC") or {}).get("Value")
            udc, idc = (inv.get("UDC") or {}).get("Value"), (inv.get("IDC") or {}).get("Value")
            if udc is not None:
                r.strings["pv1"] = {"v": udc, "a": idc, "w": round((udc or 0) * (idc or 0), 1)}
            ds = inv.get("DeviceStatus") or {}
            code = ds.get("StatusCode")
            r.status = FRONIUS_STATUS.get(code, f"status {code}")
            err = ds.get("ErrorCode")
            if err:
                r.alarms.append(Alarm(code=f"fronius.{err}", message=f"Fronius state code {err}", severity="fault"))
        except Exception:  # noqa: BLE001 - power-flow data alone is still a valid reading
            pass
        return [r]
