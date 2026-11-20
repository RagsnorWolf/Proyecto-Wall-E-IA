@echo off
rem Lanzador de la cabina. La ruta se resuelve con %~dp0 para que funcione
rem en cualquier PC, no solo donde se escribio.
setlocal
chcp 65001 >nul
title WALL-E - Asistente IA (Cabina Web)
cd /d "%~dp0"

echo.
echo ========================================
echo   WALL-E - Asistente de IA
echo   Centro de Comando (Puerto 8765)
echo ========================================
echo.

if not exist "launcher.py" (
  echo No encuentro launcher.py en esta carpeta.
  echo Este .bat tiene que estar junto a launcher.py, dentro de cockpit.
  pause
  exit /b 1
)

rem Verificar Python
set "PY=python"
where python >nul 2>nul
if not %errorlevel%==0 (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set "PY=py -3"
  ) else (
    echo No se encontro Python en esta PC.
    echo Instalalo desde https://python.org
    echo Despues corre INSTALAR.bat en la carpeta "Asistente IA Wall-E".
    pause
    exit /b 1
  )
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem Lanzar servidor (sin ventana negra)
start "WALL-E Servidor" /B %PY% launcher.py

echo.
echo Iniciando WALL-E Asistente IA...
echo Abriendo navegador en http://127.0.0.1:8765/
echo.
echo Si el navegador no se abre, entra manualmente a:
echo   http://127.0.0.1:8765/
echo.
echo Presiona cualquier tecla para cerrar este lanzador (el servidor sigue corriendo).
pause >nul
exit /b 0
