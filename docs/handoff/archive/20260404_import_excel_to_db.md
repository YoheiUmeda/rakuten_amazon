# import_excel_to_db — DB復旧スクリプト追加

commit: f189284
date: 2026-04-04
type: out-of-cycle（cycle_manager 管理外）
secrets_checked: true

## 非エンジニア向け要約
バッチ実行中にDBへの接続が切れてしまった場合でも、
出力されたExcelファイルを後からDBに投入できるスクリプトを追加しました。

## エンジニア向け要約
`scripts/import_excel_to_db.py` を新規追加。
openpyxl で Excel を読み込み、`PriceResult` 経由で `save_price_results()` に渡す。
`_validate_header_mapping()` を起動時に実行し、
`_JA_TO_KEY` の各列について `HEADER_MAP_JA[exporter_key] == ja_label` を検証。
ズレがあれば `ValueError` で即停止。

## 変更ファイル
- scripts/import_excel_to_db.py（new）
- tests/test_import_excel_to_db.py（new）: 正常系・異常系 2件

## テスト結果
13 passed（test_import_excel_to_db 2件 + test_triage 11件）

## 使い方
```
venv/Scripts/python scripts/import_excel_to_db.py output/<ファイル名>.xlsx
```

## 運用上の反省点
- 今回のバッチ実行で DB 接続障害（ConnectionTimeout）が確認された
- バッチ完了後に Excel は正常出力されており、このスクリプトで後から投入可能
- `_JA_TO_KEY` と `HEADER_MAP_JA` の重複定義は残存しているが、起動時チェックで整合を保証

## 次回確認ポイント
- DB接続復旧後、対象の出力Excelを指定して本スクリプトで再投入する（例: output/<ファイル名>.xlsx）
- excel_exporter.py の列名を変更した場合、`_IMPORT_FIELD_TO_EXPORTER_KEY` も合わせて更新すること

## 関連記録
- triage classification: task.md (task_id: 20260404-triage), commit 3a90380 / a1c3f67
