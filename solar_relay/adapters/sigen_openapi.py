"""Sigenergy official OpenAPI (developer.sigencloud.com) - PUSH model.

Sigen publishes to the vendor over MQTT on three subscriptions: Telemetry (default every 5 min),
System Data (static info, on change) and Alarm (alarmCode + status generation/recovery).  The broker
host / credentials / topic names are issued by Sigenergy when you board as a vendor and can be seen
in the Open Platform "Control Center -> Data Subscription" page.

options:
  host, port(8883), username, password, tls(true), client_id
  telemetry_topic, system_topic, alarm_topic          (exact strings from Sigen)
  system_ids: [KXGCS1727160960, ...]   optional filter; empty = accept every system pushed to us
Readings are emitted per systemId with device_id = "<device_id>:<systemId>" (or just device_id when
exactly one system is configured).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ..schema import Alarm, Reading, clamp_soc
from .base import PushAdapter

log = logging.getLogger("solar_relay.sigen")

# Telemetry signal name -> Reading attribute (values arrive as strings)
TELEMETRY_MAP = {
    "pvPowerW": "pv_w",
    "inverterActivePowerW": "ac_w",
    "inverterReactivePowerVar": "reactive_var",
    "storageSOC%": "soc",
    "storageChargeDischargePowerW": "batt_w",     # Sigen: negative = discharging (matches relay)
}
EXTRA_KEYS = (
    "gridPhaseAActivePowerW", "gridPhaseBActivePowerW", "gridPhaseCActivePowerW",
    "inverterPhaseAActivePowerW", "inverterPhaseBActivePowerW", "inverterPhaseCActivePowerW",
    "inverterMaxChargePowerW", "inverterMaxDischargePowerW", "inverterMaxFeedInActivePowerW",
    "inverterMaxAbsorptionActivePowerW", "storageChargeCapacityWh", "storageDischargeCapacityWh",
)


def parse_telemetry(payload: dict, device_id: str, brand: str = "sigen") -> Reading:
    vals = payload.get("value", {}) or {}

    def f(k: str) -> float | None:
        v = vals.get(k)
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    ts = payload.get("statisticsTime")
    r = Reading(device_id=device_id, brand=brand, source="sigen_openapi")
    if ts:
        ts = int(ts)
        r.ts = datetime.fromtimestamp(ts / 1000 if ts > 10**11 else ts, tz=timezone.utc)
    for k, attr in TELEMETRY_MAP.items():
        setattr(r, attr, f(k))
    r.soc = clamp_soc(r.soc)
    g = f("gridActivePowerW")
    if g is not None:
        r.grid_w = g           # Sigen sample: pv 1740 + batt discharge 2464 -> grid -4151 = exporting; same sign as relay
    r.reactive_var = f("gridReactivePowerVar") if r.reactive_var is None else r.reactive_var
    for k in EXTRA_KEYS:
        if k in vals:
            r.extra[k] = f(k)
    r.extra.update(systemId=payload.get("systemId"), snCode=payload.get("snCode"))
    return r


def parse_alarm(payload: dict, device_id: str, brand: str = "sigen") -> Reading:
    ts = payload.get("changeTime")
    raised = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc) if ts else None
    r = Reading(device_id=device_id, brand=brand, source="sigen_openapi")
    r.alarms.append(Alarm(code=f"sigen.{payload.get('alarmCode')}",
                          active=str(payload.get("status", "generation")).lower() == "generation",
                          severity="fault", raised_at=raised, raw=dict(payload)))
    r.extra.update(systemId=payload.get("systemId"), event="alarm")
    return r


class SigenOpenApiAdapter(PushAdapter):
    name = "sigen_openapi"
    default_brand = "sigen"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "sigen", interval_s, **options)
        self.host = options["host"]
        self.port = int(options.get("port", 8883))
        self.username = options.get("username")
        self.password = options.get("password")
        self.tls = bool(options.get("tls", True))
        self.client_id = options.get("client_id", f"solar-relay-{device_id}")
        self.topics = {k: options.get(f"{k}_topic") for k in ("telemetry", "system", "alarm")}
        self.system_ids = set(options.get("system_ids", []) or [])
        self._queue: asyncio.Queue[Reading] = asyncio.Queue()
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _dev_id(self, system_id: str | None) -> str:
        if len(self.system_ids) == 1 or not system_id:
            return self.device_id
        return f"{self.device_id}:{system_id}"

    def _handle(self, topic: str, raw: bytes) -> None:
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] bad payload on %s: %s", self.device_id, topic, exc)
            return
        items = data if isinstance(data, list) else [data]
        for item in items:
            sid = item.get("systemId")
            if self.system_ids and sid not in self.system_ids:
                continue
            if topic == self.topics["alarm"] or "alarmCode" in item:
                r = parse_alarm(item, self._dev_id(sid), self.brand)
            elif topic == self.topics["system"]:
                r = Reading(device_id=self._dev_id(sid), brand=self.brand, source=self.name)
                r.extra.update(event="system_data", **{k: v for k, v in item.items() if k != "value"})
                r.extra.update(item.get("value", {}) or {})
            else:
                r = parse_telemetry(item, self._dev_id(sid), self.brand)
            assert self._loop is not None
            self._loop.call_soon_threadsafe(self._queue.put_nowait, r)

    async def start(self) -> None:
        import paho.mqtt.client as mqtt
        self._loop = asyncio.get_running_loop()
        c = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
        if self.username:
            c.username_pw_set(self.username, self.password)
        if self.tls:
            c.tls_set()

        def on_connect(client, userdata, flags, rc, *a):  # noqa: ANN001
            log.info("[%s] Sigen MQTT connected rc=%s", self.device_id, rc)
            for t in self.topics.values():
                if t:
                    client.subscribe(t, qos=1)

        def on_message(client, userdata, msg):  # noqa: ANN001
            self._handle(msg.topic, msg.payload)

        c.on_connect, c.on_message = on_connect, on_message
        c.connect_async(self.host, self.port, keepalive=60)
        c.loop_start()
        self._client = c

    async def stop(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()

    async def stream(self) -> AsyncIterator[Reading]:
        while True:
            yield await self._queue.get()
