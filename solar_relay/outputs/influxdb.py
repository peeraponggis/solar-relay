"""InfluxDB 2.x / VictoriaMetrics (Influx line protocol) output.

Measurements:
  inverter  tags: device_id, brand, source      fields: every numeric metric + online (int) + status (str)
  alarm     tags: device_id, brand, code        fields: active (int), message (str), severity (str)
options: url, token, org, bucket, measurement (inverter), timeout_ms (10000)
"""
from __future__ import annotations

from typing import Any

from ..schema import Reading
from .base import BaseOutput


class InfluxDBOutput(BaseOutput):
    name = "influxdb"

    def __init__(self, url: str, token: str, org: str, bucket: str, measurement: str = "inverter",
                 timeout_ms: int = 10000, **options: Any):
        super().__init__(**options)
        self.url, self.token, self.org, self.bucket = url, token, org, bucket
        self.measurement = measurement
        self.timeout_ms = timeout_ms
        self._client = None
        self._write = None

    async def start(self) -> None:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS
        self._client = InfluxDBClient(url=self.url, token=self.token, org=self.org, timeout=self.timeout_ms)
        self._write = self._client.write_api(write_options=SYNCHRONOUS)

    async def stop(self) -> None:
        if self._client is not None:
            self._client.close()

    @staticmethod
    def points(reading: Reading, measurement: str = "inverter") -> list[Any]:
        from influxdb_client import Point
        p = (Point(measurement).tag("device_id", reading.device_id).tag("brand", reading.brand)
             .tag("source", reading.source).tag("site", str(reading.extra.get("site_id") or "unassigned")).time(reading.ts))
        for k, v in reading.numeric_fields().items():
            p.field(k, v)
        p.field("online", 1 if reading.online else 0)
        if reading.status:
            p.field("status", str(reading.status))
        p.field("alarm_count", len([a for a in reading.alarms if a.active]))
        pts = [p]
        for a in reading.alarms:
            pts.append(Point("alarm").tag("device_id", reading.device_id).tag("brand", reading.brand).tag("code", a.code)
                       .tag("site", str(reading.extra.get("site_id") or "unassigned"))
                       .tag("category", a.category or "unknown")
                       .field("active", 1 if a.active else 0).field("message", a.message or "").field("severity", a.severity)
                       .field("advice", a.advice or "")
                       .time(a.raised_at or reading.ts))
        return pts

    async def write(self, reading: Reading) -> None:
        import asyncio
        pts = self.points(reading, self.measurement)
        await asyncio.get_running_loop().run_in_executor(None, lambda: self._write.write(bucket=self.bucket, org=self.org, record=pts))
