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

## 障害対応チェックリスト

| 症状 | 確認箇所 |
|---|---|
| Amazon 価格 0件 | SP-API クォータ (`pricing_quota_suspected`) |
| FBA 手数料 0件 | SP-API クォータ (`fba_quota_suspected`) |
| 楽天 no_rakuten_hit | キャッシュ削除 → キーワード確認 |
| DB 保存失敗 | `DATABASE_URL` 環境変数の確認 |
