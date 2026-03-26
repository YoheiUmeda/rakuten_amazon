# tests/test_rakuten_retry.py
"""
楽天API 429 ループリトライのテスト。

テスト対象:
  - rakuten_client.perform_rakuten_api_search
  - rakuten_client.perform_rakuten_api_search_from_itemcode

モック方針:
  - requests.get を unittest.mock.patch で差し替え
  - time.sleep を patch してテストを即時完了させ、呼び出し引数でバックオフ秒数を確認
"""
import os
from unittest.mock import patch, MagicMock, call

import pytest

import requests as _requests

from rakuten_client import (
    perform_rakuten_api_search,
    perform_rakuten_api_search_from_itemcode,
    search_rakuten_product_api,
    search_ichiba_from_product,
)

APP_ID = "test_app_id"


# ─────────────────────────────────────────────
#  レスポンスビルダー
# ─────────────────────────────────────────────

def _mock_response(status_code=200, json_body=None, text=None):
    """requests.Response 相当のモックを返す"""
    m = MagicMock()
    m.status_code = status_code
    body = json_body if json_body is not None else {}
    m.json.return_value = body
    m.text = text if text is not None else str(body)
    return m


def _429_response():
    return _mock_response(status_code=429, text="error too_many_requests")


def _200_ok(items=None):
    items = items or [{"Item": {"itemName": "テスト商品", "itemPrice": 1000}}]
    return _mock_response(
        status_code=200,
        json_body={"Items": items},
        text="ok",
    )


def _200_json_rate_limit():
    """HTTPは200だがJSONにtoo_many_requestsエラーが入っているケース"""
    return _mock_response(
        status_code=200,
        json_body={"error": "too_many_requests", "error_description": "rate limited"},
        text='{"error": "too_many_requests"}',
    )


def _500_response():
    return _mock_response(status_code=500, text="Internal Server Error")


# ─────────────────────────────────────────────
#  perform_rakuten_api_search のテスト
# ─────────────────────────────────────────────

class TestPerformRakutenApiSearch:

    # ── 毎回429（全試行）──────────────────────

    def test_all_429_returns_empty(self):
        """全試行で429のとき [] を返すこと"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search("テスト", APP_ID)

        assert result == []

    def test_all_429_no_sleep_on_last_attempt(self):
        """最終試行で429のとき sleep しないこと（不要な待機の排除）"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            perform_rakuten_api_search("テスト", APP_ID)

        # attempt=0 → sleep(10), attempt=1 → sleep(20), attempt=2(最終) → sleep なし
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(10)
        mock_sleep.assert_any_call(20)

    def test_all_429_backoff_seconds(self):
        """バックオフが 10s, 20s の順で呼ばれること"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            perform_rakuten_api_search("テスト", APP_ID)

        assert mock_sleep.call_args_list == [call(10), call(20)]

    # ── 1回目429 → 2回目成功 ─────────────────

    def test_retry_succeeds_on_second_attempt(self):
        """1回目429・2回目成功のとき正常なアイテムリストを返すこと"""
        responses = [_429_response(), _200_ok()]
        with patch("rakuten_client.requests.get", side_effect=responses), \
             patch("rakuten_client.time.sleep"), \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search("テスト", APP_ID)

        assert len(result) == 1
        assert result[0]["itemName"] == "テスト商品"

    def test_retry_sleeps_only_before_successful_attempt(self):
        """1回目429→2回目成功のとき sleep は1回だけ呼ばれること"""
        responses = [_429_response(), _200_ok()]
        with patch("rakuten_client.requests.get", side_effect=responses), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            perform_rakuten_api_search("テスト", APP_ID)

        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_once_with(10)

    # ── 500系エラー ───────────────────────────

    def test_500_returns_empty_without_retry(self):
        """500エラーのときリトライせず即 [] を返すこと"""
        with patch("rakuten_client.requests.get", return_value=_500_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search("テスト", APP_ID)

        assert result == []
        mock_sleep.assert_not_called()

    # ── JSON body の too_many_requests ────────

    def test_json_rate_limit_all_attempts(self):
        """JSON本文にtoo_many_requestsが入る場合も同じリトライ制御になること"""
        with patch("rakuten_client.requests.get", return_value=_200_json_rate_limit()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search("テスト", APP_ID)

        assert result == []
        assert mock_sleep.call_count == 2  # 最終試行はsleepなし

    # ── max_retries=1（最小設定）────────────

    def test_max_retries_1_no_sleep(self):
        """RAKUTEN_MAX_RETRIES=1 のとき1回で即終了し sleep しないこと"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "1"}):

            result = perform_rakuten_api_search("テスト", APP_ID)

        assert result == []
        mock_sleep.assert_not_called()


# ─────────────────────────────────────────────
#  perform_rakuten_api_search_from_itemcode のテスト
# ─────────────────────────────────────────────

class TestPerformRakutenApiSearchFromItemcode:

    def test_all_429_returns_empty(self):
        """全試行で429のとき [] を返すこと"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep"), \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search_from_itemcode("test:item123", APP_ID)

        assert result == []

    def test_all_429_no_sleep_on_last_attempt(self):
        """最終試行で429のとき sleep しないこと"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            perform_rakuten_api_search_from_itemcode("test:item123", APP_ID)

        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list == [call(10), call(20)]

    def test_retry_succeeds_on_second_attempt(self):
        """1回目429・2回目成功のとき正常なアイテムリストを返すこと"""
        responses = [_429_response(), _200_ok()]
        with patch("rakuten_client.requests.get", side_effect=responses), \
             patch("rakuten_client.time.sleep"), \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search_from_itemcode("test:item123", APP_ID)

        assert len(result) == 1

    def test_500_returns_empty_without_retry(self):
        """500エラーのときリトライせず即 [] を返すこと"""
        with patch("rakuten_client.requests.get", return_value=_500_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "3"}):

            result = perform_rakuten_api_search_from_itemcode("test:item123", APP_ID)

        assert result == []
        mock_sleep.assert_not_called()

    def test_max_retries_1_no_sleep(self):
        """RAKUTEN_MAX_RETRIES=1 のとき1回で即終了し sleep しないこと"""
        with patch("rakuten_client.requests.get", return_value=_429_response()), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "1"}):

            result = perform_rakuten_api_search_from_itemcode("test:item123", APP_ID)

        assert result == []
        mock_sleep.assert_not_called()


# ─────────────────────────────────────────────
#  timeout 追加確認テスト
# ─────────────────────────────────────────────

class TestRakutenTimeout:

    def test_perform_search_passes_timeout(self):
        """perform_rakuten_api_search が requests.get に timeout= を渡すこと"""
        with patch("rakuten_client.requests.get", return_value=_200_ok()) as mock_get, \
             patch("rakuten_client.time.sleep"):
            perform_rakuten_api_search("テスト", APP_ID)
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)

    def test_perform_itemcode_passes_timeout(self):
        """perform_rakuten_api_search_from_itemcode が requests.get に timeout= を渡すこと"""
        with patch("rakuten_client.requests.get", return_value=_200_ok()) as mock_get, \
             patch("rakuten_client.time.sleep"):
            perform_rakuten_api_search_from_itemcode("test:item123", APP_ID)
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)

    def test_timeout_last_attempt_returns_empty(self):
        """最終試行で Timeout → [] を返し sleep しないこと"""
        with patch("rakuten_client.requests.get",
                   side_effect=_requests.exceptions.Timeout), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "1"}):
            result = perform_rakuten_api_search("テスト", APP_ID)
        assert result == []
        mock_sleep.assert_not_called()

    def test_timeout_retries_and_succeeds(self):
        """1回目 Timeout → 2回目成功でアイテムを返すこと"""
        with patch("rakuten_client.requests.get",
                   side_effect=[_requests.exceptions.Timeout, _200_ok()]) as mock_get, \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_MAX_RETRIES": "2"}):
            result = perform_rakuten_api_search("テスト", APP_ID)
        assert len(result) == 1
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(10)  # attempt=0: wait=10*1

    def test_search_rakuten_product_api_passes_timeout(self):
        """search_rakuten_product_api が requests.get に timeout= を渡すこと"""
        mock_resp = _mock_response(status_code=200, json_body={"Products": []}, text="ok")
        with patch("rakuten_client.requests.get", return_value=mock_resp) as mock_get, \
             patch("rakuten_client.time.sleep"):
            search_rakuten_product_api("B000TEST01")
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)

    def test_search_ichiba_from_product_passes_timeout(self):
        """search_ichiba_from_product が requests.get に timeout= を渡すこと"""
        mock_resp = _mock_response(status_code=200, json_body={"Items": []}, text="ok")
        with patch("rakuten_client.requests.get", return_value=mock_resp) as mock_get, \
             patch("rakuten_client.time.sleep"):
            search_ichiba_from_product(jan="4901234567890")
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == (10, 30)

    def test_sleep_time_float_string_does_not_raise(self):
        """RAKUTEN_SLEEP_TIME='0.2' のような float 文字列でもクラッシュしないこと"""
        mock_resp = _mock_response(status_code=200, json_body={"Products": []}, text="ok")
        with patch("rakuten_client.requests.get", return_value=mock_resp), \
             patch("rakuten_client.time.sleep") as mock_sleep, \
             patch.dict(os.environ, {"RAKUTEN_SLEEP_TIME": "0.2"}):
            search_rakuten_product_api("B000TEST01")
        mock_sleep.assert_called_once_with(0.2)
