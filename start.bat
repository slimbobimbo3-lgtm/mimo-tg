@echo off
title MiMo Telegram App
cd /d "%~dp0"

echo [*] Starting Kakadu VPN...
tasklist /FI "IMAGENAME eq Kakadu.exe" 2>NUL | find /I "Kakadu.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    start "" "C:\Program Files\Kakadu\Kakadu.exe"
    timeout /t 8 /nobreak >NUL
) else (
    echo [+] Kakadu already running
)

echo [*] Checking mimo serve...
tasklist /FI "WINDOWTITLE eq MimoServe" 2>NUL | find /I "cmd.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starting mimo serve...
    start "MimoServe" /MIN cmd /c "C:\Users\123\AppData\Roaming\npm\mimo.cmd serve --port 7860"
    timeout /t 5 /nobreak >NUL
) else (
    echo [+] mimo serve already running
)

echo [*] Starting server...
python server.py
