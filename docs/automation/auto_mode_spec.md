# 確認不要モード 仕様書 (Phase 1)

## 目的

Claude が実装→テスト→レビュー用ドキュメント生成までを1サイクルとして管理し、
人間が OK / NG を判断するだけで push まで進める構成の基盤を作る。
Phase 1 は「状態管理」「サイクル記録」「レビュー用ドキュメント生成」に絞る。

## 1サイクルの定義

最初に掲げた goal を達成することを 1サイクルとする。達成とは:
- 実装完了
- テスト pass（または skip 理由明示）
- 変更内容の要約
- 非エンジニアでも読めるレビュードキュメントの生成

まで揃い、人間が「push してよい / まだ直す」を判断できる状態になること。

## 1ループの流れ

```
[実装] → [テスト] → [コミット] → [レビュードキュメント生成]
  ↓ NG                               ↓ 人間確認
[修正指示] ←──────────────────── [OK / NG 判定]
  ↑ loop継続                          ↓ OK
                                   [push 候補]
```

## state 項目 (.ai/state/cycle_state.json)

| フィールド | 型 | 説明 |
|---|---|---|
| cycle_id | string | YYYYMMDD-HHMMSS |
| goal | string | サイクルの目的 |
| status | enum | in_progress / pending_review / done / stopped |
| loop_count | int | ループ回数 |
| stop_reason | string or null | 停止理由 |
| loops | array | ループ履歴 |

loops 各要素:

| フィールド | 型 | 説明 |
|---|---|---|
| loop_id | int | 1始まり連番 |
| timestamp | string | ISO 8601 |
| commit | string | git short hash |
| changed_files | array | 変更ファイル |
| test_result | enum | pass / fail / skip |
| summary | string | 1行要約 |

## OK / NG 判定の流れ

1. `review_summary` コマンドで `docs/handoff/review_summary.md` を生成
2. 人間がドキュメントを読んで判断
3. OK → `cycle_manager done` → push 候補
4. NG → `cycle_manager ng --reason "..."` → 修正ループへ

## stop 条件

### hard stop（自動停止）
- テスト連続失敗かつ原因特定不可
- 変更範囲が goal から逸脱
- secrets / 破壊的変更の疑い
- 同種失敗の繰り返し（改善見込みなし）
- 次の修正指示を具体化できない

### soft limit（警告のみ・停止せず）
- loop_count > 10 → WARNING を表示

## commit / rollback / push ポリシー

- 1ループごとに対象ファイルのみ明示コミット（`git add -A` 禁止）
- 生成物・一時ファイル・secrets はコミットしない
- rollback: `git reset --hard <前のhash>`（人間が実行）
- push: 人間が OK を判断した場合のみ手動実行

## safety rules

- secrets を含む diff は生成しない
- `.env` / APIキー / トークン / DB接続文字列は常に除外
- 変更範囲は goal に対して説明できる範囲に保つ
- 無関係なリファクタリング禁止

## Phase 1 CLI

```bash
# 新サイクル開始
python -m tools.ai_orchestrator.cycle_manager start --goal "XX を修正"

# ループ記録（実装後に呼ぶ）
python -m tools.ai_orchestrator.cycle_manager record \
  --commit abc1234 --files f1.py f2.py --test pass --summary "修正完了"

# レビュー提出（in_progress + loops>=1 が必要）
python -m tools.ai_orchestrator.cycle_manager submit

# レビュードキュメント生成 → docs/handoff/review_summary.md
python -m tools.ai_orchestrator.review_summary

# 人間が確認後: 承認
python -m tools.ai_orchestrator.cycle_manager approve

# 人間が確認後: 差し戻し（reason 必須、次ループへ）
python -m tools.ai_orchestrator.cycle_manager reject --reason "修正理由"

# state 確認
python -m tools.ai_orchestrator.cycle_manager status

# 後方互換（非推奨）
# done  → approve の alias
# ng    → deprecation warning 付きで旧挙動のまま残す（stop_reason も更新）
```

## loop_runner CLI（Phase 2 実装済み）

record → submit → review_summary を1コマンドで実行する。

```bash
# 新サイクル開始 + テスト実行（state 不在時は --goal 必須）
python -m tools.ai_orchestrator.loop_runner \
  --goal "XX を修正" \
  --test-cmd "venv/Scripts/python -m pytest tests/ -q --tb=short" \
  --files src/foo.py \
  --summary "修正完了"

# in_progress サイクル継続（--goal 省略可）
python -m tools.ai_orchestrator.loop_runner \
  --test-cmd "venv/Scripts/python -m pytest tests/ -q --tb=short" \
  --files src/foo.py \
  --summary "再修正完了"
```

動作:
- pre-flight: untracked を含む dirty check（`git status --porcelain`）
- pass → record → submit → review_summary 生成 → exit 0
- pass + `--auto-review` → 上記後に run_cycle_review を自動実行 → exit 0
- fail → record のみ → exit 1（submit しない・auto-review にも進まない）

```bash
# --auto-review: submit 後に run_cycle_review を自動実行
python -m tools.ai_orchestrator.loop_runner \
  --goal "XX を修正" \
  --test-cmd "venv/Scripts/python -m pytest tests/ -q --tb=short" \
  --files src/foo.py \
  --summary "修正完了" \
  --auto-review
```

## cycle_to_review_request CLI（Phase 2 実装済み）

pending_review 状態の cycle_state.json を orchestrator.py が読める review_request.json に変換する。

```bash
# pending_review のときのみ実行可能
python -m tools.ai_orchestrator.cycle_to_review_request \
  [--test-cmd "venv/Scripts/python -m pytest tests/ -q"] \
  [--output .ai/handoff/review_request.json]

# 続けて orchestrator で OpenAI レビューを実行
python -m tools.ai_orchestrator.orchestrator \
  --input .ai/handoff/review_request.json \
  --output docs/handoff/review_reply.md
```

制約:
- status が pending_review 以外（in_progress / done / stopped）→ exit 1
- goal が空 → exit 1
- 全ループの changed_files が空 → exit 1

## run_cycle_review CLI（Phase 2 接続拡張・実装済み）

pending_review 状態を受けて review_request.json 生成 → orchestrator 呼び出しを1コマンドで実行する。
loop_runner とは独立して動作する（loop_runner 実行後に手動で呼ぶ）。

```bash
# pending_review 後に実行
python -m tools.ai_orchestrator.run_cycle_review \
  [--test-cmd "venv/Scripts/python -m pytest tests/ -q"] \
  [--model gpt-4o-mini]

# orchestrator をスキップして review_request.json 確認のみ
python -m tools.ai_orchestrator.run_cycle_review --dry-run
```

fail 方針:
- OPENAI_API_KEY 未設定 → review_request.json 生成のみで exit 0（スキップ）
- --dry-run → review_request.json 生成のみで exit 0（スキップ）
- cycle_to_review_request 失敗 → exit 1
- orchestrator 失敗（APIエラー等）→ exit 1

成功ログ:
- `[OK] review_request.json 生成完了` ← Step 1 完了
- `[OK] review_reply.md 生成完了`     ← Step 2 完了（API 呼び出し含む）

## 承認件数の運用メモ

- `git push` の手動承認は ask ルール上の正常動作（意図的）
- `cd C:/... && git ...` 形式は auto-allow パターンに不一致となり avoidable な承認が発生するため使わない
- Approve の通常実行は `apply_review --auto-approve` を基本とする（`cycle_manager approve` の手動実行は不要）
- `apply_review --auto-approve --auto-archive` で task.md の done化・archive移動まで自動化できる（--auto-approve 成功時のみ）

## Phase 3 以降（未実装）

- 修正ループの自動継続
- loop_runner → run_cycle_review の自動連結（1コマンド実行）
- clipboard 経路の廃止
- BAT スクリプトによるワンクリック起動
