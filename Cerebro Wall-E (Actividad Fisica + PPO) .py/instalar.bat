@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   WALL-E - Cerebro PPO : instalacion
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

echo [2/4] Instalando dependencias ^(ninguna obligatoria; pygame para --ventana^) ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
".venv\Scripts\python.exe" -m pip install --quiet pygame
if errorlevel 1 echo [AVISO] Sin pygame: se puede entrenar y evaluar, pero no abrir la ventana.

echo [3/4] Verificando el gradiente y el entorno ...
".venv\Scripts\python.exe" -m unittest pruebas
if errorlevel 1 goto :error

echo [4/4] Prueba de humo: entrenamiento de 2048 pasos ...
".venv\Scripts\python.exe" entrenar_ppo.py --pasos 2048 --eval-episodios 1 --guardar modelo\prueba.json --registro modelo\prueba.csv
if errorlevel 1 goto :error
del /q modelo\prueba.json modelo\prueba.csv 2>nul

echo.
echo Listo. Ahora:
echo   entrenar.bat            entrena la politica ^(60.000 pasos, unos minutos^)
echo   mirar.bat               abre la ventana con la politica jugando
echo   iniciar.bat             lo mismo que mirar.bat
pause
exit /b 0

:error
echo.
echo [ERROR] Algo fallo. Copia este mensaje y consulta el README.
pause
exit /b 1
