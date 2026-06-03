@echo off
title Jarvis Starter
echo Activating envJarvis virtual environment...
call "%~dp0envJarvis\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate envJarvis virtual environment.
    echo Please make sure the folder "envJarvis" exists in this directory.
    pause
    exit /b %errorlevel%
)
echo Starting Jarvis App...
python run.py
pause
