"""FastAPI app + the ``web`` output that feeds it.

config.yaml:
    outputs:
      - type: web
        options: {host: 0.0.0.0, port: 8080}
    sites:
      - {id: site-a, name: บ้านคุณสมชาย, customer: สมชาย ใจดี, phone: "081-234-5678", devices: [huawei-sun2000]}

Endpoints:  /            Thai single-page UI
            /api/state   everything the UI shows (sites, devices, active alarms, history, totals)
            /api/sites   /api/devices/{id}   /api/alarms   POST /api/alarms/ack   POST /api/probe   /api/health
"""
from __future__ import annotations

import asyncio
import io
import logging
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from ..config import RelayConfig
from ..outputs.base import BaseOutput
from ..schema import Reading
from .state import State

log = logging.getLogger("solar_relay.web")
STATIC = Path(__file__).with_name("static")

try:  # request models must live at module level so FastAPI can resolve the (string) annotations
    from pydantic import BaseModel as _BaseModel
except ImportError:  # pragma: no cover - web extra not installed
    _BaseModel = object  # type: ignore[assignment,misc]


class AckBody(_BaseModel):
    device_id: str
    code: str
    note: str = ""
    by: str = ""


class SiteBody(_BaseModel):
    id: str
    name: str | None = None
    customer: str | None = None
    phone: str | None = None
    address: str | None = None
    note: str | None = None
    devices: list[str] | None = None


class ProbeBody(_BaseModel):
    host: str = ""
    serial: str | None = None
    rtu: str | None = None
    baud: int = 9600
    maps: str | None = None
    units: str | None = None
    timeout: float = 3.0
    scan: str | None = None        # CIDR to sweep, or "auto" for the relay host's /24
    ports: str | None = None


def create_app(state: State) -> Any:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, JSONResponse

    app = FastAPI(title="solar-relay", version="0.1.0", docs_url="/api/docs", redoc_url=None)
    app.state.relay_state = state

    @app.get("/", include_in_schema=False)
    async def index() -> Any:
        return FileResponse(STATIC / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        snap = state.snapshot()
        return {"ok": True, "devices": snap["totals"]["devices"], "online": snap["totals"]["online"], "alarms": snap["totals"]["alarms"]}

    @app.get("/api/state")
    async def api_state() -> Any:
        return JSONResponse(state.snapshot())

    @app.get("/api/sites")
    async def api_sites() -> Any:
        return JSONResponse(state.snapshot()["sites"])

    @app.post("/api/sites")
    async def api_site_save(body: SiteBody) -> dict[str, Any]:
        try:
            return state.save_site({k: v for k, v in body.__dict__.items() if not k.startswith("_")})
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc)) from None

    @app.delete("/api/sites/{site_id}")
    async def api_site_delete(site_id: str) -> dict[str, Any]:
        if not state.remove_site(site_id):
            raise HTTPException(404, "unknown site")
        return {"ok": True}

    @app.get("/api/history")
    async def api_history(site: str | None = None, device: str | None = None, hours: float = 24, points: int = 240) -> Any:
        if device:
            devs = [device]
        elif site:
            s = next((x for x in state.snapshot()["sites"] if x["id"] == site), None)
            if s is None:
                raise HTTPException(404, "unknown site")
            devs = [d["device_id"] for d in s["devices"]]
        else:
            devs = state.configured_devices() or sorted(state.readings)
        return JSONResponse(state.history_series(devs, hours=min(max(hours, 0.5), 48), points=min(max(points, 24), 600)))

    @app.get("/api/devices/{device_id}")
    async def api_device(device_id: str) -> Any:
        if device_id not in state.readings and device_id not in state.configured_devices():
            raise HTTPException(404, "unknown device")
        return JSONResponse(state.device_view(device_id))

    @app.get("/api/alarms")
    async def api_alarms() -> Any:
        snap = state.snapshot()
        return JSONResponse({"active": snap["active_alarms"], "history": snap["history"]})

    @app.post("/api/alarms/ack")
    async def api_ack(body: AckBody) -> dict[str, Any]:
        ok = state.ack(body.device_id, body.code, body.note, body.by)
        if not ok:
            raise HTTPException(404, "alarm not active")
        return {"ok": True}

    @app.get("/api/catalog/{code}")
    async def api_catalog(code: str, message: str = "") -> Any:
        from ..alarm_catalog import lookup
        return JSONResponse(lookup(code, message) or {})

    def _probe_args(body: ProbeBody) -> Any:
        import argparse
        if not body.host and not body.rtu and not body.scan:
            raise HTTPException(400, "host, rtu or scan required")
        port = None
        if body.host and body.ports:            # single-host probe: first port forces the Modbus port (e.g. 6607)
            try:
                port = int(str(body.ports).split(",")[0])
            except ValueError:
                raise HTTPException(400, "ports must be numeric") from None
        return argparse.Namespace(host=body.host or None, port=port, serial=body.serial or None, rtu=body.rtu or None,
                                  baud=body.baud, maps=body.maps or None, units=body.units or None, timeout=body.timeout, json=False,
                                  scan=body.scan or None, ports=body.ports or None)

    @app.post("/api/probe")
    async def api_probe(body: ProbeBody) -> dict[str, Any]:
        """Synchronous probe (blocks until done)."""
        from ..probe import run as probe_run
        args = _probe_args(body)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = await asyncio.wait_for(probe_run(args), timeout=600)
        return {"rc": rc, "output": buf.getvalue()}

    # ---- live console: start a probe job, poll its log -------------------------------------------
    jobs: dict[str, dict[str, Any]] = {}

    class _LineSink(io.TextIOBase):
        def __init__(self, job: dict[str, Any]):
            super().__init__()
            self.job, self._buf = job, ""

        def write(self, s: str) -> int:  # type: ignore[override]
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self.job["lines"].append(line)
            return len(s)

        def flush(self) -> None:
            if self._buf:
                self.job["lines"].append(self._buf)
                self._buf = ""

    def _run_job(job: dict[str, Any], args: Any) -> None:
        """Runs in its own thread + event loop so the job survives the request that started it."""
        from ..probe import run as probe_run

        async def _with_timeout() -> int:
            return await asyncio.wait_for(probe_run(args), timeout=900)

        sink = _LineSink(job)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            task = loop.create_task(_with_timeout())
            job["cancel"] = lambda: loop.call_soon_threadsafe(task.cancel)
            with redirect_stdout(sink):
                job["rc"] = loop.run_until_complete(task)
        except asyncio.CancelledError:
            job["lines"].append("!! ยกเลิกโดยผู้ใช้")
            job["rc"] = 3
        except BaseException as exc:  # noqa: BLE001 - report timeouts too
            job["lines"].append(f"!! error: {exc!r}")
            job["rc"] = 2
        finally:
            sink.flush()
            job["done"] = True
            job.pop("cancel", None)
            loop.close()

    @app.post("/api/probe/start")
    async def api_probe_start(body: ProbeBody) -> dict[str, Any]:
        import uuid
        args = _probe_args(body)
        running = next((j for j in jobs.values() if not j["done"]), None)
        if running:
            return {"job": running["id"], "already_running": True}
        import threading
        job_id = uuid.uuid4().hex[:8]
        job: dict[str, Any] = {"id": job_id, "lines": [], "done": False, "rc": None}
        jobs.clear()
        jobs[job_id] = job
        threading.Thread(target=_run_job, args=(job, args), name=f"probe-{job_id}", daemon=True).start()
        return {"job": job_id}

    @app.post("/api/probe/cancel")
    async def api_probe_cancel(job: str) -> dict[str, Any]:
        j = jobs.get(job)
        if j is None:
            raise HTTPException(404, "unknown job")
        cancel = j.get("cancel")
        if j["done"] or cancel is None:
            return {"ok": False, "done": j["done"]}
        cancel()
        return {"ok": True}

    @app.get("/api/probe/log")
    async def api_probe_log(job: str, offset: int = 0) -> dict[str, Any]:
        j = jobs.get(job)
        if j is None:
            raise HTTPException(404, "unknown job")
        return {"job": job, "lines": j["lines"][offset:], "offset": len(j["lines"]), "done": j["done"], "rc": j["rc"]}

    # ---- network info -------------------------------------------------------------------------------
    @app.get("/api/net")
    async def api_net() -> Any:
        from ..netinfo import local_info
        return JSONResponse(await asyncio.get_running_loop().run_in_executor(None, local_info))

    @app.get("/api/net/discover")
    async def api_net_discover(cidr: str | None = None, online: bool = True) -> Any:
        from ..netinfo import discover
        return JSONResponse(await asyncio.get_running_loop().run_in_executor(None, lambda: discover(cidr or None, online)))

    return app


class WebOutput(BaseOutput):
    """Output that stores readings in :class:`State` and serves the UI with uvicorn inside the relay loop."""

    name = "web"

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, history_len: int = 2000, log_level: str = "warning", **options: Any):
        super().__init__(**options)
        self.host, self.port, self.log_level = host, int(port), log_level
        self.state = State(history_len=int(history_len))
        self._server = None
        self._task: asyncio.Task | None = None

    def attach(self, cfg: RelayConfig) -> None:
        self.state.attach(cfg)

    async def start(self) -> None:
        try:
            import uvicorn
        except ImportError as exc:
            raise ImportError("web UI needs: pip install 'solar-relay[web]'  (fastapi + uvicorn)") from exc
        app = create_app(self.state)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level=self.log_level, loop="none", lifespan="off")
        self._server = uvicorn.Server(config)
        self._server.install_signal_handlers = lambda: None   # relay owns SIGINT/SIGTERM
        self._task = asyncio.create_task(self._server.serve())
        log.info("web UI on http://%s:%d/  (API docs: /api/docs)", self.host if self.host != "0.0.0.0" else "localhost", self.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def write(self, reading: Reading) -> None:
        self.state.update(reading)


def main(argv: list[str] | None = None) -> int:
    """Standalone dev server with demo data:  python -m solar_relay.web.server [--port 8080]"""
    import argparse
    from datetime import datetime, timezone

    from ..alarm_catalog import enrich_reading
    from ..config import DeviceConfig, SiteConfig
    from ..schema import Alarm

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    a = p.parse_args(argv)
    import uvicorn

    state = State()
    cfg = RelayConfig(devices=[DeviceConfig("huawei-sun2000", "modbus", "huawei"), DeviceConfig("solis-s6-hybrid", "modbus", "solis"),
                               DeviceConfig("deye-house", "solarman", "deye")],
                      sites=[SiteConfig("site-a", "บ้านคุณสมชาย", "สมชาย ใจดี", "081-234-5678", "นนทบุรี", devices=["huawei-sun2000"]),
                             SiteConfig("site-b", "โรงงาน ABC", "คุณวิภา", "02-123-4567", "สมุทรปราการ", devices=["solis-s6-hybrid", "deye-house"])])
    state.attach(cfg)
    demo = [
        Reading("huawei-sun2000", "huawei", "modbus", pv_w=5200, ac_w=5100, grid_w=-1800, load_w=3300, batt_w=0, energy_day_kwh=18.4,
                energy_total_kwh=12345, grid_v=231, grid_hz=50.02, temp_c=42, status="On-grid",
                strings={"pv1": {"v": 610, "a": 8.4, "w": 5124}}),
        Reading("solis-s6-hybrid", "solis", "modbus", pv_w=3100, ac_w=2900, grid_w=400, load_w=2600, batt_w=900, soc=64, energy_day_kwh=9.7,
                grid_v=228, grid_hz=49.98, temp_c=39, status="Generating",
                alarms=[Alarm(code="solis.PV ISO-PRO", raised_at=datetime.now(timezone.utc))]),
        Reading("deye-house", "deye", "solarman", online=False, status="offline: timeout", alarms=[Alarm(code="deye.F35")]),
    ]
    for r in demo:
        enrich_reading(r)
        state.update(r)
    print(f"demo web UI: http://{a.host}:{a.port}/", file=sys.stderr)
    uvicorn.run(create_app(state), host=a.host, port=a.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
