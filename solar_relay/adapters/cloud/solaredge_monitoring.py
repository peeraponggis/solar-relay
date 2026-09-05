"""SolarEdge Monitoring API (official; site owner / installer creates the API key in the monitoring portal).

Endpoints: /site/{id}/currentPowerFlow, /site/{id}/overview, /site/{id}/inventory (once)
Rate limit: 300 requests per day per site  ->  2 calls per poll  ->  interval_s >= 600 is safe.

options: api_key, site_id, base_url (https://monitoringapi.solaredge.com)
"""
from __future__ import annotations

import logging
from typing import Any

from ...schema import Reading, clamp_soc
from .base import CloudAdapter, kw_to_w

log = logging.getLogger("solar_relay.cloud.solaredge")


class SolarEdgeMonitoringAdapter(CloudAdapter):
    name = "cloud:solaredge"
    default_brand = "solaredge"
    base_url = "https://monitoringapi.solaredge.com"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 600, **options: Any):
        super().__init__(device_id, brand or "solaredge", max(int(interval_s), 600), **options)
        self.api_key = options["api_key"]
        self.site_id = options["site_id"]

    async def read(self) -> list[Reading]:
        p = {"api_key": self.api_key}
        flow = (await self.get_json(f"/site/{self.site_id}/currentPowerFlow", p))["siteCurrentPowerFlow"]
        unit = flow.get("unit", "kW")
        r = self.new_reading()
        r.pv_w = kw_to_w((flow.get("PV") or {}).get("currentPower"), unit)
        r.load_w = kw_to_w((flow.get("LOAD") or {}).get("currentPower"), unit)
        grid = kw_to_w((flow.get("GRID") or {}).get("currentPower"), unit)
        conns = [(c.get("from", "").upper(), c.get("to", "").upper()) for c in flow.get("connections", []) or []]
        if grid is not None:
            importing = any(f == "GRID" for f, _ in conns)
            r.grid_w = grid if importing else -grid
        st = flow.get("STORAGE") or {}
        if st:
            bw = kw_to_w(st.get("currentPower"), unit)
            if bw is not None:
                r.batt_w = bw if str(st.get("status", "")).lower().startswith("charg") else -bw
            r.soc = clamp_soc(st.get("chargeLevel"))
            r.extra["storage_status"] = st.get("status")
        r.status = (flow.get("PV") or {}).get("status")
        ov = (await self.get_json(f"/site/{self.site_id}/overview", p))["overview"]
        r.energy_day_kwh = (ov.get("lastDayData") or {}).get("energy", 0) / 1000.0
        r.energy_total_kwh = (ov.get("lifeTimeData") or {}).get("energy", 0) / 1000.0
        if r.ac_w is None:
            r.ac_w = kw_to_w((ov.get("currentPower") or {}).get("power"), "W")
        r.extra.update(site=self.site_id, last_update=ov.get("lastUpdateTime"))
        return [r]
