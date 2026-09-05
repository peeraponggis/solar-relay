"""Sungrow iSolarCloud OpenAPI (official; needs appkey + x-access-key from Sungrow developer portal,
newer accounts also need the RSA public key for password encryption -> option rsa_public_key).

Endpoints: /openapi/login, /openapi/getPowerStationList, /openapi/getDeviceList,
/openapi/getDeviceRealTimeData (point ids), /openapi/getPowerStationDetail
Default point ids below follow the iSolarCloud "device type 11 (inverter) / 14 (ESS)" tables; override
with options.point_map if your firmware exposes different points.

options:
  app_key, access_key, username, password, base_url (https://gateway.isolarcloud.com | .eu | .com.hk | .au)
  ps_id (optional), rsa_public_key (optional PEM/base64), point_map (optional {point_id: reading_field})
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.sungrow")

# point id -> (reading field, scale to relay unit). Verify against your account's point list.
DEFAULT_POINTS_INV = {
    "p13003": ("ac_w", 1.0),            # total active power W
    "p13005": ("pv_w", 1.0),            # total DC power W
    "p13011": ("energy_day_kwh", 1.0),  # daily yield kWh
    "p13112": ("energy_total_kwh", 1.0),
    "p13141": ("soc", 1.0),             # battery level %
    "p13126": ("batt_w_charge", 1.0),   # battery charging power W
    "p13150": ("batt_w_discharge", 1.0),# battery discharging power W
    "p13119": ("grid_import_w", 1.0),   # purchased power W
    "p13121": ("grid_export_w", 1.0),   # feed-in power W
    "p13149": ("load_w", 1.0),          # total load power W
    "p13158": ("load_day_kwh", 1.0),
    "p13173": ("grid_export_day_kwh", 1.0),
    "p13199": ("grid_import_day_kwh", 1.0),
    "p13028": ("temp_c", 1.0),
    "p13004": ("grid_hz", 1.0),
}


class SungrowISolarCloudAdapter(CloudAdapter):
    name = "cloud:sungrow"
    default_brand = "sungrow"
    base_url = "https://gateway.isolarcloud.com"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 300, **options: Any):
        super().__init__(device_id, brand or "sungrow", interval_s, **options)
        self.app_key = options["app_key"]
        self.access_key = options["access_key"]
        self.username = options["username"]
        self.password = options["password"]
        self.rsa_public_key = options.get("rsa_public_key")
        self.ps_id = options.get("ps_id")
        self.points = {**DEFAULT_POINTS_INV, **(options.get("point_map") or {})}
        self._token: str | None = None
        self._devices: list[dict] = []

    def _headers(self) -> dict[str, str]:
        h = {"x-access-key": self.access_key, "sys_code": "901", "Content-Type": "application/json"}
        if self._token:
            h["token"] = self._token
        return h

    def _password(self) -> str:
        if not self.rsa_public_key:
            return self.password
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = self.rsa_public_key
        if "BEGIN" not in key:
            key = f"-----BEGIN PUBLIC KEY-----\n{key}\n-----END PUBLIC KEY-----"
        pub = serialization.load_pem_public_key(key.encode())
        return base64.b64encode(pub.encrypt(self.password.encode(), padding.PKCS1v15())).decode()

    async def _call(self, path: str, body: dict) -> Any:
        body = {"appkey": self.app_key, "lang": "_en_US", **body}
        j = await self.post_json(path, body, headers=self._headers())
        if str(j.get("result_code")) != "1":
            if str(j.get("result_code")) in ("E00003", "401") and self._token:
                self._token = None
                await self._login()
                return await self._call(path, body)
            raise OSError(f"iSolarCloud {path}: {j.get('result_msg')} ({j.get('result_code')})")
        return j.get("result_data")

    async def _login(self) -> None:
        data = await self._call("/openapi/login", {"user_account": self.username, "user_password": self._password(),
                                                   "login_type": "1"})
        self._token = data["token"]

    async def start(self) -> None:
        await self._login()
        if not self.ps_id:
            ps = await self._call("/openapi/getPowerStationList", {"curPage": 1, "size": 20})
            self.ps_id = ps["pageList"][0]["ps_id"]
        devs = await self._call("/openapi/getDeviceList", {"ps_id": self.ps_id, "curPage": 1, "size": 50})
        self._devices = [d for d in devs.get("pageList", []) if int(d.get("device_type", 0)) in (1, 11, 14)]
        log.info("[%s] iSolarCloud ps_id=%s devices=%s", self.device_id, self.ps_id,
                 [(d.get("ps_key"), d.get("device_type")) for d in self._devices])

    async def read(self) -> list[Reading]:
        if not self._token:
            await self.start()
        out: list[Reading] = []
        for dev in self._devices:
            data = await self._call("/openapi/getDeviceRealTimeData",
                                    {"device_type": dev["device_type"], "ps_key_list": [dev["ps_key"]],
                                     "point_id_list": [p.lstrip("p") for p in self.points]})
            r = Reading(device_id=f"{self.device_id}:{dev.get('ps_key')}" if len(self._devices) > 1 else self.device_id,
                        brand=self.brand, source=self.name)
            r.extra.update(ps_key=dev.get("ps_key"), device_type=dev.get("device_type"), sn=dev.get("device_sn"))
            vals: dict[str, float] = {}
            for item in data.get("device_point_list", []) or []:
                dp = item.get("device_point", {}) or {}
                for pid, (field, scale) in self.points.items():
                    raw = dp.get(pid)
                    if raw not in (None, "", "--"):
                        try:
                            vals[field] = float(raw) * scale
                        except ValueError:
                            pass
                st = dp.get("dev_status")
                if st is not None:
                    r.status = {"1": "Run", "2": "Fault", "3": "Standby"}.get(str(st), f"status {st}")
                    if str(st) == "2":
                        r.alarms.append(Alarm(code="sungrow.dev_status.2", message="device fault", severity="fault"))
            for f in ("ac_w", "pv_w", "energy_day_kwh", "energy_total_kwh", "load_w", "load_day_kwh",
                      "grid_export_day_kwh", "grid_import_day_kwh", "temp_c", "grid_hz"):
                if f in vals:
                    setattr(r, f, vals[f])
            if "soc" in vals:
                r.soc = clamp_soc(vals["soc"])
            if "batt_w_charge" in vals or "batt_w_discharge" in vals:
                r.batt_w = vals.get("batt_w_charge", 0.0) - vals.get("batt_w_discharge", 0.0)
            if "grid_import_w" in vals or "grid_export_w" in vals:
                r.grid_w = vals.get("grid_import_w", 0.0) - vals.get("grid_export_w", 0.0)
            out.append(r)
        return out
