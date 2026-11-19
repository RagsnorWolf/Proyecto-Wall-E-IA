#!/usr/bin/env bash
# Instalacion del Agente de IA en Linux o macOS.
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo "  WALL-E - Agente de IA : instalacion"
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

echo "[2/4] Instalando dependencias (ninguna obligatoria) ..."
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

echo "[3/4] Corriendo las pruebas del bucle (sin red, servidor falso) ..."
.venv/bin/python -m unittest pruebas_agente

echo "[4/4] Comprobando el simulador vendorizado ..."
.venv/bin/python -c "from agente.actuadores import ActuadorSimulado; print('cuerpo simulado OK:', ActuadorSimulado('patio', semilla=1).estado()['escenario'])"

if [ ! -f "config.json" ]; then
    cp config.ejemplo.json config.json
    echo
    echo "[AVISO] Cree config.json a partir del ejemplo."
    echo "        Falta la clave del modelo: export WALLE_API_KEY=\"tu-clave\""
fi

echo
echo "Listo. Arrancar: .venv/bin/python main.py"
