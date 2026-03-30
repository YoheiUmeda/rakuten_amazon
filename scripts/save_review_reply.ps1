# クリップボードの ChatGPT レビュー結果を review_reply.md に保存して commit する
$root = Split-Path -Parent $PSScriptRoot
$path = Join-Path $root "docs\handoff\review_reply.md"

$content = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($content)) {
    Write-Error "クリップボードが空です"
    exit 1
}

# 形式チェック
foreach ($h in @("## Decision", "## Issues", "## Required changes")) {
    if ($content -notmatch [regex]::Escape($h)) {
        Write-Error "形式チェック失敗: '$h' が見つかりません"
        exit 1
    }
}

[System.IO.File]::WriteAllText($path, $content, [System.Text.Encoding]::UTF8)
Write-Host "[OK] review_reply.md に保存しました"

Set-Location $root
git add "docs/handoff/review_reply.md"
git commit -m "docs: review_reply.md を更新（ChatGPT レビュー結果）"
Write-Host "[OK] commit 完了"
