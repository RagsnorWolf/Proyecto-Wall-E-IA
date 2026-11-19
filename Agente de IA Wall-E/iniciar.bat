@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Todavia no esta instalado. Ejecuta primero instalar.bat
    pause
    exit /b 1
)

if not exist "config.json" copy /y config.ejemplo.json config.json >nul

title WALL-E - cabina local
echo.
echo Abriendo WALL-E en http://127.0.0.1:8765/
echo Ctrl+C para apagar el servidor.
echo.

".venv\Scripts\python.exe" server.py %*
if errorlevel 1 pause
