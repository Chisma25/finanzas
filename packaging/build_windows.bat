@echo off
setlocal

cd /d "%~dp0\.."

echo [1/3] Comprobando PyInstaller...
where pyinstaller >nul 2>&1
if errorlevel 1 (
  echo ERROR: PyInstaller no esta instalado o no esta en PATH.
  echo Ejecuta primero: pip install pyinstaller
  echo.
  pause
  exit /b 1
)

echo [2/3] Generando ejecutable one-file...
pyinstaller --noconfirm --clean --onefile --windowed --name MisFinanzas finanzas_gui.py
if errorlevel 1 (
  echo.
  echo ERROR: Fallo al generar el ejecutable.
  echo Revisa los mensajes anteriores.
  echo.
  pause
  exit /b 1
)

echo [3/3] OK
if exist "dist\MisFinanzas.exe" (
  echo Ejecutable generado en: dist\MisFinanzas.exe
) else (
  echo ADVERTENCIA: no se encontro dist\MisFinanzas.exe
)

echo.
echo Pulsa una tecla para cerrar...
pause >nul
endlocal
