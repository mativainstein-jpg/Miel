@echo off
chcp 65001 >nul
title Instalacion — Procesador de Facturas
cd /d "%~dp0"
echo.
echo  ============================================
echo   INSTALACION PROCESADOR DE FACTURAS
echo  ============================================
echo.

REM ── Verificar Python ────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python no esta instalado.
    echo.
    echo  Pasos para instalarlo:
    echo    1. Ir a https://www.python.org/downloads/
    echo    2. Descargar la version mas reciente
    echo    3. Durante la instalacion, tildar "Add Python to PATH"
    echo    4. Volver a ejecutar este archivo
    echo.
    pause
    exit /b 1
)
python --version
echo  Python encontrado correctamente.
echo.

REM ── Verificar Git (para que la app se actualice sola) ───────
where git >nul 2>&1
if errorlevel 1 (
    echo  [AVISO] Git no esta instalado.
    echo  Sin Git la app funciona igual, pero NO se actualizara sola.
    echo  Para tener las actualizaciones automaticas:
    echo    1. Instalar Git desde https://git-scm.com/download/win
    echo    2. Volver a ejecutar este archivo
    echo.
) else (
    git --version
    echo  Git encontrado: las actualizaciones seran automaticas.
    echo.
)

REM ── Instalar dependencias ───────────────────────────────────
echo  Instalando librerias necesarias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR al instalar librerias.
    echo  Verifica tu conexion a internet e intenta de nuevo.
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Instalacion completada correctamente.
echo.
echo   Para usar la aplicacion, abri:
echo      procesar.bat
echo  ============================================
echo.
pause
