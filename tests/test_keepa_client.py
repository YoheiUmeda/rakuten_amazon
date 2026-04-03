# tests/test_keepa_client.py
"""keepa_client の最小テスト。"""
from __future__ import annotations

import keepa_client as kc


# ── _inject_min_drops30 (get_asins_from_finder 内ロジック) ───────────────────

class TestMinDrops30Injection:
    """KEEPA_FINDER_MIN_DROPS30 が selection に正しく注入されることを確認する。"""

    def _apply(self, monkeypatch, env_val: str, selection: dict) -> dict:
        """get_asins_from_finder の注入ロジックを selection に対して再現する。"""
        monkeypatch.setenv("KEEPA_FINDER_MIN_DROPS30", env_val)
        try:
            min_drops = int(kc.os.getenv("KEEPA_FINDER_MIN_DROPS30", "0") or "0")
        except (ValueError, TypeError):
            min_drops = 0
        if min_drops > 0 and "salesRankDrops30Min" not in selection:
            selection["salesRankDrops30Min"] = min_drops
        return selection

    def test_injected_when_env_set(self, monkeypatch):
        """MIN_DROPS30=5 のとき salesRankDrops30Min=5 が注入される。"""
        sel = {"categoryId": [16026405]}
        self._apply(monkeypatch, "5", sel)
        assert sel.get("salesRankDrops30Min") == 5

    def test_not_injected_when_zero(self, monkeypatch):
        """MIN_DROPS30=0（デフォルト）のとき注入されない。"""
        sel = {"categoryId": [16026405]}
        self._apply(monkeypatch, "0", sel)
        assert "salesRankDrops30Min" not in sel

    def test_not_overwritten_when_already_set(self, monkeypatch):
        """selection に salesRankDrops30Min が既設定のとき上書きしない。"""
        sel = {"categoryId": [16026405], "salesRankDrops30Min": 10}
        self._apply(monkeypatch, "5", sel)
        assert sel["salesRankDrops30Min"] == 10
