@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYW=.venv\Scripts\pythonw.exe"
set "PY=.venv\Scripts\python.exe"

if not exist "%PYW%" set "PYW=%PY%"

if not exist "%PY%" (
    echo Todavia no esta instalado. Ejecuta primero instalar.bat
    pause
    exit /b 1
)

if not exist "config.json" copy /y config.ejemplo.json config.json >nul

rem launcher.py levanta server.py sin ventana y abre el navegador solo.
start "" /B "%PYW%" launcher.py
exit /b 0
