@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title WALL-E - Hablar con el robot
cd /d "%~dp0cerebro"

if not exist "consola.py" (
  echo No encuentro cerebro\consola.py.
  echo Este .bat tiene que estar en la carpeta "Cerebro Wall-E".
  pause
  exit /b 1
)

set "PY=python"
where python >nul 2>nul
if not !errorlevel!==0 (
  where py >nul 2>nul
  if !errorlevel!==0 (
    set "PY=py"
  ) else (
    echo No encuentro Python.
    echo Instalalo con: winget install Python.Python.3.12
    pause
    exit /b 1
  )
)

set "IP=%~1"
if "%IP%"=="" if exist "ip_robot.txt" (
  set /p IP=<ip_robot.txt
)
if "%IP%"=="" (
  echo.
  echo ========================================
  echo   WALL-E - Hablar con el robot
  echo ========================================
  echo.
  echo Escribe la IP que imprimio el ESP32 al arrancar.
  echo La encontras en el Monitor Serie del Arduino IDE, a 115200.
  echo.
  set /p IP=IP del ESP32: 
)
if "%IP%"=="" (
  echo Sin IP no hay a donde mandar las ordenes.
  pause
  exit /b 1
)
>"ip_robot.txt" echo !IP!

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

%PY% consola.py --host !IP!

echo.
echo Conexion cerrada.
pause
exit /b 0
