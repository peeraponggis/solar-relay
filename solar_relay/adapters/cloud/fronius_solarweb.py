"""Fronius Solar.web Query API (official, paid "Solar.web API" licence; AccessKeyId / AccessKeyValue).

Endpoints: /swqapi/pvsystems/{id}/flowdata, /swqapi/pvsystems/{id}/aggrdata?period=total
options: access_key_id, access_key_value, pv_system_id, base_url (https://api.solarweb.com)
Prefer the local `fronius_solarapi` adapter whenever the inverter is on the LAN.
"""
from __future__ import annotations

import logging
from typing import Any

from ...schema import Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.fronius")


class FroniusSolarWebAdapter(CloudAdapter):
    name = "cloud:fronius"
    default_brand = "fronius"
    base_url = "https://api.solarweb.com"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "fronius", interval_s, **options)
        self.headers = {"AccessKeyId": options["access_key_id"], "AccessKeyValue": options["access_key_value"],
                        "Accept": "application/json"}
        self.system_id = options["pv_system_id"]

    async def read(self) -> list[Reading]:
        flow = await self.get_json(f"/swqapi/pvsystems/{self.system_id}/flowdata", headers=self.headers)
        ch = {c["channelName"]: c.get("value") for c in (flow.get("data") or {}).get("channels", []) or []}
        r = self.new_reading()
        r.pv_w = ch.get("PowerPV")
        r.load_w = abs(ch["PowerLoad"]) if ch.get("PowerLoad") is not None else None
        if ch.get("PowerGrid") is not None:
            r.grid_w = float(ch["PowerGrid"])                # Solar.web: + import
        elif ch.get("PowerFeedIn") is not None:
            r.grid_w = -float(ch["PowerFeedIn"])
        if ch.get("PowerBattery") is not None:
            r.batt_w = -float(ch["PowerBattery"])           # Solar.web: + discharge
        r.soc = clamp_soc(ch.get("StateOfCharge") or ch.get("BatterySOC"))
        r.online = bool((flow.get("status") or {}).get("isOnline", True))
        r.extra["battery_mode"] = ch.get("BatteryMode")
        try:
            agg = await self.get_json(f"/swqapi/pvsystems/{self.system_id}/aggrdata", {"period": "total"}, headers=self.headers)
            for c in (agg.get("data") or [{}])[0].get("channels", []) or []:
                if c.get("channelName") == "EnergyProductionTotal":
                    r.energy_total_kwh = (c.get("value") or 0) / 1000.0
        except Exception as exc:  # noqa: BLE001
            log.debug("[%s] aggrdata skipped: %s", self.device_id, exc)
        return [r]
