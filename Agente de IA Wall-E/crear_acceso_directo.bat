@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Deja en el escritorio el mismo acceso directo que usa el autor:
rem icono walle.ico y arranque silencioso por abrir_walle.vbs.
rem El script de PowerShell se genera aparte para no pelear con las comillas.

set "PS1=%TEMP%\walle_acceso_directo.ps1"

> "%PS1%" echo $dir = "%CD%"
>> "%PS1%" echo $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "WALL-E Asistente IA.lnk"
>> "%PS1%" echo $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
>> "%PS1%" echo $s.TargetPath = $env:COMSPEC
>> "%PS1%" echo $s.Arguments = '/c ""' + (Join-Path $dir "abrir_walle.vbs") + '""'
>> "%PS1%" echo $s.WorkingDirectory = $dir
>> "%PS1%" echo $s.IconLocation = (Join-Path $dir "walle.ico") + ",0"
>> "%PS1%" echo $s.WindowStyle = 7
>> "%PS1%" echo $s.Description = "WALL-E - Centro de Comando"
>> "%PS1%" echo $s.Save()
>> "%PS1%" echo Write-Host "Acceso directo creado:" $lnk

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "CODIGO=%ERRORLEVEL%"
del "%PS1%" >nul 2>nul

if not "%CODIGO%"=="0" (
    echo.
    echo [ERROR] No pude crear el acceso directo.
)

pause
exit /b %CODIGO%
