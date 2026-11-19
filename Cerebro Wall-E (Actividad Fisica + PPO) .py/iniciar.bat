@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Todavia no esta instalado. Ejecuta primero instalar.bat
    pause
    exit /b 1
)

if not exist "modelo\politica.json" (
    echo No hay politica entrenada en modelo\politica.json
    echo.
    echo Entrena primero:
    echo   entrenar.bat
    pause
    exit /b 1
)

".venv\Scripts\python.exe" evaluar.py --ventana %*
if errorlevel 1 pause
