# tests/test_fee_none_propagation.py
"""
FBA手数料未取得（fee=None）時の None 伝播テスト。

テスト対象:
  - amazon_fee.annotate_fees_to_asin_price_map  (dict形式パターン)
  - price_calculation.calculate_price_difference
  - batch_runner.py の pass_filter 判定ロジック（ヘルパー関数で写して検証）
  - main.py の pass_filter 判定ロジック（ヘルパー関数で写して検証）
"""
import pytest
from amazon_fee import annotate_fees_to_asin_price_map, DEFAULT_FBA_SHIPPING_FEE
from price_calculation import calculate_price_difference

# batch_runner.py / main.py と同じ閾値デフォルト値
_MIN_PROFIT_YEN = 700
_MIN_ROI_PERCENT = 15.0


# ─────────────────────────────────────────────
#  pass_filter 判定ロジックの写し（テスト専用ヘルパー）
#
#  注意: 以下のヘルパーは batch_runner.py L307-339 / main.py L167-189 の
#  判定ロジックと同一。プロダクション側を変更した場合はここも合わせて更新すること。
# ─────────────────────────────────────────────

def _batch_runner_pass_filter(data: dict) -> bool:
    """batch_runner.py の pass_filter 判定ロジックの写し（1注文あたりベース）"""
    profit_total = data.get("price_diff_after_point") or data.get("price_diff")

    rakuten_cost_total = data.get("rakuten_effective_cost_total")
    roi_percent = data.get("roi_percent")
    if roi_percent is None:
        profit_rate = data.get("profit_rate")
        if profit_rate is not None:
            roi_percent = float(profit_rate) * 100.0
        elif profit_total is not None and rakuten_cost_total:
            base = float(rakuten_cost_total)
            if base > 0:
                roi_percent = float(profit_total) / base * 100.0

    return (
        profit_total is not None
        and roi_percent is not None
        and profit_total >= _MIN_PROFIT_YEN
        and roi_percent >= _MIN_ROI_PERCENT
    )


def _main_pass_filter(data: dict) -> bool:
    """main.py の pass_filter 判定ロジックの写し（L167-189）"""
    rakuten_price_total = data.get("rakuten_effective_cost_total")

    profit_total = data.get("profit_total")
    if profit_total is None:
        profit_total = data.get("price_diff_after_point") or data.get("price_diff")

    roi_ratio = data.get("roi_total")
    if roi_ratio is None and profit_total is not None and rakuten_price_total:
        try:
            base = float(rakuten_price_total)
            if base > 0:
                roi_ratio = float(profit_total) / base
        except Exception:
            roi_ratio = None

    roi_percent = roi_ratio * 100.0 if roi_ratio is not None else None

    return (
        profit_total is not None
        and roi_percent is not None
        and profit_total >= _MIN_PROFIT_YEN
        and roi_percent >= _MIN_ROI_PERCENT
    )


# ─────────────────────────────────────────────
#  ヘルパー
# ─────────────────────────────────────────────

def _base_asin_map(asin="B000TEST01", price=5000):
    """annotate_fees_to_asin_price_map 用の最小 asin_price_map"""
    return {asin: {"price": price, "shipping": 0, "is_fba": True}}


def _make_calc_info(
    total_fee, price=5000, rakuten_cost=3000, rakuten_point=0,
    rakuten_quantity=1, amazon_quantity=None,
):
    """calculate_price_difference 用の最小 info dict

    amazon_quantity: Amazon販売単位の数量（タイトルから取れなければ None → 1 扱い）
    rakuten_quantity: 楽天商品の内容量（_choose_best_rakuten_offer が参照する）
    """
    info = {
        "price": price,
        "total_fee": total_fee,
        "title": "テスト商品",
        "rakuten_cost_1": rakuten_cost,
        "rakuten_point_1": rakuten_point,
        "rakuten_quantity_1": rakuten_quantity,
    }
    if amazon_quantity is not None:
        info["amazon_quantity"] = amazon_quantity
    return info


# ─────────────────────────────────────────────
#  amazon_fee.annotate_fees_to_asin_price_map
# ─────────────────────────────────────────────

class TestAnnotateFeesToAsinPriceMap:

    def test_fee_none_makes_total_fee_none(self):
        """fee=None のとき total_fee は None になること（shipping_fee だけが入ってはいけない）"""
        asin = "B000TEST01"
        out = annotate_fees_to_asin_price_map(
            _base_asin_map(asin),
            {asin: {"fee": None, "fee_raw": []}},
        )
        assert out[asin]["total_fee"] is None

    def test_fee_zero_gives_shipping_only(self):
        """fee=0（正常な0円手数料）のとき total_fee = 0 + DEFAULT_FBA_SHIPPING_FEE になること"""
        asin = "B000TEST01"
        out = annotate_fees_to_asin_price_map(
            _base_asin_map(asin),
            {asin: {"fee": 0, "fee_raw": []}},
        )
        assert out[asin]["total_fee"] == DEFAULT_FBA_SHIPPING_FEE

    def test_fee_positive_adds_shipping(self):
        """fee=800 のとき total_fee = 800 + DEFAULT_FBA_SHIPPING_FEE になること"""
        asin = "B000TEST01"
        out = annotate_fees_to_asin_price_map(
            _base_asin_map(asin),
            {asin: {"fee": 800, "fee_raw": []}},
        )
        assert out[asin]["total_fee"] == 800 + DEFAULT_FBA_SHIPPING_FEE


# ─────────────────────────────────────────────
#  price_calculation.calculate_price_difference
# ─────────────────────────────────────────────

class TestCalculatePriceDifference:

    # ── fee=None ケース ──────────────────────

    def test_fee_none_profit_fields_are_none(self):
        """total_fee=None のとき fee依存フィールドはすべて None になること"""
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=None)})
        info = result["B000TEST01"]

        assert info["profit_per_item"] is None
        assert info["profit_rate"] is None
        assert info["price_diff"] is None
        assert info["price_diff_after_point"] is None
        assert info["amazon_received_per_item"] is None

    def test_fee_none_preserves_price_per_item(self):
        """total_fee=None でも amazon_price_per_item は算出されること（price / qty）"""
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=None, price=6000)})
        info = result["B000TEST01"]

        assert info["amazon_price_per_item"] == 6000.0

    def test_fee_none_preserves_rakuten_cost(self):
        """total_fee=None でも楽天データから rakuten_effective_cost_total は保持されること"""
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=None, rakuten_cost=3000)})
        info = result["B000TEST01"]

        # ポイントなし・数量1 → effective_cost_total = 3000
        assert info["rakuten_effective_cost_total"] == 3000.0

    def test_fee_none_preserves_amazon_quantity(self):
        """total_fee=None でも amazon_quantity は info に設定されること"""
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=None)})
        assert result["B000TEST01"]["amazon_quantity"] == 1

    def test_fee_none_does_not_affect_other_asins(self):
        """fee=None の ASIN があっても、他の正常 ASIN の計算は影響を受けないこと"""
        asins = {
            "B000NONE01": _make_calc_info(total_fee=None),
            "B000OK0001": _make_calc_info(total_fee=800),
        }
        result = calculate_price_difference(asins)

        assert result["B000NONE01"]["profit_per_item"] is None
        assert result["B000OK0001"]["profit_per_item"] is not None

    # ── fee=0 ケース ─────────────────────────

    def test_fee_zero_is_valid_and_calculates(self):
        """total_fee=0（正常な0円手数料）のとき計算が正常に走ること"""
        # profit = (5000 - 0) - 3000 = 2000
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=0, price=5000, rakuten_cost=3000)})
        info = result["B000TEST01"]

        assert info["profit_per_item"] == 2000.0
        assert info["amazon_received_per_item"] == 5000.0

    def test_fee_zero_roi(self):
        """total_fee=0 のとき ROI = 2000 / 3000 ≒ 0.667 になること"""
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=0, price=5000, rakuten_cost=3000)})
        roi = result["B000TEST01"]["profit_rate"]

        assert roi == pytest.approx(2000 / 3000, rel=1e-6)

    # ── 通常値ケース ─────────────────────────

    def test_normal_fee_calculates_correctly(self):
        """total_fee=800 の正常ケースで利益・ROI が正しく計算されること"""
        # profit = (5000 - 800) - 3000 = 1200
        result = calculate_price_difference({"B000TEST01": _make_calc_info(total_fee=800, price=5000, rakuten_cost=3000)})
        info = result["B000TEST01"]

        assert info["profit_per_item"] == 1200.0
        assert info["amazon_received_per_item"] == 4200.0
        assert info["profit_rate"] == pytest.approx(1200 / 3000, rel=1e-6)

    def test_normal_fee_with_rakuten_point(self):
        """楽天ポイントがある場合、ポイント控除後の原価で利益計算されること"""
        # rakuten実質コスト = 3000 - 300 = 2700
        # profit = (5000 - 800) - 2700 = 1500
        result = calculate_price_difference({
            "B000TEST01": _make_calc_info(total_fee=800, price=5000, rakuten_cost=3000, rakuten_point=300)
        })
        info = result["B000TEST01"]

        assert info["profit_per_item"] == 1500.0
        assert info["rakuten_effective_cost_total"] == 2700.0

    def test_normal_fee_multi_quantity(self):
        """Amazon数量2のとき profit_per_item は総利益 / 2 になること"""
        # amazon_quantity=2, rakuten_quantity=2 で「2個セット商品」を揃えて渡す
        # rak_per_item = 3000 / 2 = 1500
        # rak_total（最安候補の effective_total） = 3000
        # amazon_net_total = 5000 - 800 = 4200
        # profit_total = 4200 - 3000 = 1200
        # profit_per_item = 1200 / 2 = 600
        result = calculate_price_difference({
            "B000TEST01": _make_calc_info(
                total_fee=800, price=5000, rakuten_cost=3000,
                rakuten_quantity=2, amazon_quantity=2,
            )
        })
        info = result["B000TEST01"]

        assert info["profit_per_item"] == 600.0


# ─────────────────────────────────────────────
#  pass_filter 判定テスト（batch_runner.py 相当）
# ─────────────────────────────────────────────

class TestPassFilterBatchRunner:

    # ── fee=None ケース ──────────────────────

    def test_fee_none_pass_filter_is_false(self):
        """fee=None 由来で price_diff が None のとき pass_filter=False になること"""
        # calculate_price_difference が fee=None で出力する data を再現
        data = {
            "price_diff_after_point": None,   # fee依存 → None
            "price_diff": None,               # fee依存 → None
            "profit_rate": None,              # fee依存 → None
            "rakuten_effective_cost_total": 3000.0,  # 楽天データは保持
        }
        assert _batch_runner_pass_filter(data) is False

    def test_fee_none_both_diffs_none_is_false(self):
        """price_diff_after_point も price_diff も None のとき profit_total=None で False"""
        data = {
            "price_diff_after_point": None,
            "price_diff": None,
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _batch_runner_pass_filter(data) is False

    # ── 正常系サニティチェック ───────────────

    def test_normal_profit_above_threshold_is_true(self):
        """利益・ROI が閾値以上のとき pass_filter=True になること"""
        # profit=1200, rak_cost=3000 → ROI=40% (>15%)
        data = {
            "price_diff_after_point": 1200.0,
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _batch_runner_pass_filter(data) is True

    def test_profit_below_min_is_false(self):
        """利益が MIN_PROFIT_YEN(700円) 未満のとき pass_filter=False"""
        data = {
            "price_diff_after_point": 500.0,   # < 700
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _batch_runner_pass_filter(data) is False

    def test_roi_below_min_is_false(self):
        """ROI が MIN_ROI_PERCENT(15%) 未満のとき pass_filter=False"""
        # profit=200, rak_cost=3000 → ROI=6.7% < 15%
        data = {
            "price_diff_after_point": 200.0,
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _batch_runner_pass_filter(data) is False


# ─────────────────────────────────────────────
#  pass_filter 判定テスト（main.py 相当）
# ─────────────────────────────────────────────

class TestPassFilterMain:

    # ── fee=None ケース ──────────────────────

    def test_fee_none_pass_filter_is_false(self):
        """fee=None 由来で price_diff が None のとき pass_filter=False になること"""
        # calculate_price_difference が fee=None で出力する data を再現
        data = {
            "price_diff_after_point": None,   # fee依存 → None
            "price_diff": None,               # fee依存 → None
            "rakuten_effective_cost_total": 3000.0,  # 楽天データは保持
        }
        assert _main_pass_filter(data) is False

    def test_fee_none_both_fallbacks_none(self):
        """price_diff_after_point も price_diff も None のとき profit_total=None で False"""
        # main.py: profit_total = data.get("price_diff_after_point") or data.get("price_diff")
        # None or None = None → pass_filter=False
        data = {
            "price_diff_after_point": None,
            "price_diff": None,
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _main_pass_filter(data) is False

    # ── 正常系サニティチェック ───────────────

    def test_normal_profit_above_threshold_is_true(self):
        """利益・ROI が閾値以上のとき pass_filter=True になること"""
        # profit=1200, rak_cost=3000 → ROI=40% (>15%)
        data = {
            "price_diff_after_point": 1200.0,
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _main_pass_filter(data) is True

    def test_profit_below_min_is_false(self):
        """利益が MIN_PROFIT_YEN(700円) 未満のとき pass_filter=False"""
        data = {
            "price_diff_after_point": 500.0,   # < 700
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _main_pass_filter(data) is False

    def test_roi_below_min_is_false(self):
        """ROI が MIN_ROI_PERCENT(15%) 未満のとき pass_filter=False"""
        # profit=200, rak_cost=3000 → ROI=6.7% < 15%
        data = {
            "price_diff_after_point": 200.0,
            "rakuten_effective_cost_total": 3000.0,
        }
        assert _main_pass_filter(data) is False
