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


class ProbeBody(_BaseModel):
    host: str = ""
    serial: str | None = None
    rtu: str | None = None
    baud: int = 9600
    maps: str | None = None
    units: str | None = None
    timeout: float = 3.0


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

    @app.post("/api/probe")
    async def api_probe(body: ProbeBody) -> dict[str, Any]:
        import argparse

        from ..probe import run as probe_run
        if not body.host and not body.rtu:
            raise HTTPException(400, "host or rtu required")
        args = argparse.Namespace(host=body.host or None, port=None, serial=body.serial or None, rtu=body.rtu or None,
                                  baud=body.baud, maps=body.maps or None, units=body.units or None, timeout=body.timeout, json=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = await asyncio.wait_for(probe_run(args), timeout=240)
        return {"rc": rc, "output": buf.getvalue()}

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
