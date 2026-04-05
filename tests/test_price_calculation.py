# tests/test_price_calculation.py
"""
price_calculation.py の profit / ROI 計算ロジックのテスト。

テスト対象:
  - price_calculation._choose_best_rakuten_offer
  - price_calculation.calculate_price_difference（楽天候補なし / rak_total=0 の境界値）

注: fee=None/0 の伝播・pass_filter は test_fee_none_propagation.py で網羅済み。
    ここでは未カバーの論点だけを最小限で追加する。
"""
import pytest
from price_calculation import _choose_best_rakuten_offer, calculate_price_difference


# ─────────────────────────────────────────────
#  _choose_best_rakuten_offer のテスト
# ─────────────────────────────────────────────

class TestChooseBestRakutenOffer:

    def test_no_valid_candidates_returns_none(self):
        """有効な楽天候補が1件もないとき (None, None, None) を返すこと"""
        info = {}  # rakuten_cost_1〜3 が存在しない
        result = _choose_best_rakuten_offer(info, amazon_quantity=1)
        assert result == (None, None, None)

    def test_single_candidate_returns_correctly(self):
        """候補1件のとき、その値が正しく返ること"""
        info = {
            "rakuten_cost_1": 3000,
            "rakuten_point_1": 0,
            "rakuten_quantity_1": 1,
        }
        total, per_item, qty = _choose_best_rakuten_offer(info, amazon_quantity=1)
        assert total == pytest.approx(3000.0)
        assert per_item == pytest.approx(3000.0)
        assert qty == 1

    def test_picks_cheapest_per_item_among_multiple(self):
        """複数候補のうち 1個あたり原価が最安のものを選ぶこと"""
        info = {
            # 候補1: 3000円 / 1個 = 3000円/個
            "rakuten_cost_1": 3000,
            "rakuten_point_1": 0,
            "rakuten_quantity_1": 1,
            # 候補2: 5000円 / 3個 ≈ 1667円/個 → こちらが安い
            "rakuten_cost_2": 5000,
            "rakuten_point_2": 0,
            "rakuten_quantity_2": 3,
        }
        total, per_item, qty = _choose_best_rakuten_offer(info, amazon_quantity=1)
        assert total == pytest.approx(5000.0)
        assert per_item == pytest.approx(5000.0 / 3)
        assert qty == 3

    def test_point_reduces_effective_cost(self):
        """ポイントが実質原価から控除されること"""
        info = {
            "rakuten_cost_1": 3000,
            "rakuten_point_1": 300,  # 10%ポイント
            "rakuten_quantity_1": 1,
        }
        total, per_item, qty = _choose_best_rakuten_offer(info, amazon_quantity=1)
        assert total == pytest.approx(2700.0)  # 3000 - 300
        assert per_item == pytest.approx(2700.0)

    def test_qty_none_falls_back_to_amazon_quantity(self):
        """楽天の数量が取れないとき amazon_quantity にフォールバックすること"""
        info = {
            "rakuten_cost_1": 4000,
            "rakuten_point_1": 0,
            "rakuten_quantity_1": None,  # 数量不明
        }
        total, per_item, qty = _choose_best_rakuten_offer(info, amazon_quantity=2)
        assert qty == 2
        assert per_item == pytest.approx(4000.0 / 2)

    def test_anomalous_low_price_skipped_when_amazon_price_given(self):
        """Amazon単価比30%未満の楽天候補がスキップされ、次点が採用されること（JAN誤登録対策）"""
        info = {
            # 候補1: 780円 / 1個 = Amazon(8380円)の9% → スキップ
            "rakuten_cost_1": 780,
            "rakuten_point_1": 0,
            "rakuten_quantity_1": 1,
            # 候補2: 7180円 / 1個 = Amazon(8380円)の86% → 採用
            "rakuten_cost_2": 7180,
            "rakuten_point_2": 71,
            "rakuten_quantity_2": 1,
        }
        total, per_item, qty = _choose_best_rakuten_offer(
            info, amazon_quantity=1, amazon_price_per_item=8380.0
        )
        assert total == pytest.approx(7109.0)  # 7180 - 71
        assert per_item == pytest.approx(7109.0)
        assert qty == 1

    def test_no_amazon_price_disables_ratio_filter(self):
        """amazon_price_per_item が None のとき ratio フィルタを適用しないこと"""
        info = {
            "rakuten_cost_1": 780,
            "rakuten_point_1": 0,
            "rakuten_quantity_1": 1,
        }
        total, per_item, qty = _choose_best_rakuten_offer(
            info, amazon_quantity=1, amazon_price_per_item=None
        )
        assert total == pytest.approx(780.0)  # フィルタなしで通過


# ─────────────────────────────────────────────
#  calculate_price_difference の境界値テスト
# ─────────────────────────────────────────────

class TestCalculatePriceDifferenceExtra:

    def test_no_rakuten_offer_sets_amazon_fields_and_nulls_profit(self):
        """楽天候補がないとき amazon 系フィールドは設定され profit 系は None になること"""
        asins = {
            "B000TEST01": {
                "price": 5000,
                "total_fee": 500,
                "amazon_quantity": 1,
                # rakuten_cost_* なし
            }
        }
        result = calculate_price_difference(asins)
        info = result["B000TEST01"]

        # amazon 系は設定される
        assert info["amazon_received_per_item"] == pytest.approx(4500.0)  # 5000 - 500
        assert info["amazon_price_per_item"] == pytest.approx(5000.0)
        # profit 系は None
        assert info["profit_per_item"] is None
        assert info["profit_rate"] is None
        assert info["profit_total"] is None

    def test_rak_total_zero_makes_roi_none(self):
        """ポイントが原価と等しく rak_total=0 のとき roi が None になること（ゼロ除算ガード）"""
        asins = {
            "B000TEST01": {
                "price": 5000,
                "total_fee": 500,
                "amazon_quantity": 1,
                # cost=2000: Amazon5000円の40%→ratio フィルタ通過、point=2000でeffective=0
                "rakuten_cost_1": 2000,
                "rakuten_point_1": 2000,  # point == cost → effective_total = 0
                "rakuten_quantity_1": 1,
            }
        }
        result = calculate_price_difference(asins)
        info = result["B000TEST01"]

        assert info["rakuten_effective_cost_total"] == pytest.approx(0.0)
        assert info["profit_rate"] is None  # ゼロ除算ガード
        assert info["roi_percent"] is None  # ゼロ除算ガード（roi_percent も None）


# ─────────────────────────────────────────────
#  roi_percent 出力テスト
# ─────────────────────────────────────────────

class TestRoiPercentOutput:

    def test_roi_percent_equals_profit_rate_times_100(self):
        """roi_percent が profit_rate * 100 と一致すること"""
        asins = {
            "B000TEST01": {
                "price": 5000,
                "total_fee": 500,
                "amazon_quantity": 1,
                "rakuten_cost_1": 3000,
                "rakuten_point_1": 0,
                "rakuten_quantity_1": 1,
            }
        }
        result = calculate_price_difference(asins)
        info = result["B000TEST01"]

        assert info["profit_rate"] is not None
        assert info["roi_percent"] == pytest.approx(info["profit_rate"] * 100.0)

    def test_roi_percent_none_when_fee_is_none(self):
        """fee=None のとき roi_percent も None になること"""
        asins = {
            "B000TEST01": {
                "price": 5000,
                "total_fee": None,
                "amazon_quantity": 1,
                "rakuten_cost_1": 3000,
                "rakuten_point_1": 0,
                "rakuten_quantity_1": 1,
            }
        }
        result = calculate_price_difference(asins)
        assert result["B000TEST01"]["roi_percent"] is None

    def test_roi_percent_none_when_no_rakuten(self):
        """楽天候補なしのとき roi_percent も None になること"""
        asins = {
            "B000TEST01": {
                "price": 5000,
                "total_fee": 500,
                "amazon_quantity": 1,
            }
        }
        result = calculate_price_difference(asins)
        assert result["B000TEST01"]["roi_percent"] is None
