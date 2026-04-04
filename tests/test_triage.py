# tests/test_triage.py
"""triage.classify_deal の単体テスト。既存の失敗パターンを再現する。"""
from __future__ import annotations

import pytest
from triage import classify_deal

MIN_P = 700
MIN_R = 15.0


class TestClassifyDeal:

    # ── reject_no_rakuten ─────────────────────────────────────────

    def test_no_rakuten_hit(self):
        data = {"reject_reason": "no_rakuten_hit"}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_no_rakuten"
        assert result["block_reason"] == "no_rakuten_hit"
        assert result["next_action"] == "skip"

    def test_cached_no_hit(self):
        data = {"reject_reason": "cached_no_hit"}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_no_rakuten"
        assert result["next_action"] == "skip"

    # ── review_needed ─────────────────────────────────────────────

    def test_all_rakuten_items_rejected(self):
        """楽天はヒットしたが全候補リジェクト → review_needed"""
        data = {"reject_reason": "all_rakuten_items_rejected"}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "review_needed"
        assert result["next_action"] == "manual_review"

    # ── profit_candidate ─────────────────────────────────────────

    def test_profit_candidate_passes_both_thresholds(self):
        data = {"profit_total": 1000, "roi_percent": 20.0}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "profit_candidate"
        assert result["block_reason"] is None
        assert result["next_action"] == "manual_review"

    def test_profit_candidate_at_exact_threshold(self):
        data = {"profit_total": 700, "roi_percent": 15.0}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "profit_candidate"

    # ── reject_profit ─────────────────────────────────────────────

    def test_reject_profit_low_profit(self):
        data = {"profit_total": 100, "roi_percent": 20.0}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_profit"
        assert result["next_action"] == "skip"
        assert "profit=100" in result["block_reason"]

    def test_reject_profit_low_roi(self):
        data = {"profit_total": 2000, "roi_percent": 5.0}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_profit"
        assert "roi=5.0%" in result["block_reason"]

    def test_reject_profit_both_low(self):
        data = {"profit_total": 100, "roi_percent": 5.0}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_profit"

    # ── reject_no_data ────────────────────────────────────────────

    def test_reject_no_data_no_fee(self):
        """fee なし → profit_total=None → reject_no_data"""
        data = {"profit_total": None, "roi_percent": None}
        result = classify_deal(data, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_no_data"
        assert result["next_action"] == "manual_review"

    def test_reject_no_data_empty(self):
        """データなし（Keepaのみ取得できた段階）"""
        result = classify_deal({}, MIN_P, MIN_R)
        assert result["deal_status"] == "reject_no_data"

    # ── 副作用なし ────────────────────────────────────────────────

    def test_no_side_effect_on_input(self):
        """classify_deal は data を変更しない"""
        data = {"profit_total": 1000, "roi_percent": 20.0}
        original = dict(data)
        classify_deal(data, MIN_P, MIN_R)
        assert data == original
