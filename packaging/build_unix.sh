#!/usr/bin/env bash
set -euo pipefail

# Requiere: pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name MisFinanzas finanzas_gui.py

echo

echo "Ejecutable generado en: dist/MisFinanzas/MisFinanzas"
echo "Puedes compartir la carpeta dist/MisFinanzas completa."
