@echo off
title Build LMS Pro Standalone Executable
echo ========================================================
echo Compiling Library Management System to Windows .exe
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" build_exe.py
) else (
    python build_exe.py
)
pause
