@echo off
title Library Management System
echo Launching Library Management System...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
pause
