"""SMA Sunny Portal (UNOFFICIAL - SMA publishes no public cloud API).

Uses the `sunnyportal` PyPI library (screen-scraping of the classic Sunny Portal) for plant-level
production only: current power + day / total energy.  There is no battery, grid or alarm data.

For anything serious use the local `sunspec` adapter (enable "Modbus TCP" on the inverter, unit id 3
on most Sunny Boy / Tripower, unit 126 on some Sunny Island) or the SMA Data Manager M Modbus interface.

options: username, password, plant_name (optional, default first plant)
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from ...schema import Reading
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.sma")


class SmaSunnyPortalAdapter(CloudAdapter):
    name = "cloud:sma"
    default_brand = "sma"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 600, **options: Any):
        super().__init__(device_id, brand or "sma", max(int(interval_s), 600), **options)
        self.username = options["username"]
        self.password = options["password"]
        self.plant_name = options.get("plant_name")
        self._client = None
        self._plant = None

    def _login_sync(self) -> None:
        try:
            import sunnyportal.client  # type: ignore
        except ImportError as exc:
            raise ImportError("pip install sunnyportal  (unofficial SMA Sunny Portal client)") from exc
        self._client = sunnyportal.client.Client(self.username, self.password)
        plants = self._client.get_plants()
        if not plants:
            raise RuntimeError("Sunny Portal: no plants on this account")
        self._plant = next((p for p in plants if self.plant_name and p.name == self.plant_name), plants[0])

    async def start(self) -> None:
        await self.run_blocking(self._login_sync)

    def _read_sync(self) -> list[Reading]:
        today = dt.date.today()
        r = self.new_reading()
        try:
            last = self._plant.last_data_exact(today)
            r.ac_w = float(getattr(last, "power", 0) or 0)
            r.pv_w = r.ac_w
        except Exception as exc:  # noqa: BLE001
            log.debug("[%s] last_data_exact: %s", self.device_id, exc)
        try:
            day = self._plant.day_overview(today)
            r.energy_day_kwh = float(getattr(day, "summary", 0) or 0) / 1000.0
        except Exception as exc:  # noqa: BLE001
            log.debug("[%s] day_overview: %s", self.device_id, exc)
        try:
            total = self._plant.year_overview(today)
            r.extra["energy_year_kwh"] = float(getattr(total, "summary", 0) or 0) / 1000.0
        except Exception:  # noqa: BLE001
            pass
        r.extra.update(plant=self._plant.name, note="unofficial Sunny Portal scrape: production only")
        return [r]

    async def read(self) -> list[Reading]:
        if self._plant is None:
            await self.start()
        return await self.run_blocking(self._read_sync)
