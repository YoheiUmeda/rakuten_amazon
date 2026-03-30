@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_copy_review_request.ps1"
exit /b %ERRORLEVEL%
