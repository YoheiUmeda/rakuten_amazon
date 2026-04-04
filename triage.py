# triage.py
"""
候補商品を deal_status に分類する。

deal_status の種類:
    profit_candidate    : 利益・ROI 閾値を通過した仕入候補（要目視確認）
    reject_profit       : 利益または ROI が閾値未満
    reject_no_rakuten   : 楽天に一致商品なし
    review_needed       : 楽天はヒットしたが全候補リジェクト等、要レビュー
    reject_no_data      : 手数料・楽天データが取得できず判定不能

next_action の種類:
    manual_review : 手動で確認・判断が必要
    skip          : 今サイクルはスキップ
"""
from __future__ import annotations

from typing import Any, Dict


def classify_deal(
    data: Dict[str, Any],
    min_profit: float,
    min_roi: float,
) -> Dict[str, Any]:
    """
    1 件分の ASIN データを受け取り、deal_status / block_reason / next_action を返す。

    - 呼び出し元は戻り値を data にマージするだけでよい。
    - data 自体は変更しない（副作用なし）。
    """
    reject_reason = data.get("reject_reason")
    profit_total  = data.get("profit_total")
    roi_percent   = data.get("roi_percent")

    # ── 楽天ヒットなし ──────────────────────────────────────────
    if reject_reason in ("no_rakuten_hit", "cached_no_hit"):
        return {
            "deal_status": "reject_no_rakuten",
            "block_reason": reject_reason,
            "next_action": "skip",
        }

    # ── 楽天はヒットしたが全候補リジェクト ──────────────────────
    if reject_reason == "all_rakuten_items_rejected":
        return {
            "deal_status": "review_needed",
            "block_reason": "all_rakuten_items_rejected",
            "next_action": "manual_review",
        }

    # ── 利益データあり ───────────────────────────────────────────
    if profit_total is not None and roi_percent is not None:
        if profit_total >= min_profit and roi_percent >= min_roi:
            return {
                "deal_status": "profit_candidate",
                "block_reason": None,
                "next_action": "manual_review",
            }
        return {
            "deal_status": "reject_profit",
            "block_reason": f"profit={profit_total:.0f} roi={roi_percent:.1f}%",
            "next_action": "skip",
        }

    # ── 手数料 or 楽天データが取れず判定不能 ────────────────────
    return {
        "deal_status": "reject_no_data",
        "block_reason": "missing_fee_or_rakuten",
        "next_action": "manual_review",
    }
