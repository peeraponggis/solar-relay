"""Generic Modbus adapter driven by a brand register map (see modbus_maps.MAPS).

options:
  map:      huawei | solis | sungrow | solax | deye_1p | deye_3p | sofar | sigen_local
  host / port           (Modbus TCP)      or
  serial / baudrate     (Modbus RTU, e.g. /dev/ttyUSB0 9600 for Solis RS485)
  unit:     slave id (default from map)
  timeout:  seconds (default 5)
  max_block: registers per request (default 100; use 60 for flaky WiFi dongles)
"""
from __future__ import annotations

import logging
from typing import Any

from ..schema import Reading
from .base import BaseAdapter
from .modbus_maps import MAPS, decode_block, plan_blocks

log = logging.getLogger("solar_relay.modbus")


class ModbusMapAdapter(BaseAdapter):
    name = "modbus"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 30, **options: Any):
        super().__init__(device_id, brand, interval_s, **options)
        key = options.get("map") or brand
        if key not in MAPS:
            raise ValueError(f"[{device_id}] unknown modbus map '{key}'. Known: {', '.join(MAPS)}")
        self.map_key = key
        self.regs, self.finalize, defaults = MAPS[key]
        self.brand = brand or key.split("_")[0]
        self.unit = int(options.get("unit", defaults["unit"]))
        self.host = options.get("host")
        self.port = int(options.get("port", defaults["port"]))
        self.serial = options.get("serial")
        self.baudrate = int(options.get("baudrate", 9600))
        self.timeout = float(options.get("timeout", 5))
        self.blocks = plan_blocks(self.regs, int(options.get("max_block", 100)))
        self._client = None

    async def start(self) -> None:
        from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
        if self.serial:
            self._client = AsyncModbusSerialClient(port=self.serial, baudrate=self.baudrate, timeout=self.timeout)
        elif self.host:
            self._client = AsyncModbusTcpClient(self.host, port=self.port, timeout=self.timeout)
        else:
            raise ValueError(f"[{self.device_id}] modbus adapter needs 'host' or 'serial'")
        await self._client.connect()

    async def stop(self) -> None:
        if self._client is not None:
            self._client.close()

    async def _read_words(self, fc: int, start: int, count: int) -> list[int]:
        c = self._client
        if not c.connected:
            await c.connect()
        kwargs = {"count": count}
        # pymodbus 3.7 renamed slave= -> device_id= in 3.8; support both
        try:
            rr = await (c.read_input_registers if fc == 4 else c.read_holding_registers)(start, device_id=self.unit, **kwargs)
        except TypeError:
            rr = await (c.read_input_registers if fc == 4 else c.read_holding_registers)(start, slave=self.unit, **kwargs)
        if rr.isError():
            raise IOError(f"modbus fc{fc} @ {start} x{count}: {rr}")
        return list(rr.registers)

    async def read(self) -> list[Reading]:
        values: dict[str, Any] = {}
        for fc, start, count, regs in self.blocks:
            try:
                words = await self._read_words(fc, start, count)
            except Exception as exc:  # a single unsupported block (e.g. no battery) must not kill the reading
                log.debug("[%s] block fc%d@%d skipped: %s", self.device_id, fc, start, exc)
                if not values:
                    raise
                continue
            values.update(decode_block(words, start, regs))
        reading = self.finalize(values, self.new_reading())
        reading.extra.setdefault("map", self.map_key)
        return [reading]
