@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Todavia no esta instalado. Ejecuta primero instalar.bat
    pause
    exit /b 1
)

if not exist "config.json" (
    copy /y config.ejemplo.json config.json >nul
)

if "%WALLE_API_KEY%"=="" (
    echo [AVISO] La variable WALLE_API_KEY esta vacia: no se podra llamar al modelo.
    echo         Definila en esta ventana antes de seguir:
    echo             set WALLE_API_KEY=tu-clave
    echo.
    echo         Tambien podes usar solo el reflejo entrenado, sin modelo:
    echo             .venv\Scripts\python.exe main.py --sin-llm --reflejo 300
    echo.
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
