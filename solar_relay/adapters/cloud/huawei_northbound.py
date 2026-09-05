"""Huawei FusionSolar Northbound OpenAPI (official; installer creates the Northbound account).

Endpoints: /thirdData/login, /thirdData/stations, /thirdData/getStationRealKpi, /thirdData/getDevList,
/thirdData/getDevRealKpi, /thirdData/getAlarmList.
Rate limit: getDevRealKpi once per 5 minutes per account -> interval_s >= 300.

options:
  username, password (systemCode), base_url (region: https://intl.fusionsolar.huawei.com, https://sg5.fusionsolar.huawei.com, ...)
  station_codes: [..]   optional filter (default: all stations under the account)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.huawei")

DEV_STRING_INV, DEV_RES_INV, DEV_BATTERY, DEV_METER, DEV_POWER_SENSOR = 1, 38, 39, 17, 47
INV_STATE = {0: "Standby", 1: "Grid-connected", 256: "Standby: initializing", 512: "Grid-connected", 513: "Grid-connected: limited",
             514: "Grid-connected: self-derating", 768: "Shutdown: fault", 769: "Shutdown: command", 770: "Shutdown: OVGR",
             771: "Shutdown: communication disconnected", 772: "Shutdown: power limited", 773: "Shutdown: manual startup required"}


class HuaweiNorthboundAdapter(CloudAdapter):
    name = "cloud:huawei"
    default_brand = "huawei"
    base_url = "https://intl.fusionsolar.huawei.com"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "huawei", max(int(interval_s), 300), **options)
        self.username = options["username"]
        self.password = options["password"]
        self.station_filter = set(options.get("station_codes", []) or [])
        self._token: str | None = None
        self._devices: dict[int, list[dict]] = {}   # devTypeId -> devices
        self._dev_station: dict[str, str] = {}

    async def _login(self) -> None:
        resp = await self._http.post(f"{self.base_url}/thirdData/login",
                                     json={"userName": self.username, "systemCode": self.password})
        resp.raise_for_status()
        j = resp.json()
        if not j.get("success"):
            raise PermissionError(f"Huawei login failed: {j.get('message')} ({j.get('failCode')})")
        self._token = resp.headers.get("xsrf-token") or resp.headers.get("XSRF-TOKEN")
        if not self._token:
            raise PermissionError("Huawei login ok but no XSRF-TOKEN header")

    async def _call(self, path: str, body: dict) -> Any:
        if self._token is None:
            await self._login()
        j = await self.post_json(path, body, headers={"XSRF-TOKEN": self._token})
        if j.get("failCode") in (305, 401):   # token expired
            await self._login()
            j = await self.post_json(path, body, headers={"XSRF-TOKEN": self._token})
        if not j.get("success"):
            raise IOError(f"Huawei {path}: {j.get('message')} (failCode {j.get('failCode')})")
        return j.get("data")

    async def start(self) -> None:
        await self._login()
        stations = await self._call("/thirdData/stations", {"pageNo": 1, "pageSize": 100})
        codes = [s["plantCode"] for s in (stations or {}).get("list", [])]
        if self.station_filter:
            codes = [c for c in codes if c in self.station_filter]
        if not codes:
            raise RuntimeError("Huawei: no stations visible for this Northbound account")
        self._codes = codes
        devs = await self._call("/thirdData/getDevList", {"stationCodes": ",".join(codes)})
        for d in devs or []:
            self._devices.setdefault(int(d["devTypeId"]), []).append(d)
            self._dev_station[str(d["id"])] = d.get("stationCode", "")
        log.info("[%s] Huawei stations=%s devices=%s", self.device_id, codes,
                 {k: len(v) for k, v in self._devices.items()})

    async def read(self) -> list[Reading]:
        if not self._devices:
            await self.start()
        readings: list[Reading] = []
        by_station: dict[str, Reading] = {}

        def reading_for(station: str, dev: dict) -> Reading:
            r = Reading(device_id=f"{self.device_id}:{dev.get('devName') or dev['id']}", brand=self.brand, source=self.name)
            r.extra.update(station=station, dev_id=dev["id"], dev_type=dev["devTypeId"], sn=dev.get("esnCode"), model=dev.get("model"))
            return r

        for dev_type in (DEV_STRING_INV, DEV_RES_INV):
            devs = self._devices.get(dev_type, [])
            if not devs:
                continue
            data = await self._call("/thirdData/getDevRealKpi",
                                    {"devIds": ",".join(str(d["id"]) for d in devs), "devTypeId": dev_type})
            by_id = {str(d["id"]): d for d in devs}
            for item in data or []:
                dev = by_id.get(str(item["devId"]))
                if not dev:
                    continue
                m = item.get("dataItemMap", {}) or {}
                r = reading_for(self._dev_station.get(str(dev["id"]), ""), dev)
                r.ac_w = (m.get("active_power") or 0) * 1000.0
                r.pv_w = (m.get("mppt_power") or 0) * 1000.0 if m.get("mppt_power") is not None else r.ac_w
                r.reactive_var = (m.get("reactive_power") or 0) * 1000.0
                r.temp_c, r.grid_hz = m.get("temperature"), m.get("elec_freq")
                r.grid_v = m.get("a_u")
                r.energy_day_kwh, r.energy_total_kwh = m.get("day_cap"), m.get("total_cap")
                st = m.get("inverter_state")
                r.status = INV_STATE.get(int(st), f"state {st}") if st is not None else None
                r.online = int(m.get("run_state", 1) or 0) == 1
                for i in range(1, 9):
                    u, a = m.get(f"pv{i}_u"), m.get(f"pv{i}_i")
                    if u:
                        r.strings[f"pv{i}"] = {"v": u, "a": a, "w": round((u or 0) * (a or 0), 1)}
                r.extra.update(efficiency=m.get("efficiency"))
                readings.append(r)
                by_station.setdefault(r.extra["station"], r)

        for item in await self._kpi(DEV_BATTERY):
            m = item["dataItemMap"]
            r = by_station.get(item["station"]) or self._new_station_reading(item["station"], readings, by_station)
            r.soc = clamp_soc(m.get("battery_soc"))
            r.soh = m.get("battery_soh")
            if m.get("ch_discharge_power") is not None:
                r.batt_w = float(m["ch_discharge_power"]) * 1000.0   # + charge
            r.batt_charge_day_kwh, r.batt_discharge_day_kwh = m.get("charge_cap"), m.get("discharge_cap")

        for item in await self._kpi(DEV_POWER_SENSOR) + await self._kpi(DEV_METER):
            m = item["dataItemMap"]
            r = by_station.get(item["station"]) or self._new_station_reading(item["station"], readings, by_station)
            if m.get("active_power") is not None:
                r.grid_w = -float(m["active_power"])   # Huawei sensor: + feed-in -> relay + import
            r.extra.update(meter_status=m.get("meter_status"))

        # alarms (last 24 h) per station
        try:
            now = int(time.time() * 1000)
            alarms = await self._call("/thirdData/getAlarmList",
                                      {"stationCodes": ",".join(self._codes), "beginTime": now - 86_400_000,
                                       "endTime": now, "language": "en_US"})
            for a in alarms or []:
                r = by_station.get(a.get("stationCode")) or self._new_station_reading(a.get("stationCode", ""), readings, by_station)
                lev = int(a.get("lev", 3) or 3)
                r.alarms.append(Alarm(code=f"huawei.{a.get('alarmId')}", message=f"{a.get('alarmName')}: {a.get('alarmCause')}",
                                      severity="fault" if lev <= 2 else "warning",
                                      active=int(a.get("status", 1) or 1) == 1,
                                      raised_at=datetime.fromtimestamp(a["raiseTime"] / 1000, tz=timezone.utc) if a.get("raiseTime") else None,
                                      raw={"repair": a.get("repairSuggestion"), "devName": a.get("devName")}))
        except Exception as exc:  # noqa: BLE001
            log.debug("[%s] alarm list skipped: %s", self.device_id, exc)
        return readings

    async def _kpi(self, dev_type: int) -> list[dict]:
        devs = self._devices.get(dev_type, [])
        if not devs:
            return []
        data = await self._call("/thirdData/getDevRealKpi",
                                {"devIds": ",".join(str(d["id"]) for d in devs), "devTypeId": dev_type})
        out = []
        for item in data or []:
            out.append({"dataItemMap": item.get("dataItemMap", {}) or {},
                        "station": self._dev_station.get(str(item["devId"]), "")})
        return out

    def _new_station_reading(self, station: str, readings: list[Reading], by_station: dict[str, Reading]) -> Reading:
        r = Reading(device_id=f"{self.device_id}:{station}", brand=self.brand, source=self.name)
        r.extra["station"] = station
        readings.append(r)
        by_station[station] = r
        return r
