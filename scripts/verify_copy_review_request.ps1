# Verify that review_request.md is correctly transferred to clipboard
$root = Split-Path -Parent $PSScriptRoot
$reviewRequestPath = Join-Path $root "docs\handoff\review_request.md"
$copyScript        = Join-Path $root "scripts\copy_review_request.ps1"
$tmpFile           = Join-Path $root "tmp_clipboard_check.txt"
$python            = Join-Path $root "venv\Scripts\python.exe"

# Check prerequisites
if (-not (Test-Path $python))     { Write-Error "python not found: $python"; exit 1 }
if (-not (Test-Path $copyScript)) { Write-Error "copy script not found: $copyScript"; exit 1 }

# Generate review_request.md
& $python -m tools.ai_orchestrator.fill_result --print-chat-prompt --review-request-output $reviewRequestPath
if ($LASTEXITCODE -ne 0) { Write-Error "fill_result failed"; exit 1 }

# Run copy_review_request.ps1 to load clipboard
& $copyScript
if ($LASTEXITCODE -ne 0) { Write-Error "copy_review_request failed"; exit 1 }

$clipText = Get-Clipboard -Raw
if ([string]::IsNullOrEmpty($clipText)) { Write-Error "clipboard is empty"; exit 1 }

# Save clipboard to tmp file (UTF-8 without BOM)
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($tmpFile, $clipText, $utf8NoBom)

# Normalize: remove BOM, unify CRLF/LF, strip trailing newlines only
function Normalize([string]$s) {
    $s = $s -replace [char]0xFEFF, ""  # remove BOM
    $s = $s -replace "`r`n", "`n"      # CRLF to LF
    return $s.TrimEnd("`n")            # trailing newlines only (preserve spaces/tabs)
}

$src  = Normalize (Get-Content $reviewRequestPath -Raw -Encoding utf8)
$dump = Normalize $clipText

if ($src -eq $dump) {
    Write-Host "[OK] match: clipboard matches review_request.md -- paste to ChatGPT now (Ctrl+V)"
    exit 0
} else {
    Write-Error "[NG] mismatch"
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
