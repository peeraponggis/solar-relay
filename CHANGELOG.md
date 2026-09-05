# Changelog

## v0.1.0 - 2026-09-05

First release.

- **Adapters (local):** SunSpec (SolarEdge, Fronius, SMA, Delta, SolaX, GoodWe), brand Modbus maps
  (Huawei SUN2000, Solis, Sungrow, SolaX, Deye 1p/3p, Sofar, Sigenergy plant), Solarman V5 loggers
  (Deye / Sofar / Solis DLS-W/DLS-L), GoodWe UDP, Fronius Solar API, Sigenergy OpenAPI (MQTT push).
- **Adapters (cloud):** Huawei Northbound, SolisCloud v2, Solarman Smart / Deye Cloud, GoodWe SEMS,
  Growatt ShineServer, Sungrow iSolarCloud, SolarEdge Monitoring, Fronius Solar.web, SMA Sunny Portal.
- **Normalized schema** with one sign convention (grid +import / -export, battery +charge / -discharge).
- **Outputs:** InfluxDB 2.x, MQTT, Home Assistant MQTT discovery (stable entity ids), PVOutput, console.
- **Alarm catalog:** ~230 vendor codes in 27 categories with Thai repair guidance, enriched automatically.
- **Dashboards:** provisioned Grafana dashboard; generated Home Assistant Lovelace dashboard.
- **Ops:** Docker multi-arch image on GHCR (amd64 / arm64), docker-compose stack, GitHub Actions CI.
