@echo off
setlocal
chcp 65001 >nul
title WALL-E - Continuar Entrenamiento
cd /d "%~dp0"

echo.
echo ========================================
echo   WALL-E - Continuar entrenamiento
echo   Reanuda si no esta corriendo
echo ========================================
echo.
echo Revisa tres cosas antes de lanzar:
echo   1. No existe models\ENTRENAMIENTO_COMPLETO.txt
echo   2. No existe models\walle_ppo_model_v6.zip
echo   3. No hay ningun train_walle corriendo
echo.
echo Si el entrenamiento ya termino, no hace nada.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0continuar_entrenamiento.ps1" %*

echo.
pause
exit /b 0
