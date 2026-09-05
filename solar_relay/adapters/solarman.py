"""Solarman V5 logger adapter (pysolarmanv5): Deye, Sofar, Solis DLS-W / DLS-L and every other
IGEN-Tech logger stick (tcp/8899).  Wraps Modbus RTU frames in the Solarman V5 envelope and reuses
the brand register maps from modbus_maps.

options:
  host, port(8899), serial (logger serial number, 10 digits, printed on the stick), unit(1)
  map: deye_1p | deye_3p | sofar | solis
  max_block: default 60 (Solarman sticks dislike large reads)

Not supported: Solis S3-WIFI-ST (no local Modbus at all) -> use cloud:soliscloud.
"""
from __future__ import annotations

import logging
from typing import Any

from ..schema import Reading
from .base import BaseAdapter
from .modbus_maps import MAPS, decode_block, plan_blocks

log = logging.getLogger("solar_relay.solarman")


class SolarmanAdapter(BaseAdapter):
    name = "solarman"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 30, **options: Any):
        super().__init__(device_id, brand, interval_s, **options)
        key = options.get("map") or brand
        if key not in MAPS:
            raise ValueError(f"[{device_id}] unknown map '{key}'. Known: {', '.join(MAPS)}")
        self.map_key = key
        self.regs, self.finalize, defaults = MAPS[key]
        self.brand = brand or key.split("_")[0]
        self.host = options["host"]
        self.port = int(options.get("port", 8899))
        self.logger_serial = int(options["serial"])
        self.unit = int(options.get("unit", defaults["unit"]))
        self.blocks = plan_blocks(self.regs, int(options.get("max_block", 60)))
        self._client = None

    async def start(self) -> None:
        from pysolarmanv5 import PySolarmanV5Async
        self._client = PySolarmanV5Async(self.host, self.logger_serial, port=self.port, mb_slave_id=self.unit,
                                          auto_reconnect=True, socket_timeout=15)
        await self._client.connect()

    async def stop(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def read(self) -> list[Reading]:
        values: dict[str, Any] = {}
        for fc, start, count, regs in self.blocks:
            try:
                if fc == 4:
                    words = await self._client.read_input_registers(register_addr=start, quantity=count)
                else:
                    words = await self._client.read_holding_registers(register_addr=start, quantity=count)
            except Exception as exc:  # noqa: BLE001
                log.debug("[%s] block fc%d@%d skipped: %s", self.device_id, fc, start, exc)
                if not values:
                    raise
                continue
            values.update(decode_block(list(words), start, regs))
        reading = self.finalize(values, self.new_reading())
        reading.extra.setdefault("map", self.map_key)
        reading.extra.setdefault("logger_serial", self.logger_serial)
        return [reading]
