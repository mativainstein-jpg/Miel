@echo off
title Instalación — Procesador de Facturas
cd /d "%~dp0"
echo.
echo  ============================================
echo   INSTALACION PROCESADOR DE FACTURAS
echo  ============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python no está instalado.
    echo.
    echo  Pasos para instalarlo:
    echo    1. Ir a https://www.python.org/downloads/
    echo    2. Descargar la versión más reciente
    echo    3. Durante la instalación, tildar "Add Python to PATH"
    echo    4. Volver a ejecutar este archivo
    echo.
    pause
    exit /b 1
)

python --version
echo  Python encontrado correctamente.
echo.

REM Instalar dependencias
echo  Instalando librerías necesarias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR al instalar librerías.
    echo  Verificá tu conexión a internet e intentá de nuevo.
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Instalación completada correctamente.
echo.
echo   Para usar la aplicación, abrí:
echo      procesar.bat
echo  ============================================
echo.
pause
