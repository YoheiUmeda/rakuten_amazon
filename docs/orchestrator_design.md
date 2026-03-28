# 開発フロー半自動化オーケストレーター 設計メモ

## 1. 目的

「タスク要件 → プロンプト生成 → Claude Code 実行 → レビュー → commit/push」の流れを
ChatGPT API と Claude Code で分担し、繰り返し作業を半自動化する。

完全自動化はしない。人間の判断を3箇所に挟むことで、誤実装・誤push を防ぐ。

---

## 2. 役割分担

| 役割 | 担当 | やること |
|---|---|---|
| プロンプト生成 | ChatGPT API | task_request.md → claude_prompt.md を生成 |
| 実装・テスト | Claude Code | claude_prompt.md を受け取り diff を出力 |
| レビュー観察 | ChatGPT API | run_log.md + diff → review_checklist.md を生成 |
| 実行・確認 | Human | 各承認ポイントで Go/No-Go を判断 |

---

## 3. フロー概要

```
[Human] task_request.md を書く
    ↓
[ChatGPT API] → claude_prompt.md 生成
    ↓
[承認ポイント①] Human が claude_prompt.md を確認・修正
    ↓
[Claude Code] プロンプトを実行 → diff + run_log.md を出力
    ↓
[承認ポイント②] Human が diff を確認（pytest 通過前提）
    ↓
[ChatGPT API] run_log.md + diff → review_checklist.md 生成
    ↓
[承認ポイント③] Human が review_checklist.md を確認
    ↓
[script] generate_design_update_packet.py 実行 → design_update_packet.md 生成
    ↓
[承認ポイント④] Human が design_update_packet.md を確認 → commit/push
```

---

## 4. 中間成果物

| ファイル | 作成者 | 内容 |
|---|---|---|
| `task_request.md` | Human | タスク内容・背景・制約を書く入力ファイル |
| `claude_prompt.md` | ChatGPT API | Claude Code に渡す実行プロンプト |
| `run_log.md` | Claude Code | 実行ログ・diff・テスト結果の全文 |
| `review_checklist.md` | ChatGPT API | レビュー観点と判定結果 |
| `design_update_packet.md` | script | 更新対象設計書・更新理由・確認チェック項目 |

---

## 5. OpenAI 入力ポリシー（raw evidence 原則）

### 渡すもの
- diff 全文（省略・要約なし）
- エラー全文（トレースバック含む）
- 関連コードの断片（該当関数・クラス全体）
- pytest 出力全文
- run_log.md の関連部分（必要なら全文）

### 渡さないもの
- `.env` ファイルの内容
- APIキー・トークン・パスワード
- DB接続文字列

### 要約禁止の理由
「要約だけ渡す」と精度が落ちる。OpenAI が判断に使えるのは渡した事実のみ。
事実を欠いたプロンプトは、欠落を仮定で埋めた回答を生む。

---

## 6. ChatGPT API プロンプト設計（同調バイアス防止）

### system prompt 方針
- 「ユーザーの仮説に同意するな」を明示する
- 「証拠がない推測は『不明』と答えよ」を明示する
- 「最小変更を優先せよ」を明示する

### system prompt 例（プロンプト生成時）

```
あなたはコードレビュアーです。以下のルールを守ってください。

- ユーザーの仮説や方針に対して、証拠がなければ同意しない
- 推測・仮定は必ず「推測:」と前置きして区別する
- 確認済みの事実のみ「事実:」と前置きして提示する
- 推奨する変更は最小限にする。ロジック変更が不要なら提案しない
- pass_filter / fee / profit に関わる変更は必ず警告を出す
```

### 回答フォーマット指定例（レビュー時）

```
以下の形式で回答してください：

## 事実（ログ・diff から確認できること）
- ...

## 不明（ログに出ていないこと）
- ...

## 懸念（変更が及ぼしうるリスク）
- ...

## 推奨アクション
- ...
```

---

## 7. 人間承認ポイント詳細

### 承認ポイント① — プロンプト承認
- 確認内容: claude_prompt.md がタスクの意図と一致しているか
- チェック: スコープ外の変更を指示していないか
- No-Go 時: task_request.md を修正して再生成

### 承認ポイント② — diff 承認
- 確認内容: diff が想定範囲内か、pytest が通過しているか
- チェック: pass_filter / fee / profit ロジックに触れていないか
- No-Go 時: run_log.md を ChatGPT API に渡してプロンプト修正

### 承認ポイント③ — commit/push 承認
- 確認内容: review_checklist.md に未解決の懸念がないか
- チェック: シークレットが diff に含まれていないか
- No-Go 時: 懸念を task_request.md に追記して次サイクルへ

---

## 8. secrets 除外境界

OpenAI API に送信する前に以下を必ず除外する：

```
除外対象:
  - .env の全行
  - RAKUTEN_APP_ID, KEEPA_API_KEY, DATABASE_URL など
  - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  - SP-API の refresh_token / client_secret

除外方法（手動 or スクリプト）:
  - diff に secrets が含まれていないか grep で確認してから送信
  - run_log.md に環境変数の値が出力されていないか確認
```

---

## 9. MVP 実装スコープ（将来参考）

このメモは設計のみ。実装する場合の最小構成：

1. `orchestrator.py` — ChatGPT API 呼び出し + ファイル読み書き
2. `docs/prompts/system_prompt_generate.txt` — プロンプト生成用 system prompt
3. `docs/prompts/system_prompt_review.txt` — レビュー用 system prompt

実装は別セッションで行う。

---

## 11. 設計書正本の運用方針

- **正本**: Google ドキュメント（将来）
- **当面**: ローカル `docs/` ディレクトリで管理
- **移行トリガー**: チームレビューが必要になった時点
- **ローカル管理ルール**: `docs/spec_index.md` で設計書一覧・状態を管理

---

## 10. 参考: CLAUDE.md との関係

本設計は CLAUDE.md の以下ルールと整合している：

- "Ask before changing profit / fee / pass_filter logic" → 承認ポイント②で明示チェック
- "Prefer minimal diffs" → system prompt に最小変更優先を指定
- "Never commit secrets" → 承認ポイント③で diff チェック
