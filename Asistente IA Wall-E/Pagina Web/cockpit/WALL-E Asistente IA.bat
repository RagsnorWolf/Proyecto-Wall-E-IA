@echo off
setlocal
chcp 65001 >nul
title WALL-E - Asistente IA (Cabina Web)
cd /d "E:\Proyectos Ragsnor\Proyecto Wall - E\wall-e-companion\Pagina Web\cockpit"

echo.
echo ========================================
echo   WALL-E - Asistente de IA
echo   Centro de Comando (Puerto 8765)
echo ========================================
echo.

:: Verificar Python
where python >nul 2>nul
if %errorlevel%==0 (
  set "PY=python"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set "PY=py -3"
  ) else (
    echo No se encontro Python en esta PC.
    echo Instalalo desde https://python.org
    pause
    exit /b 1
  )
)

:: Lanzar servidor (sin ventana negra)
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
