#!/usr/bin/env bash
# Instalacion del Cerebro PPO en Linux o macOS.
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo "  WALL-E - Cerebro PPO : instalacion"
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

echo "[2/4] Instalando dependencias (ninguna obligatoria; pygame para --ventana) ..."
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
.venv/bin/python -m pip install --quiet pygame || echo "[AVISO] Sin pygame: se puede entrenar, pero no abrir la ventana."

echo "[3/4] Verificando el gradiente y el entorno ..."
.venv/bin/python -m unittest pruebas

echo "[4/4] Prueba de humo: entrenamiento de 2048 pasos ..."
.venv/bin/python entrenar_ppo.py --pasos 2048 --eval-episodios 1 \
    --guardar modelo/prueba.json --registro modelo/prueba.csv
rm -f modelo/prueba.json modelo/prueba.csv

echo
echo "Listo. Entrenar:  .venv/bin/python entrenar_ppo.py --pasos 60000"
echo "        Ver:       .venv/bin/python evaluar.py --ventana"
