#!/usr/bin/env bash
# Instalacion de la cabina WALL-E en Linux o macOS.
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo "  WALL-E - Agente de IA (cabina web)"
echo "=========================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] No encuentro python3. Instalalo desde https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/4] Creando entorno virtual .venv ..."
    python3 -m venv .venv
else
    echo "[1/4] El entorno virtual ya existe."
fi

echo "[2/4] Instalando dependencias opcionales ..."
.venv/bin/python -m pip install --quiet --upgrade pip || true
.venv/bin/python -m pip install --quiet -r requirements.txt \
    || echo "[AVISO] Faltan dependencias opcionales; la cabina funciona igual."

echo "[3/4] Comprobando el cerebro y el servidor ..."
.venv/bin/python -m unittest pruebas_agente

echo "[4/4] Creando config.json y carpetas de datos ..."
[ -f config.json ] || cp config.ejemplo.json config.json
mkdir -p datos

echo
echo "Listo. Arrancar:  .venv/bin/python server.py"
echo "Abre http://127.0.0.1:8765/ y presiona iniciar."
