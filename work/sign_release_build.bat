@echo off
setlocal

if "%~1"=="" (
  echo Usage: %~nx0 ^<path-to-exe^>
  exit /b 2
)

set "SIGNTOOL=C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x86\signtool.exe"
set "CERT_THUMBPRINT=7AA8DE6FED8EEF034164A1EA4A0877A42CFE6337"

"%SIGNTOOL%" sign /fd SHA256 /sha1 %CERT_THUMBPRINT% "%~1"
if errorlevel 1 exit /b %errorlevel%

"%SIGNTOOL%" verify /pa /v "%~1"
