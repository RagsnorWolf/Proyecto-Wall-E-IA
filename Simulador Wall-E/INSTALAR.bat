@echo off
rem Crea el entorno virtual del simulador e instala lo que necesita.
rem Una sola vez por computadora. Tarda unos minutos.
setlocal enabledelayedexpansion
chcp 65001 >nul
title WALL-E - Instalar Simulador
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul
if not !errorlevel!==0 (
  where py >nul 2>nul
  if !errorlevel!==0 (
    set "PY=py -3"
  ) else (
    echo No encuentro Python.
    echo Instalalo con: winget install Python.Python.3.12
    pause
    exit /b 1
  )
)

echo.
echo === Creando entorno virtual en .venv ===
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo No pude crear el entorno virtual.
    pause
    exit /b 1
  )
)

echo.
echo === Instalando dependencias ===
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Fallo la instalacion. Revisa el mensaje de arriba.
  pause
  exit /b 1
)

echo.
echo === Comprobando que PyBullet abre ===
".venv\Scripts\python.exe" -c "import pybullet, numpy, torch; print('pybullet', pybullet.getAPIVersion()); print('numpy', numpy.__version__); print('torch', torch.__version__)"
if errorlevel 1 (
  echo.
  echo PyBullet no arranca. Suele faltar Visual C++ Redistributable:
  echo https://aka.ms/vs/17/release/vc_redist.x64.exe
  pause
  exit /b 1
)

echo.
echo === Listo ===
echo Abre el simulador con "WALL-E Simulador Robot.bat".
echo.
pause
exit /b 0
