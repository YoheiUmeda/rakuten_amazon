# 変更履歴 / Architecture Decision Records (ADR)

## ADR-001: escape_rakuten_keyword のバイト計算を URL-encoded ベースに修正 (2026-03)

**問題:** 蓄積ループが raw UTF-8 バイトで計算するが、最終チェックが URLエンコード後バイトで判定するため、日本語タイトルで 3倍の差が生じて ASIN fallback が多発していた。

**決定:** `token_bytes = len(urllib.parse.quote(token, safe='').encode('utf-8')) + 3`

**理由:** 判定と蓄積の基準を URLエンコード後バイトに統一する。

---

## ADR-002: prefilter.py の戻り値をタプル化 (2026-03)

**問題:** prefilter が除外理由を捨てていたため、何件がどの理由で除外されたか追跡できなかった。

**決定:** `(filtered, excluded)` タプルで返す。`excluded` に reject_reason を記録。

---

## ADR-003: 設計書更新フローの導入 (2026-03)

**問題:** コード変更が設計書に反映されないまま進むリスク。

**決定:** commit 前に `generate_design_update_packet.py` を実行し、更新候補を可視化する。当面はローカル `docs/` を正本として管理。
