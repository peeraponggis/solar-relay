"""YAML configuration with ``${ENV_VAR}`` / ``${ENV_VAR:default}`` substitution.

Config shape (see config.example.yaml):

    relay:
      poll_interval_s: 30
    devices:
      - id: huawei-roof
        adapter: modbus            # adapter registry key
        brand: huawei
        interval_s: 20             # optional per-device override
        options: {...}             # adapter specific
    outputs:
      - type: influxdb
        options: {...}
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            name, default = m.group(1), m.group(2)
            if name in os.environ:
                return os.environ[name]
            if default is not None:
                return default
            raise KeyError(f"environment variable {name} is not set and has no default")
        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    return value


@dataclass
class DeviceConfig:
    id: str
    adapter: str
    brand: str = ""
    interval_s: int | None = None
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputConfig:
    type: str
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class SiteConfig:
    """Customer / site grouping used by the built-in web UI."""

    id: str
    name: str = ""
    customer: str = ""
    phone: str = ""
    address: str = ""
    note: str = ""
    devices: list[str] = field(default_factory=list)


@dataclass
class RelayConfig:
    poll_interval_s: int = 30
    log_level: str = "INFO"
    devices: list[DeviceConfig] = field(default_factory=list)
    outputs: list[OutputConfig] = field(default_factory=list)
    sites: list[SiteConfig] = field(default_factory=list)
    path: str | None = None            # config.yaml location (set by load); sites edited in the UI go to sites.yaml next to it

    def site_of(self, device_id: str) -> SiteConfig | None:
        for s in self.sites:
            if device_id in s.devices:
                return s
        return None

    # ---- sites persisted from the web UI ------------------------------------
    @property
    def sites_file(self) -> Path | None:
        return Path(self.path).with_name("sites.yaml") if self.path else None

    def apply_sites_override(self) -> None:
        """sites.yaml (written by the web UI) replaces the `sites:` block of config.yaml when present."""
        f = self.sites_file
        if f and f.exists():
            raw = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            self.sites = [SiteConfig(**{k: v for k, v in s.items() if k in SiteConfig.__dataclass_fields__}) for s in raw.get("sites", []) or []]

    def save_sites(self) -> Path:
        f = self.sites_file
        if f is None:
            raise RuntimeError("config has no path; cannot persist sites")
        data = {"sites": [{"id": s.id, "name": s.name, "customer": s.customer, "phone": s.phone, "address": s.address,
                           "note": s.note, "devices": list(s.devices)} for s in self.sites]}
        f.write_text("# แก้ไขจาก Web UI (หน้า ไซต์/ลูกค้า) - ไฟล์นี้แทนที่ sites: ใน config.yaml\n"
                     + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return f

    def upsert_site(self, data: dict[str, Any]) -> SiteConfig:
        sid = str(data.get("id") or "").strip()
        if not sid:
            raise ValueError("site id required")
        site = next((s for s in self.sites if s.id == sid), None)
        if site is None:
            site = SiteConfig(id=sid)
            self.sites.append(site)
        for k in ("name", "customer", "phone", "address", "note"):
            if k in data and data[k] is not None:
                setattr(site, k, str(data[k]))
        if "devices" in data and data["devices"] is not None:
            wanted = [str(d) for d in data["devices"]]
            for other in self.sites:               # a device belongs to one site only
                if other is not site:
                    other.devices = [d for d in other.devices if d not in wanted]
            site.devices = wanted
        if not site.name:
            site.name = sid
        return site

    def delete_site(self, sid: str) -> bool:
        before = len(self.sites)
        self.sites = [s for s in self.sites if s.id != sid]
        return len(self.sites) < before

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RelayConfig:
        raw = expand_env(raw or {})
        relay = raw.get("relay", {}) or {}
        devices = [
            DeviceConfig(
                id=str(d["id"]),
                adapter=str(d["adapter"]),
                brand=str(d.get("brand", "")),
                interval_s=d.get("interval_s"),
                enabled=bool(d.get("enabled", True)),
                options=dict(d.get("options", {}) or {}),
            )
            for d in raw.get("devices", []) or []
        ]
        outputs = [
            OutputConfig(
                type=str(o["type"]),
                enabled=bool(o.get("enabled", True)),
                options=dict(o.get("options", {}) or {}),
            )
            for o in raw.get("outputs", []) or []
        ]
        ids = [d.id for d in devices]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate device ids in config: {sorted(dupes)}")
        sites = [
            SiteConfig(
                id=str(s["id"]),
                name=str(s.get("name", s["id"])),
                customer=str(s.get("customer", "")),
                phone=str(s.get("phone", "")),
                address=str(s.get("address", "")),
                note=str(s.get("note", "")),
                devices=[str(x) for x in (s.get("devices", []) or [])],
            )
            for s in raw.get("sites", []) or []
        ]
        # devices may also point at their site with `site: <id>`
        for d in raw.get("devices", []) or []:
            sid = d.get("site")
            if sid:
                site = next((s for s in sites if s.id == str(sid)), None)
                if site is None:
                    site = SiteConfig(id=str(sid), name=str(sid))
                    sites.append(site)
                if str(d["id"]) not in site.devices:
                    site.devices.append(str(d["id"]))
        return cls(
            poll_interval_s=int(relay.get("poll_interval_s", 30)),
            log_level=str(relay.get("log_level", "INFO")),
            devices=devices,
            outputs=outputs,
            sites=sites,
        )

    @classmethod
    def load(cls, path: str | Path) -> RelayConfig:
        with open(path, encoding="utf-8") as fh:
            cfg = cls.from_dict(yaml.safe_load(fh) or {})
        cfg.path = str(Path(path).resolve())
        cfg.apply_sites_override()
        return cfg
