# Save clipboard content to review_reply.md
$path = Join-Path (Split-Path -Parent $PSScriptRoot) "docs\handoff\review_reply.md"
$content = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($content)) {
    Write-Error "clipboard is empty"
    exit 1
}
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
Write-Host "[OK] saved to review_reply.md: $path"
