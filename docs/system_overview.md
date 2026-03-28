# システム概要

## 目的
Amazon/楽天間の裁定取引候補を自動発見し、利益・ROI を可視化する。

## 主要コンポーネント

| コンポーネント | 役割 |
|---|---|
| Keepa API | 候補 ASIN の取得 |
| Amazon SP-API | 現在価格・FBA手数料の取得 |
| 楽天 Ichiba API | 仕入れ価格候補の取得 |
| FastAPI (backend) | 検索・集計 API の提供 |
| React (frontend) | 価格差ダッシュボードの表示 |
| PostgreSQL | 価格スナップショットの永続化 |

## スコープ外（MVP）
- 注文・購入の自動化
- 在庫管理
