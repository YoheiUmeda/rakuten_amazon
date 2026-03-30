Get-Clipboard -Raw | Set-Content .\tmp_clipboard_check.txt -Encoding utf8
Write-Host "保存完了: tmp_clipboard_check.txt"
