# dev_orchestrator MVP

## 概要

`scripts/dev_orchestrator.py` はタスク JSON を読み込み、pytest 実行 → git add/commit/push を半自動化するスクリプトです。

## 使い方

```bash
# 状態確認 + pytest だけ（git 操作なし）
python scripts/dev_orchestrator.py --task orchestrator_tasks/example_task.json --mode dry-run

# pytest PASS したら対象ファイルだけ add/commit（push なし）
python scripts/dev_orchestrator.py --task orchestrator_tasks/example_task.json --mode commit

# pytest PASS + 対象外の変更なし → add/commit/push
python scripts/dev_orchestrator.py --task orchestrator_tasks/example_task.json --mode push
```

## タスク JSON フォーマット

```json
{
  "goal": "変更のゴール説明（表示用）",
  "targets": ["app/schemas.py", "app/models.py"],
  "pytest_commands": [],
  "commit_message": "docs: clarify profit_per_item meaning",
  "allow_push": true
}
```

`pytest_commands` は空配列でも可（docs 系など pytest 不要なタスク）。
pytest が必要な場合は対象を絞って指定する:
```json
"pytest_commands": [".\\venv\\Scripts\\pytest.exe tests\\test_price_calculation.py -v --tb=short"]
```

| フィールド | 説明 |
|---|---|
| `goal` | 表示用の説明文 |
| `targets` | add/commit 対象ファイル（リポジトリルートからの相対パス） |
| `pytest_commands` | PowerShell で順番に実行するコマンド列 |
| `commit_message` | git commit に使うメッセージ |
| `allow_push` | `push` モードを許可するか（false なら push モードでも中断） |

## 動作仕様

| mode | pytest | git add/commit | git push |
|---|---|---|---|
| `dry-run` | 実行 | しない | しない |
| `commit` | 実行、FAIL で中断 | targets のみ | しない |
| `push` | 実行、FAIL で中断 | targets のみ | targets 外の変更がなく `allow_push=true` の場合のみ |
