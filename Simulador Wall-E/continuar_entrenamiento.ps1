# continuar_entrenamiento.ps1
#
# Guardian del entrenamiento. Se puede lanzar a mano o desde el Programador
# de tareas cada pocos minutos: si el entrenamiento no esta corriendo y no
# termino todavia, lo reanuda desde el ultimo checkpoint.
#
# Por que existe: el entrenamiento vive en un proceso que muere cuando se
# reinicia la sesion que lo lanzo. Sin guardian, un reinicio a mitad de noche
# deja el trabajo parado hasta que alguien mira.
#
# Condiciones para relanzar:
#   1. No existe models\ENTRENAMIENTO_COMPLETO.txt
#   2. No hay ningun proceso train_walle* corriendo
#   3. Hay algo que reanudar (un checkpoint) o no hay modelo final todavia
#
# Lo que NO mira: que exista models\walle_ppo_model_v6.zip. Ese archivo viene
# en el repo, asi que mirarlo apagaba el guardian para siempre: decia
# "se considera terminado" el primer dia y nunca reanudaba nada. Lo que manda
# es la marca de terminacion, que solo escribe el entrenador al acabar.
#
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File continuar_entrenamiento.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File continuar_entrenamiento.ps1 -Pasos 1200000

param(
    [int]$Pasos = 1200000,
    [int]$Workers = 2,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$Modelos = Join-Path $Raiz "models"
$Marca = Join-Path $Modelos "ENTRENAMIENTO_COMPLETO.txt"
$Final = Join-Path $Modelos "walle_ppo_model_v6.zip"
$Log = Join-Path $Raiz "entrenamiento_v6.log"
$LogErr = Join-Path $Raiz "entrenamiento_v6_err.log"
$Python = Join-Path $Raiz ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

function Escribir($texto) {
    Write-Host ("[GUARDIAN] " + $texto)
}

if (-not $Force) {
    if (Test-Path $Marca) {
        Escribir "el entrenamiento ya termino. No hago nada."
        exit 0
    }
}

$corriendo = @(
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like "*train_walle*" }
)
if ($corriendo.Count -gt 0) {
    Escribir ("ya hay un entrenamiento corriendo (PID " +
        (($corriendo | ForEach-Object { $_.ProcessId }) -join ", ") + "). No hago nada.")
    exit 0
}

$checkpoints = @()
if (Test-Path (Join-Path $Modelos "checkpoints")) {
    $checkpoints = @(
        Get-ChildItem (Join-Path $Modelos "checkpoints") -Filter "walle_v6_*.zip" |
            Sort-Object LastWriteTime -Descending
    )
}

if ($checkpoints.Count -gt 0) {
    Escribir ("reanudando desde " + $checkpoints[0].Name)
} elseif (Test-Path $Final) {
    # Modelo final en su sitio y sin checkpoints: no hay nada que reanudar.
    # Relanzar desde cero tiraria el modelo que ya esta.
    Escribir "hay modelo final y no hay checkpoints: nada que reanudar."
    exit 0
} else {
    Escribir "no hay checkpoints: arranca desde cero"
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$argumentos = @(
    "-u", "train_walle_v5.py",
    "--timesteps", "$Pasos",
    "--workers", "$Workers",
    "--vec", "dummy",
    "--output_dir", ".\models",
    "--auto_resume"
)

# Start-Process desacopla el proceso del arbol del shell que lo lanza: si la
# sesion que ejecuta este guardian se cierra, el entrenamiento sigue vivo.
$proceso = Start-Process -FilePath $Python `
    -ArgumentList $argumentos `
    -WorkingDirectory $Raiz `
    -RedirectStandardOutput $Log `
    -RedirectStandardError $LogErr `
    -WindowStyle Hidden `
    -PassThru

Escribir ("entrenamiento lanzado con PID " + $proceso.Id)
Escribir ("log: " + $Log)
exit 0
