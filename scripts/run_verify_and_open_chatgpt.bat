@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_copy_review_request.ps1"
set VERIFY_EXIT=%ERRORLEVEL%
if %VERIFY_EXIT% equ 0 (
    start "" "https://chatgpt.com"
)
exit /b %VERIFY_EXIT%
