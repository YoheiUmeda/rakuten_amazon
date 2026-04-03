# tests/test_prefilter.py
"""prefilter_for_rakuten の最小テスト。"""
from __future__ import annotations

import pytest

from prefilter import prefilter_for_rakuten


def _item(price=5000, fee=1000, drops30=None):
    """テスト用 ASIN item を返す。"""
    return {"price": price, "total_fee": fee, "sales_rank_drops30": drops30}


# ── 販売速度フィルタ（min_sales_rank_drops30） ────────────────────────────────

class TestSalesRankDropsFilter:

    def test_default_zero_passes_all(self):
        """min_sales_rank_drops30=0（デフォルト）のとき速度フィルタは無効。"""
        asin_map = {
            "A001": _item(drops30=0),
            "A002": _item(drops30=None),
            "A003": _item(drops30=10),
        }
        filtered, excluded = prefilter_for_rakuten(asin_map, min_price=0, min_max_possible_profit=0)
        assert set(filtered.keys()) == {"A001", "A002", "A003"}

    def test_below_threshold_excluded(self):
        """drops30 < min_sales_rank_drops30 のとき除外される。"""
        asin_map = {"A001": _item(drops30=2)}
        filtered, excluded = prefilter_for_rakuten(
            asin_map, min_price=0, min_max_possible_profit=0, min_sales_rank_drops30=3
        )
        assert "A001" not in filtered
        assert excluded["A001"].startswith("low_sales_velocity")

    def test_at_threshold_passes(self):
        """drops30 == min_sales_rank_drops30 のとき通過する（境界値）。"""
        asin_map = {"A001": _item(drops30=3)}
        filtered, excluded = prefilter_for_rakuten(
            asin_map, min_price=0, min_max_possible_profit=0, min_sales_rank_drops30=3
        )
        assert "A001" in filtered

    def test_none_drops_passes_fail_open(self):
        """sales_rank_drops30 が None のとき fail-open で通過する。"""
        asin_map = {"A001": _item(drops30=None)}
        filtered, excluded = prefilter_for_rakuten(
            asin_map, min_price=0, min_max_possible_profit=0, min_sales_rank_drops30=5
        )
        assert "A001" in filtered

    def test_above_threshold_passes(self):
        """drops30 > min_sales_rank_drops30 のとき通過する。"""
        asin_map = {"A001": _item(drops30=10)}
        filtered, excluded = prefilter_for_rakuten(
            asin_map, min_price=0, min_max_possible_profit=0, min_sales_rank_drops30=3
        )
        assert "A001" in filtered
