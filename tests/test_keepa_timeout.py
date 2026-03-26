# tests/test_keepa_timeout.py
"""
keepa_client / get_keepa_prices の timeout 指定確認テスト。

テスト対象:
  - keepa_client.get_asins_from_finder
  - keepa_client.enrich_results_with_keepa_jan
  - get_keepa_prices.get_keepa_summary
"""
import os
from unittest.mock import patch, MagicMock

import pytest


def _mock_response(status_code=200, json_body=None):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_body if json_body is not None else {}
    m.raise_for_status = MagicMock()
    return m


class TestKeepaTimeout:

    def test_get_asins_from_finder_passes_timeout(self):
        """get_asins_from_finder が requests.get に timeout=(10,30) を渡すこと"""
        from keepa_client import get_asins_from_finder

        mock_resp = _mock_response(json_body={"asinList": []})
        with patch("keepa_client.requests.get", return_value=mock_resp) as mock_get, \
             patch.dict(os.environ, {"KEEPA_API_KEY": "test_key"}):
            get_asins_from_finder('{"page": 1}')

        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)

    def test_enrich_results_passes_timeout(self):
        """enrich_results_with_keepa_jan が requests.get に timeout=(10,30) を渡すこと"""
        from keepa_client import enrich_results_with_keepa_jan

        mock_resp = _mock_response(json_body={"products": []})
        with patch("keepa_client.requests.get", return_value=mock_resp) as mock_get, \
             patch("keepa_client.time.sleep"), \
             patch.dict(os.environ, {
                 "KEEPA_API_KEY": "test_key",
                 "KEEPA_REQUEST_UPPER_NUM": "10",
             }):
            enrich_results_with_keepa_jan({"B000TEST01": {}})

        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)

    def test_get_keepa_summary_passes_timeout(self):
        """get_keepa_summary が requests.get に timeout=(10,30) を渡すこと"""
        from get_keepa_prices import get_keepa_summary

        mock_resp = _mock_response(json_body={"products": []})
        with patch("get_keepa_prices.requests.get", return_value=mock_resp) as mock_get, \
             patch.dict(os.environ, {
                 "KEEPA_API_KEY": "test_key",
                 "KEEPA_DOMAIN": "5",
             }):
            get_keepa_summary(["B000TEST01"])

        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)
