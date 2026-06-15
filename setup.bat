@echo off
chcp 65001 >NUL
title MiMo Code — Установка
echo.
echo  ==========================================
echo   MiMo Code — Telegram Mini App
echo   Установка на ваш ПК
echo  ==========================================
echo.

:: Check Python
python --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python не установлен. Скачайте с https://python.org
    echo     При установке поставьте галочку "Add Python to PATH"
    pause
    exit /b 1
)
echo [+] Python найден

:: Check Node.js (for mimo CLI)
node --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Node.js не установлен. Скачайте с https://nodejs.org
    pause
    exit /b 1
)
echo [+] Node.js найден

:: Install MiMo CLI
echo.
echo [*] Устанавливаю MiMo CLI...
call npm install -g mimocode
if %ERRORLEVEL% NEQ 0 (
    echo [!] Ошибка установки MiMo CLI
    pause
    exit /b 1
)
echo [+] MiMo CLI установлен

:: Install Python dependencies
echo.
echo [*] Устанавливаю Python зависимости...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [!] Ошибка установки зависимостей
    pause
    exit /b 1
)
echo [+] Зависимости установлены

:: Create .env if not exists
if not exist ".env" (
    echo.
    echo [*] Создаю .env файл...
    echo BOT_TOKEN= > .env
    echo MIMO_URL=http://127.0.0.1:7860 >> .env
    echo NGROK_AUTHTOKEN= >> .env
    echo [!] Отредактируйте .env файл перед запуском
)

:: Create uploads dir
if not exist "uploads" mkdir uploads

echo.
echo  ==========================================
echo   Установка завершена!
echo  ==========================================
echo.
echo  Следующие шаги:
echo  1. Отредактируйте .env файл
echo     - BOT_TOKEN: токен от @BotFather
echo     - NGROK_AUTHTOKEN: токен с ngrok.com (опционально)
echo.
echo  2. Запустите start.bat
echo.
echo  3. Напишите боту /start в Telegram
echo.
pause
