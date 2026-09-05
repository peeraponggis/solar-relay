from __future__ import annotations

import logging
from typing import Any

import httpx

from ..base import BaseAdapter

log = logging.getLogger("solar_relay.cloud")


class CloudAdapter(BaseAdapter):
    """Shared HTTP client + helpers for vendor cloud adapters."""

    base_url: str = ""
    default_interval_s = 300

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand, max(int(interval_s), 60), **options)
        self.base_url = options.get("base_url", self.base_url).rstrip("/")
        self._http = httpx.AsyncClient(timeout=float(options.get("timeout", 30)), follow_redirects=True)

    async def stop(self) -> None:
        await self._http.aclose()

    async def post_json(self, path: str, body: Any = None, headers: dict[str, str] | None = None, **kw: Any) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = await self._http.post(url, json=body, headers=headers, **kw)
        resp.raise_for_status()
        return resp.json()

    async def get_json(self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = await self._http.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


def kw_to_w(value: Any, unit: str | None = None) -> float | None:
    """Normalize a power value to W given a vendor unit string ('kW', 'W', 'MW')."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    u = (unit or "kW").strip().lower()
    if u.startswith("mw"):
        return v * 1_000_000
    if u.startswith("kw"):
        return v * 1000
    return v


def to_kwh(value: Any, unit: str | None = None) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    u = (unit or "kWh").strip().lower()
    if u.startswith("mwh"):
        return v * 1000
    if u.startswith("wh"):
        return v / 1000
    return v
