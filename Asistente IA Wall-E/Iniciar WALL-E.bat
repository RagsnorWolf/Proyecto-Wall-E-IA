@echo off
rem Lanzador del Asistente IA. Abre la cabina web en el navegador.
rem La ruta se resuelve con %~dp0 para que funcione en cualquier PC.
setlocal
chcp 65001 >nul
title WALL-E - Asistente IA

set "COCKPIT=%~dp0Pagina Web\cockpit"
if not exist "%COCKPIT%\launcher.py" (
  echo No encuentro "Pagina Web\cockpit\launcher.py".
  echo Este .bat tiene que estar en la carpeta "Asistente IA Wall-E".
  pause
  exit /b 1
)

cd /d "%COCKPIT%"

set "PY=python"
where python >nul 2>nul
if not %errorlevel%==0 (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set "PY=py -3"
  ) else (
    echo No encuentro Python.
    echo Instalalo con: winget install Python.Python.3.12
    echo Despues corre INSTALAR.bat.
    pause
    exit /b 1
  )
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

%PY% launcher.py
if errorlevel 1 (
  echo.
  echo El asistente se cerro con error. Corre INSTALAR.bat si es la primera vez.
  pause
)
exit /b 0
