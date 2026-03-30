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
- ≤1 file changed, ≤10 lines diff
- No risk to fee / pass_filter / secrets / credential handling
- Existing tests clearly not broken

Do not use /plan.
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

## Compact instructions
When compacting, preserve these constraints:
- fee=None must never be treated as 0
- pass_filter must stay on the safe side
- All requests.get calls must include timeout=(10, 30)
- No secrets in commits
