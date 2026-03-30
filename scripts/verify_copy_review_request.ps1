# review_request.md が正しくクリップボードへ載るかを検証する
$root = Split-Path -Parent $PSScriptRoot
$reviewRequestPath = Join-Path $root "docs\handoff\review_request.md"
$copyScript        = Join-Path $root "scripts\copy_review_request.ps1"
$tmpFile           = Join-Path $root "tmp_clipboard_check.txt"
$python            = Join-Path $root "venv\Scripts\python.exe"

# 存在チェック
if (-not (Test-Path $python))     { Write-Error "python が見つかりません: $python"; exit 1 }
if (-not (Test-Path $copyScript)) { Write-Error "コピースクリプトが見つかりません: $copyScript"; exit 1 }

# review_request.md を生成
& $python -m tools.ai_orchestrator.fill_result `
    --print-chat-prompt `
    --review-request-output $reviewRequestPath
if ($LASTEXITCODE -ne 0) { Write-Error "fill_result 失敗"; exit 1 }

# copy_review_request.ps1 を実行（クリップボードへ）
& $copyScript
if ($LASTEXITCODE -ne 0) { Write-Error "copy_review_request 失敗"; exit 1 }

# クリップボード → tmp_clipboard_check.txt（UTF-8 BOMなし）
$clipText = Get-Clipboard -Raw
[System.IO.File]::WriteAllText($tmpFile, $clipText, [System.Text.Encoding]::UTF8)

# 比較（BOM・CRLF/LF・末尾改行を正規化）
function Normalize([string]$s) {
    $s = $s -replace "`u{FEFF}", ""       # BOM除去
    $s = $s -replace "`r`n", "`n"         # CRLF → LF
    return $s.TrimEnd()
}

$src  = Normalize (Get-Content $reviewRequestPath -Raw -Encoding utf8)
$dump = Normalize $clipText

if ($src -eq $dump) {
    Write-Host "[OK] 実質一致: クリップボード内容は review_request.md と一致しています"
    exit 0
} else {
    Write-Error "[NG] 実質不一致"
    Write-Host "src length : $($src.Length)"
    Write-Host "dump length: $($dump.Length)"
    $minLen = [Math]::Min($src.Length, $dump.Length)
    $diffIdx = -1
    for ($i = 0; $i -lt $minLen; $i++) {
        if ($src[$i] -ne $dump[$i]) { $diffIdx = $i; break }
    }
    if ($diffIdx -ge 0) {
        Write-Host "first diff at index: $diffIdx"
        $start = [Math]::Max(0, $diffIdx - 20)
        $end   = [Math]::Min($minLen, $diffIdx + 40)
        Write-Host "src  excerpt: $($src.Substring($start, $end - $start))"
        Write-Host "dump excerpt: $($dump.Substring($start, $end - $start))"
    }
    exit 1
}
