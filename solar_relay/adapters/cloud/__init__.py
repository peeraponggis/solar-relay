"""Vendor cloud adapters - fallback when the site has no local Modbus / SunSpec access.

Every adapter here polls slowly (default 300 s) because the vendors rate-limit hard
(SolarEdge 300 req/day/site, Huawei getDevRealKpi 1 per 5 min, Sigen cloud 1 per endpoint per 5 min).
"""
