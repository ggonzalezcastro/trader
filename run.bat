@echo off
REM ============================================================
REM Quick Start - FxGerard Trading Framework
REM ============================================================
REM Ejecucion rapida (requiere setup previo con setup.bat)
REM ============================================================

setlocal

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%.venv

REM --- CONFIGURACION (editar aqui) ---
set BROKER=FTMO
set MODE=paper
REM ======================================

echo FxGerard Trading Framework
echo Broker: %BROKER% | Mode: %MODE%
echo.

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ERROR: .venv no existe. Ejecutar setup.bat primero.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

echo Iniciando Trading Host...
python -m core.host

if errorlevel 1 (
    echo.
    echo ERROR: Host fallo. Ejecutar setup.bat para revisar.
    pause
)