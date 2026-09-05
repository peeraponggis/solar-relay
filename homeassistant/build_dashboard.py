"""Generate a Home Assistant Lovelace dashboard (YAML) for the devices in a solar-relay config.

    python homeassistant/build_dashboard.py                      # devices from config.yaml (or config.example.yaml)
    python homeassistant/build_dashboard.py --config my.yaml --out homeassistant/solar-relay-dashboard.yaml
    python homeassistant/build_dashboard.py --devices huawei-sun2000 solis-s6-hybrid

Entity ids follow solar_relay.outputs.homeassistant.entity_id():  sensor.<slug>_pv_w, binary_sensor.<slug>_alarm ...
Only core Lovelace cards are used (no HACS): tile, gauge, history-graph, statistics-graph, entities,
conditional, markdown, vertical/horizontal-stack, grid.

Import: Settings -> Dashboards -> Add dashboard -> "New dashboard from scratch" -> open it -> pencil ->
three dots -> "Raw configuration editor" -> paste the YAML.  Or add to configuration.yaml:
    lovelace:
      dashboards:
        solar-relay:
          mode: yaml
          title: Solar Relay
          icon: mdi:solar-power
          filename: solar-relay-dashboard.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solar_relay.outputs.homeassistant import entity_id, ha_slug  # noqa: E402

POWER = [("pv_w", "PV", "mdi:solar-power"), ("load_w", "Load", "mdi:home-lightning-bolt"),
         ("grid_w", "Grid", "mdi:transmission-tower"), ("batt_w", "Battery", "mdi:battery-charging")]
ENERGY = [("energy_day_kwh", "PV today"), ("load_day_kwh", "Load today"), ("grid_import_day_kwh", "Import today"),
          ("grid_export_day_kwh", "Export today"), ("batt_charge_day_kwh", "Charge today"), ("batt_discharge_day_kwh", "Discharge today")]
DETAILS = ["ac_w", "reactive_var", "grid_v", "grid_hz", "temp_c", "batt_v", "batt_a", "batt_temp_c", "soh",
           "energy_total_kwh", "pv1_v", "pv1_a", "pv1_w", "pv2_v", "pv2_a", "pv2_w", "pv3_w", "pv4_w"]


def load_device_ids(config_path: Path) -> list[str]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return [str(d["id"]) for d in raw.get("devices", []) if d.get("enabled", True)]


def tile(dev: str, field: str, name: str, icon: str | None = None, color: str | None = None) -> dict[str, Any]:
    c: dict[str, Any] = {"type": "tile", "entity": entity_id(dev, field), "name": name, "vertical": True}
    if icon:
        c["icon"] = icon
    if color:
        c["color"] = color
    return c


def alarm_markdown(devices: list[str], title: str = "Active alarms") -> dict[str, Any]:
    """Markdown card listing active alarms with the repair advice from alarm_catalog (attributes of sensor.<slug>_alarms)."""
    lines = [f"### {title}", "{% set ns = namespace(n=0) %}"]
    for d in devices:
        e = entity_id(d, "alarms")
        lines += [
            f"{{% for a in (state_attr('{e}', 'alarms') or []) if a.active %}}",
            "{% set ns.n = ns.n + 1 %}",
            f"**{d}** · `{{{{ a.code }}}}` {{{{ a.message }}}}  ",
            "{% if a.advice %}➜ {{ a.advice }}{% endif %}",
            "",
            "{% endfor %}",
        ]
    lines += ["{% if ns.n == 0 %}✅ ไม่มี alarm ค้าง{% endif %}"]
    return {"type": "markdown", "content": "\n".join(lines)}


def device_overview(dev: str) -> dict[str, Any]:
    slug = ha_slug(dev)
    return {"type": "vertical-stack", "cards": [
        {"type": "tile", "entity": entity_id(dev, "status"), "name": dev, "icon": "mdi:solar-power-variant",
         "tap_action": {"action": "navigate", "navigation_path": f"/solar-relay/{slug}"}},
        {"type": "horizontal-stack", "cards": [tile(dev, f, n, i) for f, n, i in POWER]},
        {"type": "horizontal-stack", "cards": [
            {"type": "gauge", "entity": entity_id(dev, "soc"), "name": "SOC", "min": 0, "max": 100, "needle": True,
             "severity": {"red": 0, "yellow": 20, "green": 50}},
            {"type": "entities", "entities": [
                {"entity": entity_id(dev, "energy_day_kwh"), "name": "PV today"},
                {"entity": entity_id(dev, "load_day_kwh"), "name": "Load today"},
                {"entity": entity_id(dev, "alarm", "binary_sensor"), "name": "Alarm"},
            ]},
        ]},
        {"type": "conditional", "conditions": [{"condition": "state", "entity": entity_id(dev, "alarm", "binary_sensor"), "state": "on"}],
         "card": alarm_markdown([dev], f"Alarm · {dev}")},
    ]}


def device_view(dev: str) -> dict[str, Any]:
    slug = ha_slug(dev)
    power_entities = [{"entity": entity_id(dev, f), "name": n} for f, n, _ in POWER]
    return {"title": dev, "path": slug, "icon": "mdi:solar-panel", "cards": [
        {"type": "horizontal-stack", "cards": [tile(dev, f, n, i) for f, n, i in POWER]},
        {"type": "history-graph", "title": "Power flow (W)", "hours_to_show": 24, "entities": power_entities},
        {"type": "horizontal-stack", "cards": [
            {"type": "gauge", "entity": entity_id(dev, "soc"), "name": "Battery SOC", "min": 0, "max": 100, "needle": True,
             "severity": {"red": 0, "yellow": 20, "green": 50}},
            {"type": "history-graph", "title": "SOC 24h", "hours_to_show": 24, "entities": [{"entity": entity_id(dev, "soc")}]},
        ]},
        {"type": "statistics-graph", "title": "Energy per day (kWh)", "chart_type": "bar", "period": "day", "days_to_show": 14,
         "stat_types": ["change"], "entities": [{"entity": entity_id(dev, "energy_total_kwh"), "name": "PV"}]},
        {"type": "entities", "title": "Energy today", "entities": [{"entity": entity_id(dev, f), "name": n} for f, n in ENERGY]},
        {"type": "entities", "title": "Details", "entities": [{"entity": entity_id(dev, f)} for f in DETAILS]},
        {"type": "history-graph", "title": "Grid voltage / frequency", "hours_to_show": 24,
         "entities": [{"entity": entity_id(dev, "grid_v")}, {"entity": entity_id(dev, "grid_hz")}]},
        {"type": "history-graph", "title": "Temperatures", "hours_to_show": 24,
         "entities": [{"entity": entity_id(dev, "temp_c")}, {"entity": entity_id(dev, "batt_temp_c")}]},
        {"type": "entities", "title": "Status", "entities": [
            {"entity": entity_id(dev, "status")}, {"entity": entity_id(dev, "alarms")},
            {"entity": entity_id(dev, "alarm", "binary_sensor")}]},
        alarm_markdown([dev], f"Alarms · {dev}"),
    ]}


def build(devices: list[str]) -> dict[str, Any]:
    overview_cards: list[dict[str, Any]] = [
        {"type": "markdown", "content": "## ☀️ Solar Relay\n"
         + "{% set devs = [" + ", ".join(f"'{entity_id(d, 'alarm', 'binary_sensor')}'" for d in devices) + "] %}"
         + "{% set on = devs | select('is_state', 'on') | list | length %}"
         + "{% set off = devs | select('is_state', 'unavailable') | list | length %}"
         + f"อุปกรณ์ {len(devices)} เครื่อง · ⚠️ alarm {{{{ on }}}} · 📴 offline {{{{ off }}}}"},
        {"type": "grid", "columns": 2, "square": False, "cards": [device_overview(d) for d in devices]},
    ]
    views = [
        {"title": "Overview", "path": "overview", "icon": "mdi:view-dashboard", "cards": overview_cards},
        {"title": "Alarms", "path": "alarms", "icon": "mdi:alert", "cards": [
            alarm_markdown(devices, "Active alarms (all devices)"),
            {"type": "entities", "title": "Alarm state per device",
             "entities": [{"entity": entity_id(d, "alarm", "binary_sensor"), "name": d} for d in devices]},
            {"type": "entities", "title": "Latest alarm codes",
             "entities": [{"entity": entity_id(d, "alarms"), "name": d} for d in devices]},
        ]},
        *[device_view(d) for d in devices],
    ]
    return {"title": "Solar Relay", "views": views}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=None, help="solar-relay config.yaml (default: config.yaml, else config.example.yaml)")
    p.add_argument("--devices", nargs="+", help="device ids instead of reading the config")
    p.add_argument("--out", default=str(ROOT / "homeassistant" / "solar-relay-dashboard.yaml"))
    a = p.parse_args(argv)
    if a.devices:
        devices = a.devices
    else:
        cfg = Path(a.config) if a.config else (ROOT / "config.yaml" if (ROOT / "config.yaml").exists() else ROOT / "config.example.yaml")
        devices = load_device_ids(cfg)
    dash = build(devices)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("# generated by homeassistant/build_dashboard.py - do not edit by hand\n"
                   + yaml.safe_dump(dash, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(f"wrote {out} ({len(devices)} devices, {len(dash['views'])} views)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
