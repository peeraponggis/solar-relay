"""SolisCloud Platform API v2 (official; request key/secret from Solis service center).

Auth: HMAC-SHA1 over "POST\\n<Content-MD5>\\napplication/json\\n<Date>\\n<path>", header Authorization: API <key>:<sign>
Endpoints: /v1/api/userStationList, /v1/api/inverterList, /v1/api/inverterDetail, /v1/api/alarmList
Rate limit: about 1 call / 2 s; polls are cheap so interval_s 60-300 is fine.

options:
  key_id, key_secret, base_url (https://www.soliscloud.com:13333)
  inverter_sns: [..]     optional filter; default = all inverters under the account
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from email.utils import formatdate
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter, kw_to_w, to_kwh

log = logging.getLogger("solar_relay.cloud.soliscloud")

SOLIS_STATE = {1: "Online", 2: "Offline", 3: "Alarm"}


def solis_sign(key_id: str, key_secret: str, path: str, body: str, date: str | None = None) -> dict[str, str]:
    """Build the SolisCloud v2 auth headers for a POST with a JSON body (pure function, unit-tested)."""
    date = date or formatdate(usegmt=True)
    content_md5 = base64.b64encode(hashlib.md5(body.encode("utf-8")).digest()).decode()
    string_to_sign = f"POST\n{content_md5}\napplication/json\n{date}\n{path}"
    sign = base64.b64encode(hmac.new(key_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()).decode()
    return {"Content-MD5": content_md5, "Content-Type": "application/json", "Date": date,
            "Authorization": f"API {key_id}:{sign}"}


class SolisCloudAdapter(CloudAdapter):
    name = "cloud:soliscloud"
    default_brand = "solis"
    base_url = "https://www.soliscloud.com:13333"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "solis", interval_s, **options)
        self.key_id = str(options["key_id"])
        self.key_secret = str(options["key_secret"])
        self.sn_filter = set(str(s) for s in options.get("inverter_sns", []) or [])
        self._inverters: list[dict] = []

    async def _call(self, path: str, body: dict) -> Any:
        raw = json.dumps(body, separators=(",", ":"))
        headers = solis_sign(self.key_id, self.key_secret, path, raw)
        resp = await self._http.post(f"{self.base_url}{path}", content=raw, headers=headers)
        resp.raise_for_status()
        j = resp.json()
        if not j.get("success", False) or str(j.get("code")) != "0":
            raise OSError(f"SolisCloud {path}: {j.get('msg')} (code {j.get('code')})")
        return j.get("data")

    async def start(self) -> None:
        data = await self._call("/v1/api/inverterList", {"pageNo": 1, "pageSize": 100})
        records = (data or {}).get("page", {}).get("records", []) or []
        self._inverters = [r for r in records if not self.sn_filter or str(r.get("sn")) in self.sn_filter]
        if not self._inverters:
            raise RuntimeError("SolisCloud: no inverters visible for this key (check inverter_sns filter)")
        log.info("[%s] SolisCloud inverters: %s", self.device_id, [i.get("sn") for i in self._inverters])

    async def read(self) -> list[Reading]:
        if not self._inverters:
            await self.start()
        out: list[Reading] = []
        for inv in self._inverters:
            sn = str(inv["sn"])
            d = await self._call("/v1/api/inverterDetail", {"sn": sn})
            r = Reading(device_id=f"{self.device_id}:{sn}" if len(self._inverters) > 1 else self.device_id,
                        brand=self.brand, source=self.name)
            g = d.get
            r.ac_w = kw_to_w(g("pac"), g("pacStr"))
            pv = kw_to_w(g("pow1"), "W") or 0.0
            for i in range(1, 5):
                u, a, p = g(f"uPv{i}"), g(f"iPv{i}"), g(f"pow{i}")
                if u:
                    r.strings[f"pv{i}"] = {"v": u, "a": a, "w": p}
            r.pv_w = sum((s.get("w") or 0) for s in r.strings.values()) if r.strings else pv
            psum = kw_to_w(g("psum"), g("psumStr"))
            if psum is not None:
                r.grid_w = -psum                                     # SolisCloud psum: + export
            r.load_w = kw_to_w(g("familyLoadPower"), g("familyLoadPowerStr"))
            bp = kw_to_w(g("batteryPower"), g("batteryPowerStr"))
            if bp is not None:
                # batteryPower sign: positive = charging on most firmware; batteryPowerPec / storageBatteryCurrent confirm
                r.batt_w = bp
            r.soc = clamp_soc(g("batteryCapacitySoc"))
            r.soh = g("batteryHealthSoh")
            r.batt_v, r.batt_a = g("storageBatteryVoltage"), g("storageBatteryCurrent")
            r.temp_c, r.grid_hz, r.grid_v = g("inverterTemperature"), g("fac"), g("uAc1")
            r.energy_day_kwh = to_kwh(g("eToday"), g("eTodayStr"))
            r.energy_total_kwh = to_kwh(g("eTotal"), g("eTotalStr"))
            r.grid_import_day_kwh = to_kwh(g("gridPurchasedTodayEnergy"), g("gridPurchasedTodayEnergyStr"))
            r.grid_export_day_kwh = to_kwh(g("gridSellTodayEnergy"), g("gridSellTodayEnergyStr"))
            r.batt_charge_day_kwh = to_kwh(g("batteryTodayChargeEnergy"), g("batteryTodayChargeEnergyStr"))
            r.batt_discharge_day_kwh = to_kwh(g("batteryTodayDischargeEnergy"), g("batteryTodayDischargeEnergyStr"))
            r.load_day_kwh = to_kwh(g("homeLoadTodayEnergy"), g("homeLoadTodayEnergyStr"))
            st = g("state")
            r.status = SOLIS_STATE.get(int(st), f"state {st}") if st is not None else None
            r.online = st != 2
            r.extra.update(sn=sn, model=g("model") or inv.get("model"), station=g("stationId"), collector=g("collectorSn"),
                           update_ts=g("dataTimestamp"))
            if g("dataTimestamp"):
                r.ts = datetime.fromtimestamp(int(g("dataTimestamp")) / 1000, tz=timezone.utc)
            try:
                al = await self._call("/v1/api/alarmList", {"pageNo": 1, "pageSize": 50, "alarmDeviceSn": sn})
                for a in (al or {}).get("records", []) or []:
                    r.alarms.append(Alarm(code=f"solis.{a.get('alarmCode')}", message=str(a.get("alarmMsg", "")),
                                          severity="fault" if str(a.get("alarmLevel", "")).lower() in ("1", "high", "fault") else "warning",
                                          active=a.get("alarmEndTime") in (None, 0, ""),
                                          raised_at=datetime.fromtimestamp(int(a["alarmBeginTime"]) / 1000, tz=timezone.utc) if a.get("alarmBeginTime") else None,
                                          raw={"advice": a.get("advice")}))
            except Exception as exc:  # noqa: BLE001
                log.debug("[%s] alarmList skipped: %s", self.device_id, exc)
            out.append(r)
        return out
