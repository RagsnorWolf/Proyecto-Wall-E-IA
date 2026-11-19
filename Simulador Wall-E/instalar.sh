#!/usr/bin/env bash
# Instalacion del Simulador Wall-E en Linux o macOS.
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo "  WALL-E - Simulador : instalacion"
echo "=========================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] No encuentro python3. Instalalo desde https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/3] Creando entorno virtual .venv ..."
    python3 -m venv .venv
else
    echo "[1/3] El entorno virtual ya existe."
fi

echo "[2/3] Instalando dependencias (pygame para la ventana) ..."
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

echo "[3/3] Comprobando que el motor funciona (sin ventana) ..."
.venv/bin/python main.py --sin-ventana --pasos 120

echo
echo "Listo. Para jugar: .venv/bin/python main.py"
