from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from ..schema import Reading


class BaseAdapter(ABC):
    """Pull adapter: the scheduler calls :meth:`read` every ``interval_s`` seconds."""

    name: str = "base"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 30, **options: Any):
        self.device_id = device_id
        self.brand = brand or getattr(self, "default_brand", "")
        self.interval_s = int(interval_s)
        self.options = options
        self.consecutive_errors = 0

    async def start(self) -> None:  # open connections / login
        return None

    async def stop(self) -> None:
        return None

    @abstractmethod
    async def read(self) -> list[Reading]:
        ...

    def offline_reading(self, reason: str) -> Reading:
        return Reading(device_id=self.device_id, brand=self.brand, source=self.name,
                       online=False, status=f"offline: {reason}"[:200])

    def new_reading(self, **kw: Any) -> Reading:
        return Reading(device_id=self.device_id, brand=self.brand, source=self.name, **kw)

    async def run_blocking(self, fn, *args: Any) -> Any:
        """Run a synchronous vendor library call without blocking the event loop."""
        return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


class PushAdapter(BaseAdapter):
    """Push adapter: vendor sends data to us (MQTT subscription / webhook)."""

    async def read(self) -> list[Reading]:  # not used for push adapters
        return []

    @abstractmethod
    def stream(self) -> AsyncIterator[Reading]:
        ...
