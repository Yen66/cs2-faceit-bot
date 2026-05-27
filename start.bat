@echo off
chcp 65001 >nul
title CS2 Faceit Bot

echo.
echo  ================================
echo   CS2 Faceit Stats Bot
echo  ================================
echo.

:: Check .env exists
if not exist ".env" (
    echo  [!] Файл .env не найден!
    echo.
    echo  Создаю .env из примера...
    copy ".env.example" ".env" >nul
    echo.
    echo  [!] Открой файл .env и заполни:
    echo      BOT_TOKEN=твой_токен_от_BotFather
    echo      FACEIT_API_KEY=твой_ключ_от_Faceit
    echo.
    start notepad ".env"
    echo  После заполнения закрой блокнот и запусти start.bat снова.
    pause
    exit /b
)

:: Install deps if needed
echo  [1/2] Проверяю зависимости...
pip show aiogram >nul 2>&1
if errorlevel 1 (
    echo  Устанавливаю пакеты...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  [!] Ошибка установки. Убедись что Python установлен.
        pause
        exit /b
    )
)

echo  [2/2] Запускаю бота...
echo.
echo  Бот работает. Ctrl+C для остановки.
echo.

python bot.py

echo.
echo  Бот остановлен.
pause
