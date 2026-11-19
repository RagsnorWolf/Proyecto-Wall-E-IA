@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   WALL-E - Agente de IA (cabina web)
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

echo [2/4] Instalando dependencias opcionales ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [AVISO] Algunas dependencias opcionales no se instalaron.
    echo         La cabina funciona igual: reporta lo que falta en /api/state.
)

echo [3/4] Comprobando el cerebro y el servidor ...
".venv\Scripts\python.exe" -m unittest pruebas_agente
if errorlevel 1 goto :error

echo [4/4] Creando config.json y carpetas de datos ...
if not exist "config.json" copy /y config.ejemplo.json config.json >nul
if not exist "datos" mkdir "datos"

echo.
echo Listo. Para arrancar:
echo   iniciar.bat                  consola con el registro del servidor
echo   "WALL-E Asistente IA.bat"    sin consola, abre el navegador solo
echo   crear_acceso_directo.bat     deja el icono en el escritorio
echo.
echo La cabina escucha en http://127.0.0.1:8765/
echo Para conversar necesita Ollama con el modelo creado: build_model.py
pause
exit /b 0

:error
echo.
echo [ERROR] Algo fallo. Copia este mensaje y consulta el README.
pause
exit /b 1
