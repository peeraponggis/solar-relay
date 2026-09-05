"""Generate grafana/provisioning/dashboards/solar-relay-overview.json.

Run:  python grafana/build_dashboard.py
The JSON is provisioned automatically by docker-compose (grafana/provisioning/dashboards/dashboards.yaml).
Queries are Flux against the InfluxDB measurements written by solar_relay.outputs.influxdb:
  inverter  (tags device_id, brand, source; fields pv_w, load_w, grid_w, batt_w, soc, energy_day_kwh, online, alarm_count, status ...)
  alarm     (tags device_id, brand, code; fields active, message, severity)
"""
from __future__ import annotations

import json
from pathlib import Path

DS = {"type": "influxdb", "uid": "influx-solar"}
OUT = Path(__file__).parent / "provisioning" / "dashboards" / "solar-relay-overview.json"

FILTER = '  |> filter(fn: (r) => r.device_id =~ /^${device:regex}$/ and r.brand =~ /^${brand:regex}$/)'


def series(field: str, label: str | None = None, agg: str = "mean") -> str:
    q = f'''from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "inverter" and r._field == "{field}")
{FILTER}
  |> aggregateWindow(every: v.windowPeriod, fn: {agg}, createEmpty: false)'''
    if label:
        q += f'\n  |> map(fn: (r) => ({{r with device_id: r.device_id + " {label}"}}))'
    return q + '\n  |> keep(columns: ["_time", "_value", "device_id"])'


def multi_field(regex_or_expr: str) -> str:
    return f'''from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "inverter" and ({regex_or_expr}))
{FILTER}
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({{r with series: r.device_id + " " + r._field}}))
  |> keep(columns: ["_time", "_value", "series"])'''


def now(field: str, fn: str = "sum", pre: str = "") -> str:
    return f'''from(bucket: v.defaultBucket)
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "inverter" and r._field == "{field}")
{FILTER}
  |> last(){pre}
  |> group()
  |> {fn}()'''


LAST_TABLE = f'''from(bucket: v.defaultBucket)
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "inverter")
  |> filter(fn: (r) => contains(value: r._field, set: ["pv_w", "ac_w", "load_w", "grid_w", "batt_w", "soc", "energy_day_kwh", "temp_c", "online", "alarm_count", "status"]))
{FILTER}
  |> last()
  |> pivot(rowKey: ["device_id", "brand", "source"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["device_id"])'''

ALARM_TABLE = f'''from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "alarm")
{FILTER}
  |> pivot(rowKey: ["_time", "device_id", "brand", "code"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 200)'''

ENERGY_DAY = f'''from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "inverter" and r._field == "energy_day_kwh")
{FILTER}
  |> aggregateWindow(every: 1d, fn: max, createEmpty: false, timeSrc: "_start")
  |> keep(columns: ["_time", "_value", "device_id"])'''

ANNOTATIONS = '''from(bucket: v.defaultBucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "alarm" and r._field == "active" and r._value == 1)
  |> map(fn: (r) => ({_time: r._time, _value: r._value, text: r.device_id + ": " + r.code, tags: r.brand}))
  |> keep(columns: ["_time", "_value", "text", "tags"])'''

VAR = '''import "influxdata/influxdb/schema"
schema.tagValues(bucket: v.defaultBucket, tag: "{tag}", predicate: (r) => r._measurement == "inverter", start: -30d)'''

_id = 0


def target(q: str, ref: str = "A") -> dict:
    return {"datasource": DS, "query": q, "refId": ref}


def panel(title, ptype, gp, targets, unit=None, defaults=None, options=None, overrides=None, desc=None) -> dict:
    global _id
    _id += 1
    fc = {"defaults": {"color": {"mode": "palette-classic"}, "custom": {}}, "overrides": overrides or []}
    if unit:
        fc["defaults"]["unit"] = unit
    if defaults:
        fc["defaults"].update(defaults)
    p = {"id": _id, "title": title, "type": ptype, "datasource": DS,
         "gridPos": {"x": gp[0], "y": gp[1], "w": gp[2], "h": gp[3]},
         "targets": targets, "fieldConfig": fc, "options": options or {}}
    if desc:
        p["description"] = desc
    return p


def stat(title, gp, q, unit, steps, desc=None) -> dict:
    return panel(title, "stat", gp, [target(q)], unit, {"thresholds": {"mode": "absolute", "steps": steps}},
                 {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                  "colorMode": "value", "graphMode": "area", "textMode": "value"}, desc=desc)


def ts(title, gp, targets, unit=None, desc=None, overrides=None) -> dict:
    return panel(title, "timeseries", gp, targets, unit,
                 {"custom": {"lineWidth": 2, "fillOpacity": 12, "showPoints": "never", "spanNulls": True},
                  "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}},
                 {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "mean", "max"]},
                  "tooltip": {"mode": "multi", "sort": "desc"}}, overrides, desc)


def color(regex: str, c: str) -> dict:
    return {"matcher": {"id": "byRegexp", "options": regex}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}


def bg_threshold(name: str, steps: list, mappings: dict | None = None) -> dict:
    props = [{"id": "custom.cellOptions", "value": {"type": "color-background"}},
             {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}}]
    if mappings:
        props.append({"id": "mappings", "value": [{"type": "value", "options": {k: {"text": v} for k, v in mappings.items()}}]})
    return {"matcher": {"id": "byName", "options": name}, "properties": props}


GREEN = [{"color": "green", "value": None}]
GRID = [{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 3000}]
SOC = [{"color": "red", "value": None}, {"color": "orange", "value": 20}, {"color": "green", "value": 50}]
RED1 = [{"color": "green", "value": None}, {"color": "red", "value": 1}]


def build() -> dict:
    panels = [
        # ---- KPI tiles
        stat("PV now", (0, 0, 4, 4), now("pv_w"), "watt", GREEN, "รวมกำลัง DC จากแผงของอุปกรณ์ที่เลือก"),
        stat("Load now", (4, 0, 4, 4), now("load_w"), "watt", GREEN, "โหลดรวม"),
        stat("Grid now (+import / -export)", (8, 0, 4, 4), now("grid_w"), "watt", GRID, "บวก = ซื้อไฟจาก grid, ลบ = ขายไฟ"),
        stat("Battery now (+charge / -discharge)", (12, 0, 4, 4), now("batt_w"), "watt", GREEN, "บวก = ชาร์จ, ลบ = คายประจุ"),
        stat("SOC (avg)", (16, 0, 4, 4), now("soc", "mean"), "percent", SOC),
        stat("Energy today", (20, 0, 4, 4), now("energy_day_kwh"), "kwatth", GREEN),
        # ---- health
        stat("Active alarms", (0, 4, 4, 3), now("alarm_count"), "none", RED1, "จำนวน alarm ที่ยัง active รวมทุกอุปกรณ์ที่เลือก"),
        stat("Devices offline", (4, 4, 4, 3), now("online", "sum", "\n  |> map(fn: (r) => ({r with _value: 1 - r._value}))"), "none", RED1),
        panel("Device status (last)", "table", (8, 4, 16, 8), [target(LAST_TABLE)], None,
              {"custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
              {"showHeader": True, "sortBy": [{"displayName": "device_id"}]},
              overrides=[
                  bg_threshold("online", [{"color": "red", "value": None}, {"color": "green", "value": 1}], {"0": "OFFLINE", "1": "online"}),
                  bg_threshold("alarm_count", RED1),
                  {"matcher": {"id": "byName", "options": "soc"}, "properties": [{"id": "unit", "value": "percent"}]},
                  {"matcher": {"id": "byRegexp", "options": ".*_w$"}, "properties": [{"id": "unit", "value": "watt"}, {"id": "decimals", "value": 0}]},
                  {"matcher": {"id": "byName", "options": "energy_day_kwh"}, "properties": [{"id": "unit", "value": "kwatth"}]},
                  {"matcher": {"id": "byName", "options": "temp_c"}, "properties": [{"id": "unit", "value": "celsius"}]},
              ], desc="ค่าล่าสุดต่ออุปกรณ์ (ภายใน 1 ชั่วโมง)"),
        # ---- power flow
        ts("Power flow", (0, 12, 24, 9),
           [target(series("pv_w", "pv"), "A"), target(series("load_w", "load"), "B"),
            target(series("grid_w", "grid"), "C"), target(series("batt_w", "batt"), "D")],
           "watt", "pv / load / grid (+import) / batt (+charge) ต่ออุปกรณ์",
           overrides=[color(".* pv$", "yellow"), color(".* load$", "blue"), color(".* grid$", "red"), color(".* batt$", "green")]),
        # ---- battery + energy
        ts("Battery SOC", (0, 21, 12, 8), [target(series("soc"))], "percent",
           overrides=[{"matcher": {"id": "byRegexp", "options": ".*"}, "properties": [{"id": "min", "value": 0}, {"id": "max", "value": 100}]}]),
        panel("Energy per day", "barchart", (12, 21, 12, 8), [target(ENERGY_DAY)], "kwatth",
              {"custom": {"fillOpacity": 80, "lineWidth": 1}},
              {"orientation": "vertical", "xField": "_time", "showValue": "auto",
               "legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
              desc="energy_day_kwh สูงสุดของแต่ละวัน"),
        # ---- alarms
        panel("Alarm log", "table", (0, 29, 24, 9), [target(ALARM_TABLE)], None,
              {"custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
              {"showHeader": True, "sortBy": [{"displayName": "time", "desc": True}]},
              overrides=[bg_threshold("active", RED1, {"0": "recovered", "1": "ACTIVE"}),
                         {"matcher": {"id": "byName", "options": "_time"}, "properties": [{"id": "displayName", "value": "time"}]}],
              desc="alarm จาก measurement alarm: code, message, severity, active (1 = ยังค้าง)"),
        # ---- diagnostics
        ts("PV strings power", (0, 38, 12, 8), [target(multi_field('r._field =~ /^pv[0-9]+_w$/'))], "watt",
           "pv1..pvN ต่ออุปกรณ์ ใช้หา string ที่ผลิตต่ำผิดปกติ"),
        ts("Temperatures", (12, 38, 12, 8), [target(multi_field('r._field == "temp_c" or r._field == "batt_temp_c"'))], "celsius",
           "inverter temp_c และ batt_temp_c"),
        ts("Grid voltage / frequency", (0, 46, 24, 7), [target(multi_field('r._field == "grid_v" or r._field == "grid_hz"'))], None,
           "ใช้ตรวจ over/under voltage ที่ทำให้ inverter ตัด",
           overrides=[{"matcher": {"id": "byRegexp", "options": ".* grid_hz$"},
                       "properties": [{"id": "unit", "value": "hertz"}, {"id": "custom.axisPlacement", "value": "right"}]},
                      {"matcher": {"id": "byRegexp", "options": ".* grid_v$"}, "properties": [{"id": "unit", "value": "volt"}]}]),
    ]
    return {
        "uid": "solar-relay-overview",
        "title": "Solar Relay - Overview",
        "tags": ["solar", "inverter", "solar-relay"],
        "timezone": "browser",
        "editable": True,
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "time": {"from": "now-24h", "to": "now"},
        "templating": {"list": [
            {"name": "device", "label": "Device", "type": "query", "datasource": DS, "query": VAR.format(tag="device_id"),
             "includeAll": True, "multi": True, "current": {"text": "All", "value": "$__all"}, "refresh": 2, "sort": 1},
            {"name": "brand", "label": "Brand", "type": "query", "datasource": DS, "query": VAR.format(tag="brand"),
             "includeAll": True, "multi": True, "current": {"text": "All", "value": "$__all"}, "refresh": 2, "sort": 1},
        ]},
        "annotations": {"list": [{
            "name": "Alarms", "datasource": DS, "enable": True, "iconColor": "red",
            "target": {"query": ANNOTATIONS},
            "mappings": {"text": {"source": "field", "value": "text"}, "tags": {"source": "field", "value": "tags"}},
        }]},
        "panels": panels,
    }


if __name__ == "__main__":
    dash = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dash, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({len(dash['panels'])} panels)")
