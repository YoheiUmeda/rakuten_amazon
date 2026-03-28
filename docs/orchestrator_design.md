# 開発フロー半自動化オーケストレーター 設計メモ

## 1. 目的

「実装 → テスト → レビュー → commit」の流れを半自動化し、
繰り返し作業の品質を OpenAI API で補助する。

完全自動化はしない。人間の判断を3箇所に挟むことで、誤実装・誤 push を防ぐ。

---

## 2. 役割分担

| 役割 | 担当 | やること |
|---|---|---|
| 実装・テスト | Claude Code / Human | コードを書き、pytest を通す |
| レビュー依頼生成 | `generate_review_request.py` | staged diff + テスト結果 → `review_request.json` を生成 |
| レビュー実行 | `orchestrator.py` + OpenAI API | `review_request.json` → `review_reply.md` を生成 |
| 承認判断 | Human | 各承認ポイントで Go/No-Go を判断 |

---

## 3. フロー概要

```
[Claude Code / Human] 実装・テスト（pytest 通過）
    ↓
git add（staged 状態にする）
    ↓
[承認ポイント①] Human が diff を確認
    ↓
generate_review_request.py → review_request.json 生成（dry-run で確認）
    ↓
[承認ポイント②] Human が review_request.json 内容を確認
    ↓
orchestrator.py → OpenAI API → review_reply.md 生成
    ↓
[承認ポイント③] Human が review_reply.md を確認 → commit/push
```

失敗時は fail-open: orchestrator / API が失敗しても開発は止めない。`review_reply.md` なしで commit を続行してよい。

---

## 4. 中間成果物

| ファイル | 作成者 | 内容 | git 管理 |
|---|---|---|---|
| `.ai/handoff/review_request.json` | `generate_review_request.py` | task / changed_files / git_diff / test_output / related_code | commit しない（.gitignore 済み）|
| `docs/review_reply.md` | `orchestrator.py` + OpenAI API | 事実・不明・懸念・推奨アクション | commit しない（.gitignore 済み）|

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

### 承認ポイント① — diff 確認
- 確認内容: `git diff --staged` が想定範囲内か、pytest が通過しているか
- チェック: pass_filter / fee / profit ロジックに触れていないか
- No-Go 時: 実装に戻って修正

### 承認ポイント② — review_request.json 確認（dry-run）
- 確認内容: changed_files / git_diff / test_output が正しく取れているか
- チェック: secrets が JSON に含まれていないか（redaction が機能しているか）
- No-Go 時: `--files` / `--related-code` を調整して再実行

### 承認ポイント③ — review_reply.md 確認 → commit/push
- 確認内容: 懸念・推奨アクションに未対応の重大な指摘がないか
- チェック: `git status` が clean か（review_request.json / review_reply.md が staged 外か）
- No-Go 時: 指摘を次タスクの open_questions に追記して commit、次サイクルへ
- fail-open: orchestrator / API 失敗時は review なしで commit を続行してよい

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

## 9. 実装済みコンポーネント

| ファイル | 役割 |
|---|---|
| `tools/ai_orchestrator/generate_review_request.py` | staged diff + テスト結果 → `review_request.json` 生成 CLI |
| `tools/ai_orchestrator/orchestrator.py` | `review_request.json` → OpenAI API → `review_reply.md` 生成 CLI |
| `tools/ai_orchestrator/openai_client.py` | OpenAI Responses API ラッパー |
| `tools/ai_orchestrator/redaction.py` | API 送信前の secrets マスク |
| `.ai/prompts/review_system.md` | レビュー用 system prompt |
| `.claude/commands/review-handoff.md` | Claude Code スラッシュコマンド（`/project:review-handoff`）|

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
