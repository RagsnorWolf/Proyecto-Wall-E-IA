@echo off
rem Instala lo que necesita el Asistente IA. Una sola vez por computadora.
setlocal enabledelayedexpansion
chcp 65001 >nul
title WALL-E - Instalar Asistente IA
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul
if not %errorlevel%==0 (
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
echo === Instalando dependencias del asistente ===
%PY% -m pip install --upgrade pip
%PY% -m pip install -r "Modelo AI\requirements.txt"
if errorlevel 1 (
  echo.
  echo Fallo la instalacion. Revisa el mensaje de arriba.
  pause
  exit /b 1
)

echo.
echo === Listo ===
echo.
echo Falta una cosa que no se instala con pip: Ollama, el motor del modelo
echo de lenguaje. Descargalo de https://ollama.com y despues corre:
echo.
echo     ollama pull qwen2.5:3b
echo.
echo Sin Ollama el asistente abre pero no puede conversar.
echo.
pause
exit /b 0
