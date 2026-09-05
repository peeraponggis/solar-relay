"""Uses the exact sample payloads published on developer.sigencloud.com (Telemetry / Alarm pages)."""
from datetime import timezone

from solar_relay.adapters.sigen_openapi import parse_alarm, parse_telemetry

TELEMETRY = {
    "deviceType": "system", "systemId": "AXBNH1123789222", "snCode": "AXBNH1123789222", "statisticsTime": 1757407020,
    "value": {
        "gridPhaseCReactivePowerVar": "-51.0", "inverterActivePowerW": "4207.0", "inverterReactivePowerVar": "-6.0",
        "inverterMaxChargePowerW": "4199.0", "inverterMaxAbsorptionActivePowerW": "5000.0",
        "inverterPhaseAActivePowerW": "4192.0", "gridActivePowerW": "-4151.0", "inverterMaxFeedInActivePowerW": "5000.0",
        "inverterMaxDischargePowerW": "2466.0", "storageChargeCapacityWh": "6090.0", "storageDischargeCapacityWh": "1960.0",
        "pvPowerW": "1740.0", "storageChargeDischargePowerW": "-2464.0", "storageSOC%": "24.4", "gridReactivePowerVar": "-51.0",
    },
}
ALARM = {"systemId": "KXGCS1727160960", "alarmCode": "1001", "status": "generation", "changeTime": 1716173149647}


def test_parse_telemetry_signs():
    r = parse_telemetry(TELEMETRY, "sigen-1")
    assert r.pv_w == 1740.0 and r.ac_w == 4207.0
    assert r.grid_w == -4151.0           # exporting (pv 1740 + battery 2464 ~ inverter 4207) -> negative in relay convention
    assert r.batt_w == -2464.0           # discharging
    assert r.soc == 24.4
    assert r.ts.tzinfo == timezone.utc and r.ts.year == 2025
    assert r.extra["inverterMaxDischargePowerW"] == 2466.0


def test_parse_alarm():
    r = parse_alarm(ALARM, "sigen-1")
    a = r.alarms[0]
    assert a.code == "sigen.1001" and a.active is True and a.raised_at.year == 2024
    assert r.extra["event"] == "alarm"
