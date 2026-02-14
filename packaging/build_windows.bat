@echo off
setlocal

REM Requiere: pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name MisFinanzas finanzas_gui.py

echo.
echo Ejecutable generado en: dist\MisFinanzas\MisFinanzas.exe
echo Puedes compartir la carpeta dist\MisFinanzas completa.
endlocal
