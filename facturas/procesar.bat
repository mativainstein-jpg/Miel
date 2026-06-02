@echo off
title Procesador de Facturas
cd /d "%~dp0"

REM Verificar que Python esté instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python no está instalado.
    echo.
    echo  Descargalo desde: https://www.python.org/downloads/
    echo  Asegurate de marcar "Add Python to PATH" durante la instalación.
    echo.
    pause
    exit /b 1
)

REM Instalar dependencias si no están
pip show PyQt5 >nul 2>&1
if errorlevel 1 (
    echo  Instalando dependencias por primera vez, espera un momento...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  ERROR al instalar dependencias. Revisa tu conexión a internet.
        echo.
        pause
        exit /b 1
    )
    echo  Dependencias instaladas correctamente.
)

REM Iniciar la aplicación
python main.py
if errorlevel 1 (
    echo.
    echo  La aplicación cerró con un error. Revisá el mensaje de arriba.
    pause
)
