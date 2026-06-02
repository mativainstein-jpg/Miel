@echo off
title Compilar ProcesadorFacturas.exe
cd /d "%~dp0"
echo.
echo  ============================================================
echo   GENERANDO ProcesadorFacturas.exe
echo   Esto puede tardar 3-5 minutos, no cierres esta ventana.
echo  ============================================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python no encontrado.
    echo  Instalar desde python.org y tildar "Add Python to PATH"
    pause & exit /b 1
)

REM Instalar dependencias + PyInstaller
echo  [1/3] Instalando dependencias...
python -m pip install -r requirements.txt >nul 2>&1
python -m pip install pyinstaller >nul 2>&1
echo       OK

REM Limpiar compilaciones anteriores
if exist dist\ProcesadorFacturas.exe (
    echo  Borrando version anterior...
    del /f dist\ProcesadorFacturas.exe >nul 2>&1
)

REM Compilar (usando python -m para evitar problemas de PATH)
echo  [2/3] Compilando (tarda unos minutos)...
python -m PyInstaller ProcesadorFacturas.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo  ERROR durante la compilacion.
    echo  Revisa los mensajes de arriba.
    pause & exit /b 1
)

REM Verificar que se generó
if not exist dist\ProcesadorFacturas.exe (
    echo.
    echo  ERROR: No se encontro el ejecutable generado.
    pause & exit /b 1
)

echo  [3/3] Listo.
echo.
echo  ============================================================
echo   Ejecutable generado en:
echo     %~dp0dist\ProcesadorFacturas.exe
echo.
echo   Para distribuir:
echo     1. Copiar  dist\ProcesadorFacturas.exe  a la carpeta destino
echo     2. Si usan Gmail, copiar tambien  credentials.json
echo     3. El usuario solo hace doble clic en ProcesadorFacturas.exe
echo  ============================================================
echo.
pause
