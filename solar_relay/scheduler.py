"""asyncio poll loop: one task per pull-adapter, one long-running task per push-adapter,
readings fan out to every configured output."""
from __future__ import annotations

import asyncio
import logging

from .adapters.base import BaseAdapter, PushAdapter
from .alarm_catalog import enrich_reading
from .config import RelayConfig
from .outputs.base import BaseOutput
from .registry import get_adapter_class, get_output_class
from .schema import Reading

log = logging.getLogger("solar_relay.scheduler")


class Relay:
    def __init__(self, cfg: RelayConfig):
        self.cfg = cfg
        self.adapters: list[BaseAdapter] = []
        self.outputs: list[BaseOutput] = []
        self.queue: asyncio.Queue[Reading] = asyncio.Queue(maxsize=10_000)
        self._stop = asyncio.Event()

    # ---- construction ---------------------------------------------------
    def build(self) -> Relay:
        for d in self.cfg.devices:
            if not d.enabled:
                continue
            cls = get_adapter_class(d.adapter)
            interval = d.interval_s or self.cfg.poll_interval_s
            self.adapters.append(cls(device_id=d.id, brand=d.brand, interval_s=interval, **d.options))
        for o in self.cfg.outputs:
            if not o.enabled:
                continue
            cls = get_output_class(o.type)
            out = cls(**o.options)
            if hasattr(out, "attach"):      # outputs that need the whole config (web UI: sites, devices)
                out.attach(self.cfg)
            self.outputs.append(out)
        if not self.adapters:
            raise RuntimeError("no enabled devices in config")
        if not self.outputs:
            log.warning("no outputs configured, readings will only be logged")
        return self

    # ---- run ------------------------------------------------------------
    async def run(self, once: bool = False) -> None:
        for o in self.outputs:
            await o.start()
        pump = asyncio.create_task(self._pump())
        workers: list[asyncio.Task] = []
        try:
            for a in self.adapters:
                await a.start()
                if isinstance(a, PushAdapter):
                    workers.append(asyncio.create_task(self._push_loop(a)))
                else:
                    workers.append(asyncio.create_task(self._poll_loop(a, once)))
            if once:
                await asyncio.gather(*workers, return_exceptions=True)
                await self.queue.join()
            else:
                await self._stop.wait()
        finally:
            for t in workers:
                t.cancel()
            pump.cancel()
            for a in self.adapters:
                await a.stop()
            for o in self.outputs:
                await o.stop()

    def stop(self) -> None:
        self._stop.set()

    def _tag_site(self, r: Reading) -> None:
        site = self.cfg.site_of(r.device_id) or self.cfg.site_of(r.device_id.split(":", 1)[0])
        if site:
            r.extra.setdefault("site_id", site.id)
            r.extra.setdefault("site_name", site.name)
            r.extra.setdefault("customer", site.customer)

    async def _poll_loop(self, adapter: BaseAdapter, once: bool) -> None:
        backoff = adapter.interval_s
        while not self._stop.is_set():
            try:
                readings = await adapter.read()
                for r in readings:
                    r.derive_missing()
                    enrich_reading(r)
                    self._tag_site(r)
                    await self.queue.put(r)
                backoff = adapter.interval_s
                adapter.consecutive_errors = 0
            except Exception as exc:  # noqa: BLE001 - keep the loop alive whatever the vendor does
                adapter.consecutive_errors += 1
                log.warning("[%s] read failed (%d): %s", adapter.device_id, adapter.consecutive_errors, exc)
                if adapter.consecutive_errors >= 3:
                    off = adapter.offline_reading(str(exc))
                    self._tag_site(off)
                    await self.queue.put(off)
                backoff = min(adapter.interval_s * 2 ** min(adapter.consecutive_errors, 4), 900)
            if once:
                return
            await asyncio.sleep(backoff)

    async def _push_loop(self, adapter: PushAdapter) -> None:
        async for reading in adapter.stream():
            reading.derive_missing()
            enrich_reading(reading)
            self._tag_site(reading)
            await self.queue.put(reading)
            if self._stop.is_set():
                break

    async def _pump(self) -> None:
        while True:
            reading = await self.queue.get()
            try:
                await self._dispatch(reading)
            finally:
                self.queue.task_done()

    async def _dispatch(self, reading: Reading) -> None:
        if not self.outputs:
            log.info("%s", reading.to_dict())
            return
        results = await asyncio.gather(*(o.write(reading) for o in self.outputs), return_exceptions=True)
        for o, res in zip(self.outputs, results):
            if isinstance(res, Exception):
                log.warning("[output %s] write failed: %s", o.name, res)
