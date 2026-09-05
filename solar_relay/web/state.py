"""In-memory state behind the web UI: latest reading per device, active alarms, alarm history."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from ..config import RelayConfig, SiteConfig
from ..schema import Alarm, Reading

UNASSIGNED = SiteConfig(id="_unassigned", name="ไม่ระบุไซต์")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class State:
    def __init__(self, history_len: int = 2000):
        self._lock = threading.Lock()
        self.cfg: RelayConfig | None = None
        self.readings: dict[str, Reading] = {}
        self.active: dict[tuple[str, str], dict[str, Any]] = {}     # (device_id, code) -> alarm record
        self.history: deque[dict[str, Any]] = deque(maxlen=history_len)
        self.started = datetime.now(timezone.utc)

    # ---- config ---------------------------------------------------------
    def attach(self, cfg: RelayConfig) -> None:
        self.cfg = cfg

    def site_for(self, device_id: str) -> SiteConfig:
        if self.cfg:
            s = self.cfg.site_of(device_id)
            if s:
                return s
        return UNASSIGNED

    def configured_devices(self) -> list[str]:
        if self.cfg:
            return [d.id for d in self.cfg.devices if d.enabled]
        return sorted(self.readings)

    # ---- updates --------------------------------------------------------
    def update(self, reading: Reading) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            is_event = reading.extra.get("event") == "alarm"
            prev = self.readings.get(reading.device_id)
            if is_event and prev is not None:
                # Sigen-style push: keep the last telemetry, only apply the alarm event
                for a in reading.alarms:
                    self._apply_alarm(reading.device_id, a, now)
                return
            self.readings[reading.device_id] = reading
            seen: set[str] = set()
            for a in reading.alarms:
                seen.add(a.code)
                self._apply_alarm(reading.device_id, a, now)
            if not is_event:
                # poll adapters send the complete alarm set -> anything missing has recovered
                for key in [k for k in self.active if k[0] == reading.device_id and k[1] not in seen]:
                    self._recover(key, now)

    def _apply_alarm(self, device_id: str, a: Alarm, now: datetime) -> None:
        key = (device_id, a.code)
        if a.active:
            rec = self.active.get(key)
            if rec is None:
                rec = {"device_id": device_id, **asdict(a), "raised_at": _iso(a.raised_at or now), "first_seen": _iso(now),
                       "last_seen": _iso(now), "acked": False, "ack_note": ""}
                self.active[key] = rec
                self.history.appendleft({**rec, "event": "raised", "at": _iso(now)})
            else:
                rec["last_seen"] = _iso(now)
                if a.message and not rec.get("message"):
                    rec["message"] = a.message
                if a.advice and not rec.get("advice"):
                    rec["advice"], rec["category"] = a.advice, a.category
        else:
            self._recover(key, now, a)

    def _recover(self, key: tuple[str, str], now: datetime, a: Alarm | None = None) -> None:
        rec = self.active.pop(key, None)
        if rec is not None:
            self.history.appendleft({**rec, "event": "recovered", "at": _iso(now)})
        elif a is not None:
            self.history.appendleft({"device_id": key[0], **asdict(a), "raised_at": _iso(a.raised_at), "event": "recovered", "at": _iso(now)})

    def ack(self, device_id: str, code: str, note: str = "", by: str = "") -> bool:
        with self._lock:
            rec = self.active.get((device_id, code))
            if rec is None:
                return False
            rec["acked"] = True
            rec["ack_note"] = note
            rec["acked_by"] = by
            rec["acked_at"] = _iso(datetime.now(timezone.utc))
            self.history.appendleft({**rec, "event": "acked", "at": rec["acked_at"]})
            return True

    # ---- views ----------------------------------------------------------
    def device_view(self, device_id: str) -> dict[str, Any]:
        r = self.readings.get(device_id)
        site = self.site_for(device_id)
        alarms = [v for k, v in self.active.items() if k[0] == device_id]
        cfg_dev = next((d for d in (self.cfg.devices if self.cfg else []) if d.id == device_id), None)
        base: dict[str, Any] = {
            "device_id": device_id, "site_id": site.id, "site_name": site.name,
            "adapter": cfg_dev.adapter if cfg_dev else None, "brand": cfg_dev.brand if cfg_dev else None,
            "online": bool(r.online) if r else False, "has_data": r is not None,
            "alarm_count": len(alarms), "alarms": alarms, "age_s": None,
        }
        if r:
            d = r.to_dict()
            d.pop("alarms", None)
            base.update(d)
            base["age_s"] = round((datetime.now(timezone.utc) - r.ts).total_seconds())
        return base

    def site_views(self) -> list[dict[str, Any]]:
        sites = list(self.cfg.sites) if self.cfg else []
        assigned = {d for s in sites for d in s.devices}
        loose = [d for d in self.configured_devices() if d not in assigned] + [d for d in self.readings if d not in assigned and d not in self.configured_devices()]
        if loose:
            sites.append(SiteConfig(id=UNASSIGNED.id, name=UNASSIGNED.name, devices=sorted(set(loose))))
        out = []
        for s in sites:
            devs = [self.device_view(d) for d in s.devices]
            agg = {k: sum((dv.get(k) or 0) for dv in devs if dv.get(k) is not None) for k in ("pv_w", "load_w", "grid_w", "batt_w", "energy_day_kwh")}
            socs = [dv["soc"] for dv in devs if dv.get("soc") is not None]
            out.append({
                "id": s.id, "name": s.name, "customer": s.customer, "phone": s.phone, "address": s.address, "note": s.note,
                "device_count": len(devs), "online": sum(1 for dv in devs if dv["online"]),
                "offline": sum(1 for dv in devs if not dv["online"]),
                "alarms": sum(dv["alarm_count"] for dv in devs),
                "faults": sum(1 for dv in devs for a in dv["alarms"] if a.get("severity") == "fault"),
                "soc_avg": round(sum(socs) / len(socs), 1) if socs else None,
                **{k: round(v, 1) for k, v in agg.items()},
                "devices": devs,
            })
        return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            sites = self.site_views()
            active = sorted(self.active.values(), key=lambda a: ({"fault": 0, "warning": 1, "info": 2}.get(a.get("severity"), 3), a.get("first_seen") or ""))
            return {
                "now": _iso(datetime.now(timezone.utc)), "started": _iso(self.started),
                "sites": sites,
                "totals": {
                    "sites": len(sites), "devices": sum(s["device_count"] for s in sites),
                    "online": sum(s["online"] for s in sites), "offline": sum(s["offline"] for s in sites),
                    "alarms": len(active), "faults": sum(1 for a in active if a.get("severity") == "fault"),
                    "unacked": sum(1 for a in active if not a.get("acked")),
                    **{k: round(sum(s[k] for s in sites), 1) for k in ("pv_w", "load_w", "grid_w", "batt_w", "energy_day_kwh")},
                },
                "active_alarms": [self._with_site(a) for a in active],
                "history": [self._with_site(h) for h in list(self.history)[:300]],
            }

    def _with_site(self, rec: dict[str, Any]) -> dict[str, Any]:
        s = self.site_for(rec["device_id"])
        return {**rec, "site_id": s.id, "site_name": s.name, "customer": s.customer, "phone": s.phone}
