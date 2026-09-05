from solar_relay.schema import Alarm, Reading, clamp_soc


def test_derive_load_from_balance():
    r = Reading(device_id="x", brand="b", source="s", pv_w=3000, grid_w=-1000, batt_w=500)
    r.derive_missing()
    # load = pv + grid_import - batt_charge = 3000 - 1000 - 500
    assert r.load_w == 1500


def test_derive_grid_from_balance():
    r = Reading(device_id="x", brand="b", source="s", pv_w=1000, load_w=2500, batt_w=-500)
    r.derive_missing()
    # grid = load - pv + batt = 2500 - 1000 - 500 -> importing 1000 W
    assert r.grid_w == 1000


def test_numeric_fields_and_strings():
    r = Reading(device_id="x", brand="b", source="s", pv_w=10, soc=None, strings={"pv1": {"v": 300.0, "a": 2.0, "w": None}})
    f = r.numeric_fields()
    assert f == {"pv_w": 10.0, "pv1_v": 300.0, "pv1_a": 2.0}


def test_to_dict_serializes_dates():
    r = Reading(device_id="x", brand="b", source="s", alarms=[Alarm(code="c", raised_at=None)])
    d = r.to_dict()
    assert isinstance(d["ts"], str) and d["alarms"][0]["code"] == "c"


def test_clamp_soc():
    assert clamp_soc(120) == 100 and clamp_soc(-3) == 0 and clamp_soc(None) is None
