"""Unified alarm / error-code catalog for every brand + enrichment of Alarm objects.

Data lives in ``alarm_catalog.yaml`` (same folder).  Structure:

    categories:                      # shared repair guidance, referenced by entries
      grid_overvoltage: {name: ..., cause: ..., action: ..., severity: warning}
    brands:
      huawei:
        "2032": {name: Grid loss, category: grid_loss}                 # exact code
        "2062": {name: Low insulation resistance, category: insulation, action: ...override...}
      solis:
        "OV-G-V": {name: ..., category: ..., aliases: ["OV-G-V01", "OV-G-V02"]}
      sunspec:
        "Evt1.b0": {...}

Lookup order for an Alarm(code="huawei.2032", message="Grid loss"):
  1. brand = code prefix before the first dot, key = the rest ("2032")
  2. exact key in brands[brand]
  3. any entry whose key or alias appears (case-insensitive, word boundary) in "<key> <message>"
  4. brand-level "_default" entry, then global "_default"
The matched entry (merged over its category) fills Alarm.message (if empty), Alarm.advice,
Alarm.category and normalises Alarm.severity.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .schema import Alarm, Reading

CATALOG_PATH = Path(__file__).with_name("alarm_catalog.yaml")
SEVERITIES = ("info", "warning", "fault")


@lru_cache(maxsize=1)
def load_catalog(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else CATALOG_PATH
    with open(p, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    cats = raw.get("categories", {}) or {}
    brands: dict[str, dict[str, dict]] = {}
    for brand, entries in (raw.get("brands", {}) or {}).items():
        merged: dict[str, dict] = {}
        for key, entry in (entries or {}).items():
            entry = dict(entry or {})
            cat = cats.get(entry.get("category", ""), {})
            # category gives defaults, entry overrides
            full = {**cat, **{k: v for k, v in entry.items() if v not in (None, "")}}
            full.setdefault("name", key)
            full.setdefault("severity", "warning")
            full["key"] = str(key)
            merged[str(key)] = full
        brands[brand] = merged
    return {"categories": cats, "brands": brands, "_default": raw.get("_default", {})}


def _split(code: str) -> tuple[str, str]:
    brand, _, rest = code.partition(".")
    return (brand.lower(), rest) if rest else ("", code)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", re.IGNORECASE)


@lru_cache(maxsize=4096)
def lookup(code: str, message: str = "", brand_hint: str = "") -> dict[str, Any] | None:
    """Find the catalog entry for an alarm; returns a merged dict or None."""
    cat = load_catalog()
    brand, key = _split(code)
    brand = brand or brand_hint.lower()
    table = cat["brands"].get(brand, {})
    if key in table:
        return table[key]
    hay = f"{key} {message}"
    best: tuple[int, dict] | None = None
    for entry in table.values():
        for alias in [entry["key"], *entry.get("aliases", [])]:
            if _alias_pattern(str(alias)).search(hay):
                score = len(str(alias))
                if best is None or score > best[0]:
                    best = (score, entry)
    if best:
        return best[1]
    if "_default" in table:
        return table["_default"]
    return cat["_default"] or None


def enrich_alarm(alarm: Alarm, brand_hint: str = "") -> Alarm:
    entry = lookup(alarm.code, alarm.message or "", brand_hint)
    if not entry:
        return alarm
    if not alarm.message:
        alarm.message = str(entry.get("name", ""))
    alarm.advice = str(entry.get("action", "") or "")
    alarm.category = str(entry.get("category", "") or "")
    sev = str(entry.get("severity", alarm.severity)).lower()
    if sev in SEVERITIES:
        alarm.severity = sev
    alarm.raw.setdefault("catalog_name", entry.get("name"))
    if entry.get("cause"):
        alarm.raw.setdefault("cause", entry["cause"])
    return alarm


def enrich_reading(reading: Reading) -> Reading:
    for a in reading.alarms:
        enrich_alarm(a, reading.brand)
    return reading


# ---------------------------------------------------------------------------
def to_markdown() -> str:
    """Render the whole catalog as a Markdown reference (docs/ALARM_CODES.md)."""
    cat = load_catalog()
    out = ["# Alarm / error code reference (all brands)", "",
           "Generated from `solar_relay/alarm_catalog.yaml` by `python -m solar_relay.alarm_catalog --markdown`.", ""]
    out += ["## Categories (shared guidance)", "", "| category | name | typical cause | action |", "|---|---|---|---|"]
    for k, c in cat["categories"].items():
        out.append(f"| `{k}` | {c.get('name', '')} | {c.get('cause', '')} | {c.get('action', '')} |")
    out.append("")
    for brand, table in cat["brands"].items():
        out += [f"## {brand}", "", "| code | name | severity | category | action |", "|---|---|---|---|---|"]
        for key, e in table.items():
            aliases = ", ".join(str(a) for a in e.get("aliases", []))
            code = f"`{key}`" + (f" ({aliases})" if aliases else "")
            out.append(f"| {code} | {e.get('name', '')} | {e.get('severity', '')} | {e.get('category', '')} | {e.get('action', '')} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys
    try:  # Windows consoles default to a legacy code page; the catalog is Thai + symbols
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    p = argparse.ArgumentParser(prog="solar_relay.alarm_catalog")
    p.add_argument("--markdown", action="store_true", help="print the catalog as Markdown")
    p.add_argument("--lookup", nargs="+", metavar="CODE", help="look up alarm codes, e.g. huawei.2032 solis.OV-G-V01 deye.F16")
    p.add_argument("--message", default="", help="vendor message text to match aliases against (with --lookup)")
    a = p.parse_args(argv)
    if a.markdown:
        print(to_markdown())
        return 0
    if a.lookup:
        for code in a.lookup:
            print(json.dumps({code: lookup(code, a.message)}, ensure_ascii=False, indent=2))
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
