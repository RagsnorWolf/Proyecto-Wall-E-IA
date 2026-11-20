@echo off
rem ---------------------------------------------------------------------------
rem WALL-E - Cerebro Robot
rem
rem Menu del cerebro. La ruta se resuelve con %~dp0 para que funcione en
rem cualquier PC. ASCII puro y sin BOM: un acento o un BOM rompe cmd.
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
chcp 65001 >nul
title WALL-E - Cerebro Robot
cd /d "%~dp0"

if not exist "cerebro\consola.py" goto SIN_ARCHIVOS

rem --- Python ---
set "PY=python"
where python >nul 2>nul
if not !errorlevel!==0 goto BUSCAR_PY
goto PY_LISTO

:BUSCAR_PY
where py >nul 2>nul
if not !errorlevel!==0 goto SIN_PY
set "PY=py"

:PY_LISTO
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem --- IP guardada o la que venga por argumento ---
set "IP=%~1"
if "%IP%"=="" if exist "ip_robot.txt" set /p IP=<ip_robot.txt

:MENU
cls
echo.
echo ============================================
echo   WALL-E  -  CEREBRO DEL ROBOT
echo ============================================
echo.
if "%IP%"=="" (
  echo   IP del ESP32: sin definir
) else (
  echo   IP del ESP32: %IP%
)
echo.
echo   [1] Modo manual      hablarle en castellano
echo   [2] Modo autonomo    esquiva obstaculos solo
echo   [3] Probar el enlace sin robot
echo   [4] Estado del enlace
echo   [5] Cambiar la IP
echo   [0] Salir
echo.
choice /c 123450 /n /m "Opcion: "
set "OP=%errorlevel%"

if "%OP%"=="1" goto MANUAL
if "%OP%"=="2" goto AUTONOMO
if "%OP%"=="3" goto PRUEBAS
if "%OP%"=="4" goto ESTADO
if "%OP%"=="5" goto CAMBIAR_IP
if "%OP%"=="6" goto SALIR
goto MENU

rem ---------------------------------------------------------------------------
:MANUAL
if "%IP%"=="" goto PEDIR_IP
cls
%PY% "cerebro\consola.py" --host %IP%
echo.
pause
goto MENU

rem ---------------------------------------------------------------------------
:AUTONOMO
if "%IP%"=="" goto PEDIR_IP
cls
echo.
echo ============================================
echo   MODO AUTONOMO
echo ============================================
echo.
echo   El robot va a empezar a moverse solo.
echo   Dejalo en el piso, con espacio alrededor.
echo.
echo   Ctrl+C para parar.
echo.
pause
%PY% "cerebro\autonomo.py" --host %IP%
echo.
pause
goto MENU

rem ---------------------------------------------------------------------------
:PRUEBAS
cls
echo.
echo Pruebas del enlace, sin robot y sin WiFi.
echo Levanta un puente falso y habla con el.
echo.
%PY% "cerebro\test_link.py" --loopback
echo.
pause
goto MENU

rem ---------------------------------------------------------------------------
:ESTADO
if "%IP%"=="" goto PEDIR_IP
cls
%PY% "cerebro\consola.py" --host %IP% --status
echo.
pause
goto MENU

rem ---------------------------------------------------------------------------
:CAMBIAR_IP
cls
echo.
echo IP actual: %IP%
echo.
echo La encontras en el Monitor Serie del Arduino IDE, a 115200,
echo en la linea que imprime el ESP32 al arrancar.
echo.
set "NUEVA="
set /p NUEVA=Nueva IP del ESP32: 
if "%NUEVA%"=="" goto MENU
set "IP=%NUEVA%"
> "ip_robot.txt" echo %IP%
echo Guardada en ip_robot.txt
echo.
pause
goto MENU

rem ---------------------------------------------------------------------------
:PEDIR_IP
cls
echo.
echo Todavia no hay IP guardada.
echo.
set "IP="
set /p IP=IP del ESP32: 
if "%IP%"=="" goto MENU
> "ip_robot.txt" echo %IP%
goto MENU

rem ---------------------------------------------------------------------------
:SIN_PY
echo.
echo No encuentro Python en esta PC.
echo Instalalo con: winget install Python.Python.3.12
echo.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:SIN_ARCHIVOS
echo.
echo No encuentro cerebro\consola.py
echo Este .bat tiene que estar en la carpeta "Cerebro Wall-E".
echo.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:SALIR
endlocal
exit /b 0
