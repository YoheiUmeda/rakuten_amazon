# tests/test_escape_rakuten_keyword.py
"""
escape_rakuten_keyword のバイト長制御テスト。

- 蓄積ループが URLエンコード後バイトで計算されること
- 長い日本語タイトルでも ASIN fallback に逃げないこと
- 短いタイトルが従来どおり返ること
"""
import urllib.parse

import pytest

from rakuten_client import escape_rakuten_keyword

FALLBACK = "B0F5BTJBJP"
BYTE_LIMIT = 800

# B0F5BTJBJPの実タイトル（エンコード後オーバーしていた長いタイトル）
LONG_TITLE = (
    "モバイルルーター USB型 ポケットWiFi 365チャージWiFi 車載 Wi-Fi バッテリーレス "
    "スティックWiFi 10ギガ付 タイプC 1年間 使える ポケット WiFi ギガ リチャージ "
    "可能 簡単設定 スティック WiFi 月額費用無し モバイルWiFi プリペイドWiFi"
)


def encoded_bytes(s: str) -> int:
    """URL エンコード後のバイト長を返す。"""
    return len(urllib.parse.quote(s, safe='').encode('utf-8'))


class TestLongTitleByteLimit:

    def test_long_title_stays_within_byte_limit(self):
        """長い日本語タイトルでも URLエンコード後が byte_limit 以内に収まる。"""
        result = escape_rakuten_keyword(LONG_TITLE, FALLBACK, byte_limit=BYTE_LIMIT)
        assert encoded_bytes(result) <= BYTE_LIMIT, (
            f"encoded bytes {encoded_bytes(result)} > {BYTE_LIMIT}: keyword={result!r}"
        )

    def test_long_title_does_not_fallback_to_asin(self):
        """長いタイトルでも ASIN フォールバックにならない（意味のあるキーワードが使われる）。"""
        result = escape_rakuten_keyword(LONG_TITLE, FALLBACK, byte_limit=BYTE_LIMIT)
        assert result != FALLBACK, (
            f"fallback to ASIN occurred but should have used truncated title: {result!r}"
        )

    def test_result_is_not_empty(self):
        """短縮後のキーワードが空でない。"""
        result = escape_rakuten_keyword(LONG_TITLE, FALLBACK, byte_limit=BYTE_LIMIT)
        assert len(result) >= 4


class TestShortTitleUnchanged:

    def test_short_ascii_title_passes_through(self):
        """短い ASCII タイトルは変更されずに返る。"""
        title = "USB WiFi Adapter 600Mbps"
        result = escape_rakuten_keyword(title, FALLBACK)
        assert result != FALLBACK
        assert "USB" in result or "WiFi" in result

    def test_short_japanese_title_passes_through(self):
        """短い日本語タイトルは ASIN fallback にならない。"""
        title = "モバイルルーター WiFi 本体"
        result = escape_rakuten_keyword(title, FALLBACK)
        assert result != FALLBACK

    def test_empty_title_returns_fallback(self):
        """空タイトルは fallback を返す（既存動作を壊さない）。"""
        result = escape_rakuten_keyword("", FALLBACK)
        assert result == FALLBACK
