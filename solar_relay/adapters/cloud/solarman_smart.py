"""Solarman Smart / Deye Cloud business API (official, needs appId + appSecret from Solarman / IGEN).

Covers every plant on a Solarman-based cloud: Deye, Sofar, Solis (Solarman loggers) and many OEMs.
Endpoints: /account/v1.0/token, /station/v1.0/list, /station/v1.0/realTime, /device/v1.0/alertList
Rate limit: generous, but real-time data refreshes only every 5 min -> interval_s 300.

options:
  app_id, app_secret, email, password (plain; hashed with SHA-256 before sending), base_url
  station_ids: [..]   optional filter
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.solarman")


class SolarmanSmartAdapter(CloudAdapter):
    name = "cloud:solarman"
    default_brand = "deye"
    base_url = "https://globalapi.solarmanpv.com"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "deye", interval_s, **options)
        self.app_id = str(options["app_id"])
        self.app_secret = str(options["app_secret"])
        self.email = options.get("email")
        self.password = str(options["password"])
        self.station_filter = set(int(s) for s in options.get("station_ids", []) or [])
        self._token: str | None = None
        self._stations: list[dict] = []

    async def _login(self) -> None:
        body = {"appSecret": self.app_secret, "email": self.email,
                "password": hashlib.sha256(self.password.encode("utf-8")).hexdigest()}
        j = await self.post_json(f"/account/v1.0/token?appId={self.app_id}&language=en", body)
        if not j.get("success"):
            raise PermissionError(f"Solarman login failed: {j.get('msg')}")
        self._token = j["access_token"]

    async def _call(self, path: str, body: dict) -> Any:
        if not self._token:
            await self._login()
        j = await self.post_json(f"{path}?language=en", body, headers={"Authorization": f"bearer {self._token}"})
        if not j.get("success"):
            if str(j.get("code")) in ("2101001", "401"):
                await self._login()
                return await self._call(path, body)
            raise OSError(f"Solarman {path}: {j.get('msg')} (code {j.get('code')})")
        return j

    async def start(self) -> None:
        j = await self._call("/station/v1.0/list", {"page": 1, "size": 100})
        self._stations = [s for s in j.get("stationList", []) if not self.station_filter or int(s["id"]) in self.station_filter]
        if not self._stations:
            raise RuntimeError("Solarman: no stations visible for this account")
        log.info("[%s] Solarman stations: %s", self.device_id, [(s["id"], s.get("name")) for s in self._stations])

    async def read(self) -> list[Reading]:
        if not self._stations:
            await self.start()
        out: list[Reading] = []
        for st in self._stations:
            sid = int(st["id"])
            j = await self._call("/station/v1.0/realTime", {"stationId": sid})
            r = Reading(device_id=f"{self.device_id}:{sid}" if len(self._stations) > 1 else self.device_id,
                        brand=self.brand, source=self.name)
            g = j.get
            r.pv_w = g("generationPower")
            r.load_w = g("usePower")
            purchase, wire = g("purchasePower"), g("wirePower")
            if purchase is not None or wire is not None:
                r.grid_w = float(purchase or 0) - float(wire or 0)
            elif g("gridPower") is not None:
                r.grid_w = float(g("gridPower"))
            ch, dis = g("chargePower"), g("dischargePower")
            if ch is not None or dis is not None:
                r.batt_w = float(ch or 0) - float(dis or 0)
            elif g("batteryPower") is not None:
                r.batt_w = float(g("batteryPower"))
            r.soc = clamp_soc(g("batterySoc"))
            r.extra.update(station=sid, name=st.get("name"), irradiance=g("irradiateIntensity"))
            if g("lastUpdateTime"):
                r.ts = datetime.fromtimestamp(int(g("lastUpdateTime")), tz=timezone.utc)
                r.online = time.time() - int(g("lastUpdateTime")) < 1800
            try:
                al = await self._call("/station/v1.0/alertList", {"stationId": sid, "startTimestamp": int(time.time()) - 86400,
                                                                     "endTimestamp": int(time.time()), "page": 1, "size": 50})
                for a in al.get("alertList", []) or []:
                    r.alarms.append(Alarm(code=f"solarman.{a.get('alertNameInPAAS') or a.get('code')}", message=str(a.get("addr") or a.get("alertNameInPAAS", "")),
                                          severity="fault" if int(a.get("level", 1) or 1) >= 2 else "warning",
                                          raised_at=datetime.fromtimestamp(int(a["alertTime"]), tz=timezone.utc) if a.get("alertTime") else None,
                                          raw={"deviceSn": a.get("deviceSn"), "influence": a.get("influence")}))
            except Exception as exc:  # noqa: BLE001
                log.debug("[%s] alertList skipped: %s", self.device_id, exc)
            out.append(r)
        return out
