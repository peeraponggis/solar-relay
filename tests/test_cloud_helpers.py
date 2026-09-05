import base64
import hashlib
import hmac

from solar_relay.adapters.cloud.base import kw_to_w, to_kwh
from solar_relay.adapters.cloud.goodwe_sems import _kw_str
from solar_relay.adapters.cloud.soliscloud import solis_sign


def test_solis_sign_matches_spec():
    body = '{"pageNo":1,"pageSize":10}'
    date = "Fri, 05 Sep 2026 10:00:00 GMT"
    h = solis_sign("KEY", "SECRET", "/v1/api/inverterList", body, date)
    md5 = base64.b64encode(hashlib.md5(body.encode()).digest()).decode()
    expect = base64.b64encode(hmac.new(b"SECRET", f"POST\n{md5}\napplication/json\n{date}\n/v1/api/inverterList".encode(),
                                       hashlib.sha1).digest()).decode()
    assert h["Content-MD5"] == md5
    assert h["Authorization"] == f"API KEY:{expect}"
    assert h["Date"] == date


def test_unit_helpers():
    assert kw_to_w("1.5", "kW") == 1500 and kw_to_w(20, "W") == 20 and kw_to_w(None) is None
    assert to_kwh(2500, "Wh") == 2.5 and to_kwh("3", "MWh") == 3000
    assert _kw_str("1.23(kW)") == 1230 and _kw_str("55%") == 55 and _kw_str("-0.4(kW)") == -400
