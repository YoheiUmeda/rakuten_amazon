# AmazonPriceSearch

## 概要

Keepa から Amazon 商品候補を取得し、楽天市場との価格差・利益率を計算して仕入れ候補を洗い出すリサーチツール。

- バックエンド: Python (FastAPI)
- フロントエンド: React + TypeScript
- データベース: PostgreSQL（省略可）

## 主な機能

- Keepa Product Finder から ASIN リストを取得
- Amazon SP-API で価格・FBA 手数料を取得
- 楽天市場 API で最安値を検索
- 利益・ROI を計算してフィルタリング
- 結果を Excel 出力 / DB 保存 / ダッシュボード表示

## ローカル起動方法

### バックエンド（FastAPI）

```bash
cp .env.example .env   # 各項目を設定
source venv/bin/activate
uvicorn app.main_fastapi:app --reload
```

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

### DB なしで動かす場合

`DATABASE_URL` を `.env` に設定しなければ DB 保存をスキップして動作する。Excel 出力のみ使う場合は設定不要。

## 環境変数

設定ファイルは `.env.example` を参照。主なキー:

| キー | 必須 | 説明 |
|---|---|---|
| `KEEPA_API_KEY` | 必須 | Keepa API キー |
| `RAKUTEN_API_ID` | 必須 | 楽天アプリ ID |
| `REFRESH_TOKEN` 他 | 必須 | Amazon SP-API 認証情報 |
| `DATABASE_URL` | 省略可 | PostgreSQL 接続文字列 |

## 注意事項

- `.env` をコミットしない
- 利益計算・手数料ロジックの変更は慎重に行う
- 詳細な設計ルール・作業ルールは `CLAUDE.md` を参照
