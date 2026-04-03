# 運用設計 / Runbook

## バッチ手動実行

```bash
cd C:/Python/project/rakuten_amazon
python batch_runner.py
```

または FastAPI 経由:
```bash
curl -X POST http://localhost:8000/batch/run
```

## キャッシュ削除

楽天検索キャッシュ (`rakuten_cache.json`) に古いエントリがある場合:

```bash
# 特定 ASIN のエントリを削除（Python）
python -c "
import json, pathlib
p = pathlib.Path('rakuten_cache.json')
cache = json.loads(p.read_text())
keys_to_delete = [k for k in cache if 'B0F5BTJBJP' in k]
for k in keys_to_delete:
    del cache[k]
p.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
print(f'Deleted {len(keys_to_delete)} keys')
"
```

## 設計書更新パケット生成

```bash
# commit 前に実行
python -m tools.ai_orchestrator.generate_design_update_packet --staged

# dry-run 確認
python -m tools.ai_orchestrator.generate_design_update_packet --dry-run
```

## サーバー起動

```bash
uvicorn app.main_fastapi:app --reload
```

## レビューオーケストレーター

### 実行タイミング
実装後・テスト通過後・commit 前を基本とする。

### 基本フロー

**Step 1: staged 状態にする**
```bash
git add <変更ファイル>
```

**Step 2: dry-run で内容確認**
```bash
venv/Scripts/python -m tools.ai_orchestrator.generate_review_request \
  --task "タスクの説明" \
  --staged \
  --test-cmd "python -m pytest tests/ -v" \
  --run-tests \
  --dry-run
```
`related_code` が必要な場合のみ `--related-code file1.py` を追加（後述）。

**Step 3: review_request.json 保存**
```bash
venv/Scripts/python -m tools.ai_orchestrator.generate_review_request \
  --task "タスクの説明" \
  --staged \
  [--test-cmd "..." --run-tests] \
  [--related-code file1.py] \
  --output .ai/handoff/review_request.json
```

**Step 4: orchestrator 実行**
```bash
venv/Scripts/python -m tools.ai_orchestrator.orchestrator \
  --input .ai/handoff/review_request.json \
  --output docs/review_reply.md
```

**Step 5: review_reply.md を確認して commit**

---

### 一発実行（run_review.py）

Step 2〜4 を1コマンドに集約したショートカット。
fail-open: orchestrator 失敗時も `exit 0` で終了し、commit を止めない。

```bash
# dry-run（JSON保存なし、generate の出力だけ確認）
venv/Scripts/python -m tools.ai_orchestrator.run_review \
  --task "タスク説明" \
  --staged \
  --dry-run

# save-only（JSON保存して止まる、orchestrator はスキップ）
# ※ review_request.json が既存の場合は exit 1。上書きする場合のみ --overwrite を追加する。
venv/Scripts/python -m tools.ai_orchestrator.run_review \
  --task "タスク説明" \
  --staged \
  --save-only

# 全ステップ実行（OPENAI_API_KEY 必要）
venv/Scripts/python -m tools.ai_orchestrator.run_review \
  --task "タスク説明" \
  --staged \
  --test-cmd "python -m pytest tests/ -v" \
  --run-tests
```

| オプション | 挙動 |
|---|---|
| `--dry-run` | JSON 保存なし、orchestrator スキップ |
| `--save-only` | JSON 保存あり、orchestrator スキップ。既存ファイルがある場合は `--overwrite` も必要 |
| なし | JSON 保存あり、orchestrator まで全実行 |

失敗時は WARN を出して `exit 0`。`review_reply.md` なしで commit を続行してよい。

---

### 失敗時の扱い（fail-open — 開発は止めない）

| 失敗ケース | 対応 |
|---|---|
| `generate_review_request` が空 diff | `--files` で対象を明示指定して再試行。解決しなければスキップして commit |
| `orchestrator` 失敗（API エラー等） | `review_reply.md` なしで commit を続行。レビューなし commit は許容する |
| `test-cmd` 失敗 | `test_output` に失敗内容が含まれる。テスト修正後に再実行するか、内容を open_questions に転記して続行 |
| `OPENAI_API_KEY` 未設定 | `.env` を確認。なければ `--dry-run` で user content のみ確認して終了 |

---

### related_code 使用基準
- diff だけでは文脈が不足するときだけ使う（例: 変更関数の呼び出し元が重要な場合）
- 基本は 1〜2 ファイルまで。何でも追加しない（4000文字上限）
- diff を見て「これだけで意図が伝わる」と思えば related_code は不要

### Windows での test-cmd 推奨書式
- `python -m pytest tests/ -v`（venv 有効化済みの場合）
- またはフルパス: `C:/path/to/venv/Scripts/python.exe -m pytest tests/ -v`
- `venv/Scripts/python` 相対パスは cmd.exe で不安定なことがある

### 生成物の git 管理
- `.ai/handoff/review_request.json` — `.gitignore` 済み、commit しない
- `docs/review_reply.md` — `.gitignore` 済み、commit しない
- commit 前に `git status` で working tree が clean か確認

---

### 運用チェックリスト（commit 前）

```
[ ] git add 済みで staged 状態になっているか
[ ] --staged または --files で対象ファイルが正しく取れているか
[ ] test-cmd が OS 的に安全な書式か（Windows: フルパス推奨）
[ ] dry-run で changed_files / git_diff / test_output の内容が妥当か
[ ] related_code は本当に必要か（diff だけで足りないか）
[ ] review_request.json に secrets が含まれていないか
[ ] review_reply.md を確認したか（または API 失敗で skip したか）
[ ] git status が clean か（review_request.json / review_reply.md が staged に入っていないか）
```

---

## 障害対応チェックリスト

| 症状 | 確認箇所 |
|---|---|
| Amazon 価格 0件 | SP-API クォータ (`pricing_quota_suspected`) |
| FBA 手数料 0件 | SP-API クォータ (`fba_quota_suspected`) |
| 楽天 no_rakuten_hit | キャッシュ削除 → キーワード確認 |
| DB 保存失敗 | `DATABASE_URL` 環境変数の確認 |
