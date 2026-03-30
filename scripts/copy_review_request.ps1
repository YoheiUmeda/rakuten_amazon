# review_request.md の内容をクリップボードにコピーする
$path = Join-Path (Split-Path -Parent $PSScriptRoot) "docs\handoff\review_request.md"
if (-not (Test-Path $path)) {
    Write-Error "review_request.md が見つかりません: $path"
    exit 1
}
$info = Get-Item $path
Write-Host "更新時刻: $($info.LastWriteTime)"
Get-Content $path -TotalCount 5 -Encoding utf8 | ForEach-Object { Write-Host $_ }
Write-Host "---"
Get-Content $path -Raw -Encoding utf8 | Set-Clipboard
Write-Host "[OK] クリップボードにコピーしました: $path"
