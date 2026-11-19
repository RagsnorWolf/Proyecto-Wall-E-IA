@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Todavia no esta instalado. Ejecuta primero instalar.bat
    pause
    exit /b 1
)

".venv\Scripts\python.exe" entrenar_ppo.py %*
echo.
echo Terminado. Para verla jugar: iniciar.bat
pause
