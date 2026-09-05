"""PVOutput.org addstatus output (one PVOutput system per relay device).

options:
  api_key
  systems: {device_id: system_id, ...}     readings from devices not listed are ignored
  min_interval_s: 300                       PVOutput free accounts accept 1 status per 5 min
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ..schema import Reading
from .base import BaseOutput

log = logging.getLogger("solar_relay.pvoutput")


class PVOutputOutput(BaseOutput):
    name = "pvoutput"
    URL = "https://pvoutput.org/service/r2/addstatus.jsp"

    def __init__(self, api_key: str, systems: dict[str, Any], min_interval_s: int = 300, **options: Any):
        super().__init__(**options)
        self.api_key = api_key
        self.systems = {str(k): str(v) for k, v in systems.items()}
        self.min_interval_s = int(min_interval_s)
        self._last: dict[str, float] = {}
        self._http = httpx.AsyncClient(timeout=15)

    async def stop(self) -> None:
        await self._http.aclose()

    @staticmethod
    def payload(reading: Reading) -> dict[str, str]:
        local = reading.ts.astimezone()
        p = {"d": local.strftime("%Y%m%d"), "t": local.strftime("%H:%M")}
        if reading.energy_day_kwh is not None:
            p["v1"] = str(int(reading.energy_day_kwh * 1000))
        if (reading.pv_w if reading.pv_w is not None else reading.ac_w) is not None:
            p["v2"] = str(int(reading.pv_w if reading.pv_w is not None else reading.ac_w))
        if reading.load_day_kwh is not None:
            p["v3"] = str(int(reading.load_day_kwh * 1000))
        if reading.load_w is not None:
            p["v4"] = str(int(reading.load_w))
        if reading.temp_c is not None:
            p["v5"] = f"{reading.temp_c:.1f}"
        if reading.grid_v is not None:
            p["v6"] = f"{reading.grid_v:.1f}"
        return p

    async def write(self, reading: Reading) -> None:
        sid = self.systems.get(reading.device_id)
        if not sid or not reading.online:
            return
        now = time.time()
        if now - self._last.get(reading.device_id, 0) < self.min_interval_s:
            return
        p = self.payload(reading)
        if "v1" not in p and "v2" not in p:
            return
        resp = await self._http.post(self.URL, data=p, headers={"X-Pvoutput-Apikey": self.api_key, "X-Pvoutput-SystemId": sid})
        if resp.status_code != 200:
            raise OSError(f"PVOutput {resp.status_code}: {resp.text[:120]}")
        self._last[reading.device_id] = now
