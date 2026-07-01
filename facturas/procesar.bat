@echo off
chcp 65001 >nul
title Procesador de Facturas
cd /d "%~dp0"

REM ── Verificar Python ────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python no esta instalado.
    echo  Ejecuta primero  primera_vez.bat
    echo.
    pause
    exit /b 1
)

REM ── Buscar la ultima version (si hay internet) ──────────────
python actualizar.py

REM ── Instalar lo que falte (rapido si ya esta todo) ──────────
python -m pip install -q -r requirements.txt 2>nul

REM ── Iniciar la aplicacion ───────────────────────────────────
python main.py
if errorlevel 1 (
    echo.
    echo  La aplicacion cerro con un error. Revisa el mensaje de arriba.
    pause
)
