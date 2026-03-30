# review_request.md の内容をクリップボードにコピーする
$path = Join-Path (Split-Path -Parent $PSScriptRoot) "docs\handoff\review_request.md"
if (-not (Test-Path $path)) {
    Write-Error "review_request.md が見つかりません: $path"
    exit 1
}
Get-Content $path -Raw | Set-Clipboard
Write-Host "[OK] クリップボードにコピーしました: $path"
