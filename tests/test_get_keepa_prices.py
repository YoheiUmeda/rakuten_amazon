# tests/test_get_keepa_prices.py
"""get_keepa_prices: KEEPA_DOMAIN デフォルト値のテスト"""
import os
import sys
import unittest.mock as mock


def _reload_module():
    """get_keepa_prices を再ロードして module-level の load_dotenv を回避する。"""
    mod_name = "get_keepa_prices"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    with mock.patch("dotenv.load_dotenv"):
        import get_keepa_prices as m
    return m


def test_default_domain_is_5(monkeypatch):
    """KEEPA_DOMAIN 未設定のとき domain=5 (amazon.co.jp) が使われる。"""
    monkeypatch.delenv("KEEPA_DOMAIN", raising=False)
    m = _reload_module()

    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["domain"] = params.get("domain")
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {"products": []}
        return r

    with mock.patch("requests.get", side_effect=fake_get):
        with mock.patch.dict(os.environ, {"KEEPA_API_KEY": "dummy"}):
            m.get_keepa_summary(["B00TEST1234"])

    assert captured.get("domain") == 5


def test_explicit_domain_overrides_default(monkeypatch):
    """KEEPA_DOMAIN=6 と明示されたとき domain=6 が使われる（上書き不可）。"""
    monkeypatch.setenv("KEEPA_DOMAIN", "6")
    m = _reload_module()

    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["domain"] = params.get("domain")
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {"products": []}
        return r

    with mock.patch("requests.get", side_effect=fake_get):
        with mock.patch.dict(os.environ, {"KEEPA_API_KEY": "dummy", "KEEPA_DOMAIN": "6"}):
            m.get_keepa_summary(["B00TEST1234"])

    assert captured.get("domain") == 6
