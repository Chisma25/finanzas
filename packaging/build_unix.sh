#!/usr/bin/env bash
set -euo pipefail

# Requiere: pip install pyinstaller
# Genera binario one-file
pyinstaller --noconfirm --clean --onefile --windowed --name MisFinanzas finanzas_gui.py

echo
echo "Binario generado en: dist/MisFinanzas"
