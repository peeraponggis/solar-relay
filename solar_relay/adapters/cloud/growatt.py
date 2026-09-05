"""Growatt ShineServer (UNOFFICIAL, via the `growattServer` PyPI library).

options: username, password, plant_id (optional: first plant), server_url (optional)
Supports MIX / SPH (hybrid), TLX / MIN (hybrid-X) and plain string inverters as far as the library does.
"""
from __future__ import annotations

import logging
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.growatt")


class GrowattAdapter(CloudAdapter):
    name = "cloud:growatt"
    default_brand = "growatt"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "growatt", interval_s, **options)
        self.username = options["username"]
        self.password = options["password"]
        self.plant_id = options.get("plant_id")
        self.server_url = options.get("server_url")
        self._api = None
        self._user_id = None
        self._devices: list[dict] = []

    def _login_sync(self) -> None:
        import growattServer
        self._api = growattServer.GrowattApi(add_random_user_id=True)
        if self.server_url:
            self._api.server_url = self.server_url
        login = self._api.login(self.username, self.password)
        if not login.get("success", True):
            raise PermissionError(f"Growatt login failed: {login}")
        self._user_id = login["user"]["id"] if "user" in login else login.get("userId")
        if not self.plant_id:
            plants = self._api.plant_list(self._user_id)
            self.plant_id = plants["data"][0]["plantId"]
        self._devices = self._api.device_list(self.plant_id)

    async def start(self) -> None:
        await self.run_blocking(self._login_sync)

    def _read_sync(self) -> list[Reading]:
        out: list[Reading] = []
        for dev in self._devices:
            sn, dtype = dev.get("deviceSn"), str(dev.get("deviceType", "")).lower()
            r = Reading(device_id=f"{self.device_id}:{sn}" if len(self._devices) > 1 else self.device_id,
                        brand=self.brand, source=self.name)
            r.extra.update(sn=sn, device_type=dtype, plant=self.plant_id)
            try:
                if dtype in ("mix", "sph"):
                    s = self._api.mix_system_status(sn, self.plant_id)
                    r.pv_w = float(s.get("ppv", 0)) * 1000
                    r.load_w = float(s.get("pLocalLoad", 0)) * 1000
                    r.grid_w = (float(s.get("pactouser", 0)) - float(s.get("pactogrid", 0))) * 1000
                    r.batt_w = (float(s.get("chargePower", 0)) - float(s.get("pdisCharge1", 0))) * 1000
                    r.soc = clamp_soc(s.get("SOC"))
                    r.batt_v = s.get("vBat")
                    r.grid_v, r.grid_hz = s.get("vAc1"), s.get("fAc")
                    r.ac_w = float(s.get("pac", 0)) * 1000 if s.get("pac") is not None else None
                    d = self._api.mix_totals(sn, self.plant_id)
                    r.energy_day_kwh, r.energy_total_kwh = d.get("epvToday"), d.get("epvTotal")
                    r.grid_import_day_kwh, r.grid_export_day_kwh = d.get("etouserToday"), d.get("etogridToday")
                    r.batt_charge_day_kwh, r.batt_discharge_day_kwh = d.get("echargeToday"), d.get("edischarge1Today")
                    r.load_day_kwh = d.get("elocalLoadToday")
                elif dtype in ("tlx", "min"):
                    s = self._api.tlx_system_status(self.plant_id, sn) if hasattr(self._api, "tlx_system_status") else {}
                    r.pv_w = float(s.get("ppv", 0)) * 1000 if s else None
                    r.load_w = float(s.get("pLocalLoad", 0)) * 1000 if s else None
                    r.grid_w = (float(s.get("pactouser", 0)) - float(s.get("pactogrid", 0))) * 1000 if s else None
                    r.batt_w = (float(s.get("chargePower", 0)) - float(s.get("pdisCharge1", 0))) * 1000 if s else None
                    r.soc = clamp_soc(s.get("SOC")) if s else None
                    d = self._api.tlx_energy_overview(self.plant_id, sn) if hasattr(self._api, "tlx_energy_overview") else {}
                    r.energy_day_kwh, r.energy_total_kwh = d.get("epvToday"), d.get("epvTotal")
                else:
                    s = self._api.inverter_data(sn, None) if hasattr(self._api, "inverter_data") else {}
                    r.ac_w = s.get("pac")
                    r.pv_w = s.get("ppv")
                    r.energy_day_kwh, r.energy_total_kwh = s.get("eToday") or s.get("e_today"), s.get("eTotal") or s.get("e_total")
                    r.temp_c = s.get("temperature")
                    r.grid_v, r.grid_hz = s.get("vac1"), s.get("fac")
                    r.status = str(s.get("status") or "")
                    fault = s.get("faultCode") or s.get("errorCode")
                    if fault and str(fault) not in ("0", "None"):
                        r.alarms.append(Alarm(code=f"growatt.{fault}", message=str(s.get("faultInfo") or ""), severity="fault"))
                r.online = str(dev.get("lost", "false")).lower() != "true"
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] Growatt %s (%s): %s", self.device_id, sn, dtype, exc)
                r.online = False
                r.status = f"error: {exc}"[:200]
            out.append(r)
        return out

    async def read(self) -> list[Reading]:
        if self._api is None:
            await self.start()
        return await self.run_blocking(self._read_sync)
