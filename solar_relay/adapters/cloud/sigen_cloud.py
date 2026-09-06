"""Sigenergy mySigen cloud (UNOFFICIAL - same web-app API the mySigen portal / app uses; the official
OpenAPI is push-only and needs vendor boarding, see sigen_openapi).

Flow (reverse-engineered by the `sigen` PyPI package and GerardBrowne/sig-data):
  POST {api}/auth/oauth/token   form: grant_type=password, scope=server, username, password=AES(password), userDeviceId
                                Basic auth sigen:sigen + the web-app headers (sg-* / client-server)
  GET  {api}/device/owner/station/home                     -> stationId, stationName, pvCapacity, batteryCapacity, onGrid
  GET  {api}/device/sigen/station/energyflow?id=<station>  -> pvPower, loadPower, buySellPower, batteryPower, batterySoc, evPower ... (kW)
  POST {api}/data-process/sigen/station/statistics/energy  -> powerGeneration, powerUse, powerFromGrid, powerToGrid, esCharging, esDischarging (kWh)

options:
  username, password, region (apac | eu | us | cn; web-apac.sigencloud.com -> apac)
  station_ids: [..]   optional: extra station ids on the account (the "home" station is always included)
  grid_positive_is_import: true    buySellPower sign  (verify on site: buying at night must give grid_w > 0)
  battery_positive_is_charge: true batteryPower sign  (verify: charging must give batt_w > 0)
Poll interval >= 60 s (the app itself refreshes every ~10 s, be polite).
"""
from __future__ import annotations

import base64
import logging
import time
import uuid
from datetime import date, datetime, timezone
from typing import Any

from ...schema import Alarm, Reading, clamp_soc
from .base import CloudAdapter

log = logging.getLogger("solar_relay.cloud.sigen")

REGION_API = {"eu": "https://api-eu.sigencloud.com", "cn": "https://api-cn.sigencloud.com",
              "apac": "https://api-apac.sigencloud.com", "us": "https://api-us.sigencloud.com"}
CLIENT_SERVER = {"eu": "eu", "cn": "cn", "apac": "aus", "us": "us"}
WEB_APP_VERSION, WEB_APP_BUILD, WEB_APP_PACKAGE = "3.5.2", "1", "sigen_app"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) Gecko/20100101 Firefox/152.0"
STATION_STATUS = {0: "Normal", 1: "Warning", 2: "Fault", 3: "Offline"}


def encrypt_password(password: str) -> str:
    """AES-128-CBC with the web app's static key/iv ('sigensigensigenp'), PKCS7, base64 - what the portal sends."""
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    key = iv = b"sigensigensigenp"
    padder = padding.PKCS7(128).padder()
    data = padder.update(password.encode("utf-8")) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode()


def kw(v: Any) -> float | None:
    """Sigen app values are kW floats; guard against firmware that already reports W."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if abs(f) > 500 else f * 1000.0


def parse_energyflow(d: dict[str, Any], grid_import_positive: bool = True, batt_charge_positive: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["pv_w"] = kw(d.get("pvPower"))
    out["load_w"] = kw(d.get("loadPower"))
    out["ac_w"] = kw(d.get("acPower"))
    g = kw(d.get("buySellPower"))
    if g is not None:
        out["grid_w"] = g if grid_import_positive else -g
    b = kw(d.get("batteryPower"))
    if b is not None:
        out["batt_w"] = b if batt_charge_positive else -b
    out["soc"] = clamp_soc(d.get("batterySoc"))
    out["energy_day_kwh"] = float(d["pvDayNrg"]) if d.get("pvDayNrg") not in (None, "") else None
    extra = {k: d.get(k) for k in ("evPower", "generatorPower", "heatPumpPower", "thirdPvPower", "onGrid", "onOffGridStatus", "stationStatus") if k in d}
    out["extra"] = extra
    return out


class SigenCloudAdapter(CloudAdapter):
    name = "cloud:sigen"
    default_brand = "sigen"

    def __init__(self, device_id: str, brand: str = "", interval_s: int = 120, **options: Any):
        super().__init__(device_id, brand or "sigen", max(int(interval_s), 60), **options)
        self.username = str(options["username"])
        self._password_enc = encrypt_password(str(options["password"]))
        self.region = str(options.get("region", "apac")).lower()
        if self.region not in REGION_API:
            raise ValueError(f"[{device_id}] region must be one of {list(REGION_API)}")
        self.base_url = options.get("base_url") or REGION_API[self.region]
        self.extra_stations = [str(s) for s in options.get("station_ids", []) or []]
        self.grid_import_positive = bool(options.get("grid_positive_is_import", True))
        self.batt_charge_positive = bool(options.get("battery_positive_is_charge", True))
        self.user_device_id = str(int(time.time() * 1000))
        self.session_id = str(uuid.uuid4())
        self._token: str | None = None
        self._refresh: str | None = None
        self._expiry = 0.0
        self._stations: list[dict[str, Any]] = []

    # ---- headers / auth -------------------------------------------------
    def _headers(self, content_type: str, path: str, bearer: bool = True) -> dict[str, str]:
        origin = self.base_url.replace("https://api-", "https://app-", 1)
        ts = str(int(time.time() * 1000) * 1000)
        h = {
            "Accept": "*/*", "Accept-Language": "zh-CN,zh;", "User-Agent": USER_AGENT, "Content-Type": content_type,
            "Origin": origin, "Referer": f"{origin}/", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site",
            "lang": "en_US", "client-server": CLIENT_SERVER[self.region], "AUTH-CLIENT-ID": "sigen", "VERSION": "RELEASE",
            "sg-v": WEB_APP_VERSION, "sg-bui": WEB_APP_BUILD, "sg-env": "1", "sg-platform": "web", "sg-pkg": WEB_APP_PACKAGE,
            "sg-ts": ts, "sg-log-id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}{ts}")), "sg-session": self.session_id,
        }
        if bearer and self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def _token_request(self, form: dict[str, str]) -> None:
        r = await self._http.post(f"{self.base_url}/auth/oauth/token", data=form,
                                  headers=self._headers("application/x-www-form-urlencoded", "auth/oauth/token", bearer=False),
                                  auth=("sigen", "sigen"))
        if r.status_code == 401:
            raise PermissionError(f"Sigen login rejected (401): {r.text[:200]}")
        r.raise_for_status()
        j = r.json()
        data = j.get("data") or {}
        if not data.get("access_token"):
            raise PermissionError(f"Sigen login failed: {j.get('msg') or j}")
        self._token, self._refresh = data["access_token"], data.get("refresh_token")
        self._expiry = time.time() + float(data.get("expires_in", 3600)) - 60

    async def _login(self) -> None:
        await self._token_request({"scope": "server", "grant_type": "password", "userDeviceId": self.user_device_id,
                                   "username": self.username, "password": self._password_enc})

    async def _ensure_token(self) -> None:
        if self._token and time.time() < self._expiry:
            return
        if self._refresh:
            try:
                await self._token_request({"scope": "server", "grant_type": "refresh_token", "refresh_token": self._refresh})
                return
            except Exception as exc:  # noqa: BLE001
                log.debug("[%s] refresh failed, re-login: %s", self.device_id, exc)
        await self._login()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self._ensure_token()
        r = await self._http.get(f"{self.base_url}/{path}", params=params, headers=self._headers("application/json", path))
        if r.status_code == 401:
            self._token = None
            await self._ensure_token()
            r = await self._http.get(f"{self.base_url}/{path}", params=params, headers=self._headers("application/json", path))
        r.raise_for_status()
        j = r.json()
        if j.get("code") not in (0, "0", None) and j.get("data") is None:
            raise OSError(f"Sigen {path}: {j.get('msg')} (code {j.get('code')})")
        return j.get("data")

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        await self._ensure_token()
        r = await self._http.post(f"{self.base_url}/{path}", json=body, headers=self._headers("application/json", path))
        r.raise_for_status()
        j = r.json()
        return j.get("data")

    # ---- adapter --------------------------------------------------------
    async def start(self) -> None:
        await self._login()
        home = await self._get("device/owner/station/home") or {}
        stations: list[dict[str, Any]] = []
        if home.get("stationId") is not None:
            stations.append({"id": str(home["stationId"]), "name": home.get("stationName"), "pv_capacity_kw": home.get("pvCapacity"),
                             "battery_capacity_kwh": home.get("batteryCapacity"), "on_grid": home.get("onGrid")})
        for sid in self.extra_stations:
            if sid not in {s["id"] for s in stations}:
                stations.append({"id": sid, "name": None})
        if not stations:
            raise RuntimeError("Sigen: no station on this account")
        self._stations = stations
        log.info("[%s] Sigen stations: %s", self.device_id, [(s["id"], s.get("name")) for s in stations])

    async def read(self) -> list[Reading]:
        if not self._stations:
            await self.start()
        out: list[Reading] = []
        today = date.today().strftime("%Y-%m-%d")
        for st in self._stations:
            sid = st["id"]
            flow = await self._get("device/sigen/station/energyflow", {"id": sid}) or {}
            p = parse_energyflow(flow, self.grid_import_positive, self.batt_charge_positive)
            r = Reading(device_id=f"{self.device_id}:{sid}" if len(self._stations) > 1 else self.device_id, brand=self.brand, source=self.name)
            for k in ("pv_w", "load_w", "ac_w", "grid_w", "batt_w", "soc", "energy_day_kwh"):
                setattr(r, k, p.get(k))
            r.extra.update(p["extra"])
            r.extra.update(station=sid, name=st.get("name"), pv_capacity_kw=st.get("pv_capacity_kw"), battery_capacity_kwh=st.get("battery_capacity_kwh"))
            st_code = flow.get("stationStatus")
            if st_code is not None:
                try:
                    r.status = STATION_STATUS.get(int(st_code), f"status {st_code}")
                    if int(st_code) == 2:
                        r.alarms.append(Alarm(code="sigen.station.fault", message="station status = fault (ดูรหัสในแอป mySigen)", severity="fault"))
                    r.online = int(st_code) != 3
                except (TypeError, ValueError):
                    r.status = str(st_code)
            try:
                stats = await self._post("data-process/sigen/station/statistics/energy",
                                         {"stationId": sid, "dateFlag": "1", "startDate": today, "endDate": today, "fulfill": "false"})
                row = stats[-1] if isinstance(stats, list) and stats else (stats if isinstance(stats, dict) else {})
                if row:
                    r.energy_day_kwh = r.energy_day_kwh if r.energy_day_kwh is not None else _f(row.get("powerGeneration"))
                    r.load_day_kwh = _f(row.get("powerUse"))
                    r.grid_import_day_kwh = _f(row.get("powerFromGrid"))
                    r.grid_export_day_kwh = _f(row.get("powerToGrid"))
                    r.batt_charge_day_kwh = _f(row.get("esCharging"))
                    r.batt_discharge_day_kwh = _f(row.get("esDischarging"))
            except Exception as exc:  # noqa: BLE001 - statistics are optional
                log.debug("[%s] statistics skipped: %s", self.device_id, exc)
            r.ts = datetime.now(timezone.utc)
            out.append(r)
        return out


def _f(v: Any) -> float | None:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
