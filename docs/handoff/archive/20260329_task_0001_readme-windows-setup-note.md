---
task_id: "0001"
title: "README ローカル起動手順に Windows 補足を追加"
slug: "readme-windows-setup-note"
status: done
approved_at: "2026-03-29T00:00:00+09:00"
version: 1
updated: 2026-03-30
secrets_checked: true
---

<!-- アーカイブ: docs/handoff/archive/20260329_task_0001_readme-windows-setup-note.md -->

## タスク
README.md のバックエンド起動手順（`source venv/bin/activate`）の下に、
Windows PowerShell 環境向けの補足コマンド `.\venv\Scripts\Activate.ps1` を1行追加する。

## 背景と目的
handoff MVP の運用テストを兼ねた最小変更。
Linux/Mac 向けの `source` コマンドのみ記載されており、
Windows PowerShell では `.\venv\Scripts\Activate.ps1` が正しいため補足する。

## 実施条件・制約
- README.md の該当箇所のみ変更する
- コードロジック・設定ファイルには触れない
- 変更は1〜2行以内にする

## raw evidence
diff: README.md line 26 に1行追加
  + # Windows PowerShell の場合: .\venv\Scripts\Activate.ps1

## 除外確認
- .env / APIキー / トークン: 未含有（確認済み）
