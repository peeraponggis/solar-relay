from solar_relay.adapters.modbus_maps import (
    HUAWEI,
    MAPS,
    SOLIS,
    Reg,
    bit_alarms,
    decode,
    decode_block,
    finalize_deye,
    finalize_huawei,
    finalize_solis,
    finalize_sungrow,
    plan_blocks,
)
from solar_relay.schema import Reading


def test_decode_types():
    assert decode([0xFFFF], Reg("a", 0, "i16")) == -1
    assert decode([0x0001, 0x0000], Reg("a", 0, "u32")) == 65536
    assert decode([0x0000, 0x0001], Reg("a", 0, "u32", wordorder="little")) == 65536
    assert decode([0xFFFF, 0xFFFE], Reg("a", 0, "i32")) == -2
    assert decode([1234], Reg("a", 0, "u16", 0.1)) == 123.4
    assert decode([0x5355, 0x4E32, 0x3030, 0x3000], Reg("a", 0, "str4")) == "SUN2000"


def test_plan_blocks_groups_contiguous_and_splits_gaps():
    blocks = plan_blocks(HUAWEI, max_block=100)
    starts = [(fc, start) for fc, start, _, _ in blocks]
    assert (3, 30000) in starts and (3, 32000) in starts and (3, 37000) in starts
    for _, _, count, _ in blocks:
        assert 0 < count <= 100


def test_all_maps_plan_and_decode_zero():
    for key, (regs, finalize, defaults) in MAPS.items():
        blocks = plan_blocks(regs)
        values = {}
        for fc, start, count, rs in blocks:
            values.update(decode_block([0] * count, start, rs))
        r = finalize(values, Reading(device_id=key, brand=key, source="test"))
        assert r.device_id == key, key
        assert defaults["unit"] > 0


def _words_for(regs, assignments: dict[str, int], fill=0):
    """Build a fake register space and return per-block word lists as the client would."""
    space = {}
    by_name = {r.name: r for r in regs}
    for name, raw in assignments.items():
        r = by_name[name]
        if r.count == 1:
            space[r.addr] = raw & 0xFFFF
        else:
            hi, lo = (raw >> 16) & 0xFFFF, raw & 0xFFFF
            words = [hi, lo] if r.wordorder == "big" else [lo, hi]
            for i, w in enumerate(words):
                space[r.addr + i] = w
    values = {}
    for fc, start, count, rs in plan_blocks(regs):
        values.update(decode_block([space.get(start + i, fill) for i in range(count)], start, rs))
    return values


def test_huawei_finalize_signs_and_alarms():
    v = _words_for(HUAWEI, {
        "input_power_w": 5000, "active_power_w": 4800, "device_status": 0x0200,
        "meter_status": 1, "meter_active_power_w": (-1500) & 0xFFFFFFFF,     # Huawei: -1500 = importing
        "ess_running_status": 2, "ess_charge_discharge_w": 1200, "ess_soc": 555,
        "alarm1": 0b1000_0000, "energy_day_kwh": 1234,
    })
    r = finalize_huawei(v, Reading(device_id="h", brand="huawei", source="t"))
    assert r.pv_w == 5000 and r.ac_w == 4800
    assert r.grid_w == 1500          # relay: + import
    assert r.batt_w == 1200 and r.soc == 55.5
    assert r.status == "On-grid"
    assert r.energy_day_kwh == 12.34
    assert [a.message for a in r.alarms] == ["Grid loss"]


def test_solis_battery_direction_and_faults():
    v = _words_for(SOLIS, {"batt_w": 2000, "batt_dir": 1, "status": 3, "fault1": 0b11, "meter_w": (-700) & 0xFFFFFFFF,
                           "energy_day_kwh": 87})
    r = finalize_solis(v, Reading(device_id="s", brand="solis", source="t"))
    assert r.batt_w == -2000         # discharging
    assert r.grid_w == -700          # exporting
    assert r.status == "Generating"
    assert r.energy_day_kwh == 8.7
    assert {a.message for a in r.alarms} == {"No grid", "Grid overvoltage"}


def test_sungrow_running_state_bits():
    regs, _, _ = MAPS["sungrow"]
    v = _words_for(regs, {"running_state": 0b100, "batt_w_abs": 900, "export_w": 300, "status": 0x5500})
    r = finalize_sungrow(v, Reading(device_id="g", brand="sungrow", source="t"))
    assert r.batt_w == -900 and r.grid_w == -300
    assert r.alarms and r.alarms[0].severity == "fault"


def test_deye_offsets_and_sign():
    regs, _, _ = MAPS["deye_3p"]
    v = _words_for(regs, {"batt_w": (-800) & 0xFFFF, "batt_temp_c": 1250, "temp_c": 1400, "status": 2})
    r = finalize_deye(v, Reading(device_id="d", brand="deye", source="t"))
    assert r.batt_w == 800            # Deye -800 = charging -> relay +800
    assert r.batt_temp_c == 25.0 and r.temp_c == 40.0
    assert r.status == "Normal"


def test_bit_alarms():
    a = bit_alarms(0b101, "x", {0: "zero", 2: "two"})
    assert [(x.code, x.message) for x in a] == [("x.b0", "zero"), ("x.b2", "two")]
    assert bit_alarms(None, "x") == [] and bit_alarms("str", "x") == []
