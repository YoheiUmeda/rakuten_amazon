# システム構成図 / アーキテクチャ

## レイヤー構成

```
[Frontend: React + TypeScript]
        ↕ REST API (HTTP)
[Backend: FastAPI (Python)]
        ↕ ORM (SQLAlchemy)
[Database: PostgreSQL]

[Batch: batch_runner.py]
        ↕
[Keepa API] → ASIN 候補
[Amazon SP-API] → 価格・FBA手数料
[楽天 Ichiba API] → 仕入れ価格
```

## 依存サービス

| サービス | 用途 | 制限 |
|---|---|---|
| Keepa API | ASIN 検索 | レート制限あり |
| Amazon SP-API (Pricing) | 価格取得 | クォータ制限あり |
| Amazon SP-API (FBA Fee) | 手数料見積もり | クォータ制限あり |
| 楽天 Ichiba API | 商品検索 | SLEEP_TIME 必須 |

## 未解決の構成課題
- バッチスケジューラ（現状: 手動実行）
- Docker 化（現状: ローカル実行のみ）
