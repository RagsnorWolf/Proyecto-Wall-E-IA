@echo off
setlocal
chcp 65001 >nul
title WALL-E - Guardian del entrenamiento
cd /d "%~dp0"

echo.
echo ========================================
echo   WALL-E - Guardian del entrenamiento
echo ========================================
echo.
echo Instala una tarea de Windows que cada 10 minutos revisa si el
echo entrenamiento sigue vivo. Si murio por un reinicio, lo reanuda
echo desde el ultimo checkpoint.
echo.
echo Se detiene solo cuando aparece models\ENTRENAMIENTO_COMPLETO.txt
echo o models\walle_ppo_model_v7.zip.
echo.
echo Usa: %~nx0 instalar   ^|   %~nx0 quitar   ^|   %~nx0 estado
echo.

set ACCION=%~1
if "%ACCION%"=="" set ACCION=estado

set TAREA=WALL-E Entrenamiento
set SCRIPT=%~dp0continuar_entrenamiento.ps1

if /i "%ACCION%"=="instalar" goto instalar
if /i "%ACCION%"=="quitar" goto quitar
if /i "%ACCION%"=="estado" goto estado
echo Accion desconocida: %ACCION%
goto fin

:instalar
schtasks /Query /TN "%TAREA%" >nul 2>nul
if %errorlevel%==0 (
  echo La tarea ya existe. Quitando la anterior...
  schtasks /Delete /TN "%TAREA%" /F >nul 2>nul
)
schtasks /Create /TN "%TAREA%" /SC MINUTE /MO 10 /F ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%SCRIPT%\"" >nul
if %errorlevel%==0 (
  echo.
  echo Tarea instalada: se ejecuta cada 10 minutos.
  echo Para quitarla: %~nx0 quitar
) else (
  echo.
  echo No se pudo crear la tarea. Proba ejecutando este .bat como administrador.
)
goto fin

:quitar
schtasks /Delete /TN "%TAREA%" /F >nul 2>nul
if %errorlevel%==0 (
  echo Tarea eliminada.
) else (
  echo No habia tarea instalada.
)
goto fin

:estado
schtasks /Query /TN "%TAREA%" /FO LIST 2>nul
if %errorlevel% neq 0 (
  echo No hay tarea instalada.
  echo Instalala con: %~nx0 instalar
)
goto fin

:fin
echo.
pause
exit /b 0
