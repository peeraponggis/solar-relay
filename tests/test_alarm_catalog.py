import yaml

from solar_relay import alarm_catalog as ac
from solar_relay.schema import Alarm, Reading


def test_catalog_loads_and_every_entry_has_category_or_action():
    cat = ac.load_catalog()
    assert cat["brands"] and cat["categories"]
    for brand, table in cat["brands"].items():
        for key, e in table.items():
            assert e.get("action"), f"{brand}.{key} has no action"
            assert e.get("severity") in ac.SEVERITIES, f"{brand}.{key}"
            if e.get("category"):
                assert e["category"] in cat["categories"], f"{brand}.{key} unknown category {e['category']}"


def test_exact_lookup_huawei():
    e = ac.lookup("huawei.2032")
    assert e["name"] == "Grid loss" and e["category"] == "grid_loss" and "กริด" in e["action"]


def test_alias_lookup_solis_from_message():
    e = ac.lookup("solis.4117", "OV-G-V02 Grid over voltage")
    assert e["key"] == "OV-G-V" and e["category"] == "grid_overvoltage"


def test_alias_lookup_prefers_longest_match():
    e = ac.lookup("goodwe.errors", "GFCI Device Check Failure")
    assert e["key"] == "GFCI Device Check Failure"


def test_alias_word_boundary_does_not_match_inside_numbers():
    # sungrow "2" alias must not match inside "1234"
    e = ac.lookup("sungrow.1234", "")
    assert e["name"] == "Sungrow fault"      # brand default


def test_brand_default_then_global_default():
    assert ac.lookup("deye.F99")["name"] == "Deye fault"
    assert ac.lookup("unknownbrand.x")["name"] == "Unknown alarm"


def test_enrich_alarm_fills_message_advice_and_severity():
    a = Alarm(code="deye.F16")
    ac.enrich_alarm(a)
    assert a.message == "AC leakage current (GFCI)"
    assert a.category == "leakage" and a.severity == "fault" and a.advice


def test_enrich_reading_uses_brand_hint_when_code_has_no_prefix():
    r = Reading(device_id="x", brand="fronius", source="t", alarms=[Alarm(code="102")])
    ac.enrich_reading(r)
    assert r.alarms[0].category == "grid_overvoltage"


def test_markdown_render_and_yaml_round_trip():
    md = ac.to_markdown()
    assert "## huawei" in md and "| `2062` |" in md
    yaml.safe_load(ac.CATALOG_PATH.read_text(encoding="utf-8"))
