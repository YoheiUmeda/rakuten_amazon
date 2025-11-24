from __future__ import annotations

from typing import Dict, Tuple, Any

from utils.utils import extract_quantity


def _choose_best_rakuten_offer(
    info: Dict[str, Any],
    amazon_quantity: int,
) -> Tuple[float | None, float | None, int | None]:
    """
    楽天候補のうち「1個あたりの実質仕入れ値」が一番安いものを 1 件だけ返す。
    返り値:
        (effective_cost_total, cost_per_item, quantity)
    なければ (None, None, None)
    """
    best_total = None
    best_per_item = None
    best_qty = None

    for i in range(1, 4):
        cost = info.get(f"rakuten_cost_{i}")
        point = info.get(f"rakuten_point_{i}", 0) or 0
        qty = info.get(f"rakuten_quantity_{i}")

        # 金額が入っていない候補はスキップ
        if not cost or cost <= 0:
            continue

        # 数量が取れなければ Amazon 側と同じとみなす
        try:
            qty = int(qty) if qty is not None else amazon_quantity
        except Exception:
            qty = amazon_quantity

        if qty <= 0:
            qty = amazon_quantity

        # 実質仕入れ額（ポイント控除後）
        effective_total = float(cost) - float(point)
        per_item = effective_total / qty

        # 1個あたり原価が最安のものを採用
        if best_per_item is None or per_item < best_per_item:
            best_per_item = per_item
            best_total = effective_total
            best_qty = qty

    return best_total, best_per_item, best_qty


def calculate_price_difference(
    asins: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Keepa + SP-API + 楽天API で集約した dict に対して、
    ・Amazon受取額（手数料控除後）
    ・楽天仕入れ原価（ポイント控除後）
    ・利益・ROI
    を付加して返す。
    """
    for asin, info in asins.items():
        # -------- Amazon 側 --------
        price = float(info.get("price") or 0.0)
        fee = float(info.get("total_fee") or info.get("fee") or 0.0)
        title = info.get("title") or ""

        # Amazon 側の数量（「10枚」など）。取れなければ 1。
        aq = info.get("amazon_quantity")
        if aq is None:
            aq = extract_quantity(title) or 1

        try:
            amazon_quantity = int(aq)
        except Exception:
            amazon_quantity = 1

        if amazon_quantity <= 0:
            amazon_quantity = 1

        # 1SKUあたりの受取額（販売価格 - 手数料）
        amazon_net_total = price - fee
        amazon_received_per_item = (
            amazon_net_total / amazon_quantity if amazon_quantity > 0 else None
        )
        amazon_price_per_item = price / amazon_quantity if amazon_quantity > 0 else None

        # -------- 楽天 側 --------
        rak_total, rak_per_item, rak_qty = _choose_best_rakuten_offer(
            info, amazon_quantity
        )

        # 楽天候補が取れなかった場合は利益系は None
        if rak_total is None:
            info.update(
                {
                    "amazon_quantity": amazon_quantity,
                    "amazon_price_per_item": amazon_price_per_item,
                    "amazon_received_per_item": amazon_received_per_item,
                    "rakuten_effective_cost_total": None,
                    "rakuten_effective_cost_per_item_selected": None,
                    "price_diff": None,
                    "price_diff_after_point": None,
                    "profit_per_item": None,
                    "profit_rate": None,
                }
            )
            continue

        # -------- 利益・ROI 計算 --------
        # 1SKUあたりの総利益
        profit_total = amazon_net_total - rak_total
        # 1個あたりに割った利益（デバッグ用途）
        profit_per_item = (
            profit_total / amazon_quantity if amazon_quantity > 0 else profit_total
        )

        # 「Amazon受取額 - 楽天原価」の差額（= profit_total と同じ）
        price_diff = profit_total

        # ROI倍率（1.0 = 100%）
        roi = profit_total / rak_total if rak_total > 0 else None

        info.update(
            {
                "amazon_quantity": amazon_quantity,
                "amazon_price_per_item": amazon_price_per_item,
                "amazon_received_per_item": amazon_received_per_item,
                "rakuten_effective_cost_total": rak_total,
                "rakuten_effective_cost_per_item_selected": rak_per_item,
                "price_diff": price_diff,
                "price_diff_after_point": price_diff,
                "profit_per_item": profit_per_item,
                "profit_rate": roi,
            }
        )

    return asins
