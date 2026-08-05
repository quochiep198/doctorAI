@echo off
title Doctor AI - Medical Assistant
echo ==============================================================
echo              DOCTOR AI - MEDICAL ASSISTANT RAG
echo ==============================================================
echo.
echo Launching Doctor AI web application...
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your PATH.
    echo Please install Python and try again.
    pause
    exit /b 1
)

:: Run the web application
python AIDoctor\backend\run_web.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application crashed or stopped with errors.
    pause
)
