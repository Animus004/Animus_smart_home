@echo off
title Animus Smart Room Intelligence Daemon
echo =====================================================
echo    Starting Animus Smart Room Intelligence Daemon   
echo =====================================================

echo.
echo [1/3] Connecting ADB targets...
adb connect 192.168.1.5:5555
adb connect 192.168.1.11:5555

echo.
echo [2/3] Starting Animus Daemon...
start /B python server/music_daemon/main.py

timeout /t 3 /nobreak > nul

echo.
echo [3/3] Launching Animus Interactive Console...
python animus_console.py
pause
