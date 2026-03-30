# クリップボードの内容を review_reply.md に保存する
$path = Join-Path (Split-Path -Parent $PSScriptRoot) "docs\handoff\review_reply.md"
$content = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($content)) {
    Write-Error "クリップボードが空です"
    exit 1
}
[System.IO.File]::WriteAllText($path, $content, [System.Text.Encoding]::UTF8)
Write-Host "[OK] review_reply.md に保存しました: $path"
