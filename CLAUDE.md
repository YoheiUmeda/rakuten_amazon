# CLAUDE.md

## Project overview
This project is an Amazon/Rakuten arbitrage research tool.

Backend: FastAPI
Frontend: React + TypeScript
Database: PostgreSQL

Main goals:
- Fetch candidate ASINs from Keepa
- Get Amazon prices and fees
- Search Rakuten items
- Calculate profit and ROI
- Save snapshots
- Show candidates in UI

## Working rules
- Before starting a task from docs/handoff/task.md, confirm status: approved
- One session, one theme
- Run /clear between themes; run /compact when context grows long (Pro/Max: check /stats)
- First, inspect current state only
- Always specify target files
- Show diff plan before editing
- After implementation, run pytest
- Start a new thread after one theme is closed
- Use only necessary logs/snippets
- Extra usage is the last resort

## Lightweight flow (skip plan mode)
All of the following must hold:
- 1 file only, ≤10 lines diff
- No risk to fee / pass_filter / secrets / credential handling
- Existing tests clearly not broken

Do not use /plan.
No /plan for run-only/review-only/execution-only tasks either. If Plan Mode auto-starts, exit immediately and continue without saving.
Do not create or update a plan file.
Implement directly.

Report in 3 lines only:
Changed: <file>
Tests: pass/skip
Commit: <hash>

## Flow selection
Use /lf when ALL hold:
- 1 file only, ≤10 lines diff
- Doc-only or equivalent small fix
- No risk to fee / pass_filter / secrets / credential handling
- Clean session (after /clear, no active plan file)

Use normal flow when any applies:
- Multiple files or broad impact
- Design decisions required
- Safety conditions touched (fee / pass_filter / secrets / credentials)

Use /plan only for complex/high-risk/multi-step changes; normal flow is: inspect → diff → implement.

For run-only / review-only / execution-only tasks (status check, start/stop/approve, loop_runner), never use /plan. If Plan Mode auto-starts, exit immediately without saving.

## Safety rules
- Never commit secrets
- Never edit .env directly without explicit instruction
- Ask before changing profit / fee / pass_filter logic
- Ask before changing credential handling
- Prefer minimal diffs
- Do not touch unused files unless explicitly asked

## Important files
- amazon_fee.py
- price_calculation.py
- batch_runner.py
- main.py
- keepa_client.py
- get_keepa_prices.py
- rakuten_client.py
- spapi_client.py
- app/schemas.py
- app/db.py
- app/repository.py
- app/main_fastapi.py

## Notes
- fee=None must never be treated as 0
- pass_filter must stay on the safe side
- All requests.get calls must include timeout=(10, 30); never add a call without it
- RAKUTEN_SLEEP_TIME is a float (e.g. 0.2); always read with float(), never int()
- search_rakuten_product_api and search_ichiba_from_product have no retry logic; 429 is absorbed by except Exception

## AI Orchestrator (run_review)

### 標準実行パターン

```bash
# 変更内容を確認してから進める（review_request.json を保存して止まる）
venv/Scripts/python -m tools.ai_orchestrator.run_review \
  --task "タスク説明" --staged --save-only

# full-step（API 呼び出し・review_reply.md 生成）
venv/Scripts/python -m tools.ai_orchestrator.run_review \
  --task "タスク説明" --staged \
  --test-cmd "venv/Scripts/python -m pytest tests/ -q --tb=short" --run-tests

# 実行履歴を確認
venv/Scripts/python -m tools.ai_orchestrator.run_review --history-tail 10
```

### モデル方針（〜2026-04-13 頃まで）

- デフォルト: `gpt-4o-mini`（`OPENAI_MODEL` 未設定で自動適用）
- 変更する場合: `--model gpt-4o` または `.env` に `OPENAI_MODEL=gpt-4o`

### やってはいけないこと

- 無関係なファイルを staged に混ぜたまま full-step を実行しない
- 巨大差分（数百行以上）でいきなり full-step を回さない（save-only で確認してから）
- `--test-cmd` の引数に secrets を含めない

## Handoff result
- After task execution, fill docs/handoff/result.md (conclusion / diff / test output) before closing
- result.md is gitignored; copy from docs/handoff/result.md.template if it does not exist

## Review flow (正式手順)
```
# 1. review_request 生成・verify・クリップボード載せ
scripts\run_verify_copy_review_request.bat

# 2. ChatGPT に貼り付け (Ctrl+V) → 返答をコピー

# 3. review_reply.md に保存
scripts\paste_review_reply.ps1

# 4. result.md 更新
venv/Scripts/python -m tools.ai_orchestrator.apply_review --dry-run
venv/Scripts/python -m tools.ai_orchestrator.apply_review

# 5. Approve なら task.md を done にして archive へ（手動）
```

## クリップボード検証スクリプト

`review_request.md` が正しくクリップボードへ転送されるかを検証する。

```
scripts\run_verify_copy_review_request.bat
```

- `fill_result.py --print-chat-prompt` で `docs/handoff/review_request.md` を生成
- `copy_review_request.ps1` でクリップボードへ載せ、`tmp_clipboard_check.txt` と比較
- BOM・CRLF/LF・末尾改行を無視して実質一致 / 不一致を判定
- 成功: exit 0、失敗: exit 1（差分情報を表示）

## Auto-allow scope (ai_orchestrator / automation work)

Pre-approved via .claude/settings.local.json (no per-call confirmation):
- Edit/Write: `tools/ai_orchestrator/**`, `tests/test_cycle_manager.py`,
  `tests/test_loop_runner.py`, `tests/test_cycle_to_review_request.py`,
  `tests/test_run_cycle_review.py`, `docs/automation/auto_mode_spec.md`, `CLAUDE.md`
- Bash (pytest): `venv/Scripts/python -m pytest tests/test_cycle_manager* *` など
- Bash (CLI): `venv/Scripts/python -m tools.ai_orchestrator.*`
- Bash (git): `git add` (上記パス限定), `git log/status/diff`
- Bash (safe commit): `venv/Scripts/python -m tools.ai_orchestrator.safe_commit *`

Important files (fee/pass_filter/credentials) は従来通り都度承認。
git commit (raw) は auto-allow 対象外。safe_commit を使うこと。
git push は都度承認。

### 実行コマンド正規化ルール（auto-allow を確実に効かせるため）
- `cd C:/... &&` を Bash コマンド先頭に付けない（repo root で自動実行）
- `&&` で複数コマンドを結合しない（1アクション = 1コマンド）
- `git add` と `git status` は別コマンドで実行する
- `cycle_manager start` と `loop_runner` は別コマンドで実行する
- `git add` は原則1ファイルずつ実行し、複数ファイルを1コマンドにまとめない
- settings 検証や件数確認に `python -c` や `&&` 連結を使わず、`permissions_audit` を使う

### settings 変更後の再測定ルール
- settings.local.json を変更した後、同じセッション内で新しい allow 対象コマンドの承認測定をしない
- settings 変更後の承認再測定は Claude Code 再起動後に行う

## permissions_audit (settings 検証・集計)
```bash
# JSON 妥当性確認
venv/Scripts/python -m tools.ai_orchestrator.permissions_audit validate-settings

# allow/ask/deny 件数・defaultMode 表示
venv/Scripts/python -m tools.ai_orchestrator.permissions_audit summarize-settings
```

## safe_commit (安全柵付きコミット)
```bash
venv/Scripts/python -m tools.ai_orchestrator.safe_commit -m "feat: ..."
```
abort 条件: staged なし / Important files 混入 / secrets ファイル名 / message 空
scope 外ファイルは WARNING のみ（abort しない）

## Compact instructions
When compacting, preserve these constraints:
- fee=None must never be treated as 0
- pass_filter must stay on the safe side
- All requests.get calls must include timeout=(10, 30)
- No secrets in commits
