@echo off
setlocal
chcp 65001 >nul
title WALL-E - Evaluar Cerebro
cd /d "%~dp0"

echo.
echo ========================================
echo   WALL-E - Banco de pruebas del cerebro
echo   Mide si el modelo aprendio de verdad
echo ========================================
echo.
echo Corre varios episodios con semillas fijas y saca una tabla:
echo   distancia neta, camino recorrido, contactos, atascos, chunks,
echo   velocidad media y recompensa.
echo.
echo OJO: cierra el simulador antes. Dos procesos PyBullet a la vez
echo matan el entrenamiento con un crash nativo sin mensaje.
echo.

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set EPISODIOS=%~1
if "%EPISODIOS%"=="" set EPISODIOS=10

set OBSTACULOS=%~2
if "%OBSTACULOS%"=="" set OBSTACULOS=8

echo Evaluando %EPISODIOS% episodios con %OBSTACULOS% obstaculos.
echo.

%PY% -u evaluar_v6.py --episodes %EPISODIOS% --obstacles %OBSTACULOS%

echo.
echo Evaluacion terminada.
pause
exit /b 0
