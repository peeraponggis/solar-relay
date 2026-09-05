"""GoodWe SEMS Portal (UNOFFICIAL - reverse-engineered app API, may change without notice).

Endpoints: /api/v2/Common/CrossLogin, {api}v2/PowerStation/GetMonitorDetailByPowerstationId
options: account, password, power_station_id, base_url (https://www.semsportal.com)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.goodwe")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _kw_str(s: Any) -> float | None:
    """'1.23(kW)' / '456(W)' / '55%' -> W or %."""
    if s is None:
        return None
    m = _NUM.search(str(s))
    if not m:
        return None
    v = float(m.group())
    if "(kW)" in str(s) or "kW" in str(s):
        v *= 1000.0
    return v


class GoodWeSemsAdapter(CloudAdapter):
    name = "cloud:goodwe"
    default_brand = "goodwe"
    base_url = "https://www.semsportal.com"
    LOGIN_TOKEN = json.dumps({"version": "v2.1.0", "client": "ios", "language": "en"})

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "goodwe", interval_s, **options)
        self.account = options["account"]
        self.password = options["password"]
        self.ps_id = options["power_station_id"]
        self._token: str | None = None
        self._api: str | None = None

    async def _login(self) -> None:
        j = await self.post_json("/api/v2/Common/CrossLogin", {"account": self.account, "pwd": self.password},
                                 headers={"Token": self.LOGIN_TOKEN})
        if str(j.get("code")) not in ("0", "200"):
            raise PermissionError(f"SEMS login failed: {j.get('msg')}")
        data = j["data"]
        self._token = json.dumps({"uid": data["uid"], "timestamp": data["timestamp"], "token": data["token"],
                                  "client": "ios", "version": "v2.1.0", "language": "en"})
        self._api = data.get("api", f"{self.base_url}/api/")

    async def read(self) -> list[Reading]:
        if not self._token:
            await self._login()
        j = await self.post_json(f"{self._api}v2/PowerStation/GetMonitorDetailByPowerstationId",
                                 {"powerStationId": self.ps_id}, headers={"Token": self._token})
        if str(j.get("code")) not in ("0", "200"):
            self._token = None
            raise OSError(f"SEMS: {j.get('msg')}")
        d = j["data"]
        r = self.new_reading()
        flow = d.get("powerflow") or {}
        r.pv_w = _kw_str(flow.get("pv"))
        r.load_w = _kw_str(flow.get("load"))
        grid = _kw_str(flow.get("grid"))
        if grid is not None:
            # gridStatus: 1 = export to grid, -1 = import
            r.grid_w = -grid if int(flow.get("gridStatus", -1) or -1) == 1 else grid
        batt = _kw_str(flow.get("bettery"))
        if batt is not None:
            # batteryStatus: 1 = discharging, -1 = charging (SEMS convention)
            r.batt_w = -batt if int(flow.get("batteryStatus", 1) or 1) == 1 else batt
        r.soc = clamp_soc(_kw_str(flow.get("soc")))
        kpi = d.get("kpi") or {}
        r.energy_day_kwh = kpi.get("power")
        r.energy_total_kwh = kpi.get("total_power")
        invs = d.get("inverter") or []
        if invs:
            full = invs[0].get("invert_full") or {}
            r.ac_w = full.get("pac")
            r.temp_c = full.get("tempperature") or full.get("temperature")
            r.grid_v, r.grid_hz = full.get("vac1"), full.get("fac1")
            r.status = str(invs[0].get("status_text") or full.get("work_mode") or "")
            r.online = int(invs[0].get("status", 1) or 0) >= 0
            for i in (1, 2, 3, 4):
                if full.get(f"vpv{i}"):
                    r.strings[f"pv{i}"] = {"v": full[f"vpv{i}"], "a": full.get(f"ipv{i}"),
                                           "w": round((full[f"vpv{i}"] or 0) * (full.get(f"ipv{i}") or 0), 1)}
            err = full.get("error_msg") or invs[0].get("warning")
            if err and str(err).strip() not in ("", "0", "None"):
                r.alarms.append(Alarm(code="goodwe.sems", message=str(err), severity="fault"))
            r.extra.update(sn=invs[0].get("sn"), model=invs[0].get("type"))
        return [r]
