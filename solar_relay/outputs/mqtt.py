"""MQTT output.

Topics (prefix default "solar"):
  {prefix}/{device_id}/state            retained JSON with every field
  {prefix}/{device_id}/{field}          one topic per numeric field (when per_field: true)
  {prefix}/{device_id}/availability     online / offline
  {prefix}/{device_id}/alarm            JSON list of active alarms
options: host, port(1883), username, password, tls(false), prefix(solar), per_field(true), qos(0), client_id
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from ..schema import Reading
from .base import BaseOutput

log = logging.getLogger("solar_relay.mqtt")


def topic_safe(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)


class MqttOutput(BaseOutput):
    name = "mqtt"

    def __init__(self, host: str, port: int = 1883, username: str | None = None, password: str | None = None,
                 tls: bool = False, prefix: str = "solar", per_field: bool = True, qos: int = 0,
                 client_id: str = "solar-relay", **options: Any):
        super().__init__(**options)
        self.host, self.port, self.username, self.password, self.tls = host, int(port), username, password, tls
        self.prefix, self.per_field, self.qos, self.client_id = prefix.strip("/"), per_field, int(qos), client_id
        self._client = None
        self._connected = asyncio.Event()

    async def start(self) -> None:
        import paho.mqtt.client as mqtt
        loop = asyncio.get_running_loop()
        c = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
        if self.username:
            c.username_pw_set(self.username, self.password)
        if self.tls:
            c.tls_set()
        c.will_set(f"{self.prefix}/relay/availability", "offline", retain=True)

        def on_connect(client, userdata, flags, rc, *a):  # noqa: ANN001
            log.info("MQTT connected to %s:%s rc=%s", self.host, self.port, rc)
            client.publish(f"{self.prefix}/relay/availability", "online", retain=True)
            loop.call_soon_threadsafe(self._connected.set)

        c.on_connect = on_connect
        c.connect_async(self.host, self.port, keepalive=60)
        c.loop_start()
        self._client = c

    async def stop(self) -> None:
        if self._client is not None:
            self._client.publish(f"{self.prefix}/relay/availability", "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()

    def publish(self, topic: str, payload: Any, retain: bool = True) -> None:
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False, default=str)
        self._client.publish(topic, payload, qos=self.qos, retain=retain)

    def device_topic(self, reading: Reading) -> str:
        return f"{self.prefix}/{topic_safe(reading.device_id)}"

    async def write(self, reading: Reading) -> None:
        base = self.device_topic(reading)
        self.publish(f"{base}/availability", "online" if reading.online else "offline")
        self.publish(f"{base}/state", reading.to_dict())
        self.publish(f"{base}/alarm", [a.__dict__ for a in reading.alarms if a.active])
        if self.per_field:
            for k, v in reading.numeric_fields().items():
                self.publish(f"{base}/{k}", str(round(v, 3)))
            if reading.status:
                self.publish(f"{base}/status", reading.status)
