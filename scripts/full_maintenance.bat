@echo off
setlocal
call scripts\cleanup_python.bat
if errorlevel 1 exit /b 1
call scripts\cleanup_frontend.bat
if errorlevel 1 exit /b 1
call scripts\verify_project.bat
