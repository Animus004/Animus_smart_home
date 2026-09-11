@echo off
title Animus Smart Room Intelligence Daemon
echo =====================================================
echo    Starting Animus Smart Room Intelligence Daemon   
echo =====================================================

echo.
echo [1/3] Auto-discovering hardware & connecting ADB targets...
python scripts/discover_and_connect_adb.py

echo.
echo [2/3] Starting Animus Daemon...
start /B python server/music_daemon/main.py

timeout /t 5 /nobreak > nul

echo.
echo [3/3] Launching Animus Interactive Console...
python animus_console.py
pause
