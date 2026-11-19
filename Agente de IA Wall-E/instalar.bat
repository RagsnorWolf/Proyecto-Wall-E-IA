@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   WALL-E - Agente de IA : instalacion
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
    echo [1/4] Creando entorno virtual .venv ...
    python -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [1/4] El entorno virtual ya existe.
)

echo [2/4] Instalando dependencias ^(ninguna obligatoria^) ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :error

echo [3/4] Corriendo las pruebas del bucle ^(sin red, servidor falso^) ...
".venv\Scripts\python.exe" -m unittest pruebas_agente
if errorlevel 1 goto :error

echo [4/4] Comprobando el simulador vendorizado ...
".venv\Scripts\python.exe" -c "from agente.actuadores import ActuadorSimulado; print('cuerpo simulado OK:', ActuadorSimulado('patio', semilla=1).estado()['escenario'])"
if errorlevel 1 goto :error

if not exist "config.json" (
    copy /y config.ejemplo.json config.json >nul
    echo.
    echo [AVISO] Cree config.json a partir del ejemplo.
    echo         Falta la clave del modelo: define la variable WALLE_API_KEY
    echo.
    echo         PowerShell:  $env:WALLE_API_KEY="tu-clave"
    echo         CMD:         set WALLE_API_KEY=tu-clave
    echo.
)

echo.
echo Listo. Para arrancar: iniciar.bat
echo   o ejecuta:  .venv\Scripts\python.exe main.py --probar
pause
exit /b 0

:error
echo.
echo [ERROR] Algo fallo. Copia este mensaje y consulta el README.
pause
exit /b 1
