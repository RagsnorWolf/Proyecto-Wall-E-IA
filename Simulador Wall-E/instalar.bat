@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   WALL-E - Simulador : instalacion
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No encuentro Python en el PATH.
    echo         Instala Python 3.10 o superior desde https://www.python.org/downloads/
    echo         Marca la casilla "Add python.exe to PATH" durante la instalacion.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual .venv ...
    python -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [1/3] El entorno virtual ya existe.
)

echo [2/3] Instalando dependencias ^(pygame para la ventana^) ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [AVISO] pygame no se instalo. El motor y la prueba headless andan igual;
    echo         la ventana queda para cuando puedas instalarlo.
)

echo [3/3] Comprobando que el motor funciona ^(sin ventana^) ...
".venv\Scripts\python.exe" main.py --sin-ventana --pasos 120
if errorlevel 1 goto :error

echo.
echo Listo. Para jugar: doble clic en iniciar.bat
echo   o ejecuta:  .venv\Scripts\python.exe main.py
pause
exit /b 0

:error
echo.
echo [ERROR] Algo fallo. Copia este mensaje y consulta el README.
pause
exit /b 1
