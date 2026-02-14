@echo off
setlocal

REM Requiere: pip install pyinstaller
REM Genera UN solo .exe (one-file) sin consola
pyinstaller --noconfirm --clean --onefile --windowed --name MisFinanzas finanzas_gui.py

echo.
echo Ejecutable generado en: dist\MisFinanzas.exe
echo Puedes compartir directamente este .exe.
endlocal
