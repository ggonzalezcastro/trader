@echo off
REM ============================================================
REM FxGerard Trading Framework - Windows Setup & Launcher
REM ============================================================
REM Ejecutar como Administrador la primera vez
REM ============================================================

setlocal enabledelayedexpansion

echo ================================================
echo   FxGerard Trading Framework - Setup & Run
echo ================================================
echo.

REM --- CONFIGURACION ---
set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%.venv
set PYTHON_URL=https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe
set REQUIREMENTS=%PROJECT_DIR%requirements.txt
set HOST_MODULE=core.host

REM --- VARIABLES DE ENTORNO ---
set BROKER=FTMO
set MODE=paper

echo [1/6] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo     Python NO encontrado. Instalando Python 3.13...
    echo     Descargando desde python.org...
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%TEMP%\python-installer.exe'"
    echo     Ejecutando instalador...
    start /wait %TEMP%\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
    echo     Python instalado.
) else (
    echo     Python detected.
    python --version
)

echo.
echo [2/6] Verificando pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo     ERROR: pip no disponible. Instalar Python manualmente.
    pause
    exit /b 1
)
echo     pip OK.

echo.
echo [3/6] Creando entorno virtual...
if exist "%VENV_DIR%" (
    echo     .venv ya existe.
) else (
    echo     Creando .venv...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo     ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

echo.
echo [4/6] Activando entorno virtual...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [5/6] Instalando dependencias...
echo     Installing from requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r "%REQUIREMENTS%"

if errorlevel 1 (
    echo.
    echo     ERROR: Fallo instalando dependencias.
    pause
    exit /b 1
)
echo     Dependencias instaladas.

echo.
echo [6/6] Verificando MT5...
python -c "import MetaTrader5" >nul 2>&1
if errorlevel 1 (
    echo     AVISO: MetaTrader5 package no instalado (solo funciona en Windows con MT5 terminal)
    echo     Para instalar MT5: https://www.mql5.com/en/download
    echo     El framework seguira en modo simulacion.
) else (
    echo     MT5 package OK.
)

echo.
echo ================================================
echo   ENTORNO LISTO
echo ================================================
echo.
echo   Broker: %BROKER%
echo   Mode:   %MODE%
echo   Project: %PROJECT_DIR%
echo.

REM --- MENU DE ARRANQUE ---
:menu
echo Seleccionar accion:
echo.
echo   1 - Iniciar en modo PAPER (demo, sin riesgo)
echo   2 - Iniciar en modo LIVE (real)
echo   3 - Ver estado del sistema
echo   4 - Actualizar dependencias
echo   5 - Salir
echo.
set /p choice="Opcion [1-5]: "

if "!choice!"=="1" goto paper
if "!choice!"=="2" goto live
if "!choice!"=="3" goto status
if "!choice!"=="4" goto update
if "!choice!"=="5" goto end
goto menu

:paper
echo.
echo Iniciando en modo PAPER...
set MODE=paper
call :run_host
goto menu

:live
echo.
echo ADVERTENCIA: Esto ejecutara operaciones REALES con dinero.
set /p confirm="Escriba 'LIVE' para confirmar: "
if not "!confirm!"=="LIVE" (
    echo Operacion cancelada.
    goto menu
)
set MODE=live
call :run_host
goto menu

:status
echo.
echo --- Estado del Sistema ---
echo.
python -c "import sys; print('Python:', sys.version)" 2>nul || echo Python: NO
call "%VENV_DIR%\Scripts\python.exe" -c "import MetaTrader5; print('MT5: OK')" 2>nul || echo MT5: NO DISPONIBLE
call "%VENV_DIR%\Scripts\python.exe" -c "import pydantic; print('Pydantic:', pydantic.__version__)" 2>nul
call "%VENV_DIR%\Scripts\python.exe" -c "import loguru; print('Loguru: OK')" 2>nul
echo.
goto menu

:update
echo.
echo Actualizando dependencias...
call "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
call "%VENV_DIR%\Scripts\python.exe" -m pip install -r "%REQUIREMENTS%"
echo Actualizacion completa.
goto menu

:run_host
echo.
echo Iniciando Trading Host...
echo Broker: %BROKER%
echo Mode: %MODE%
echo Presiona Ctrl+C para detener.
echo.
set BROKER=%BROKER%
set MODE=%MODE%
call "%VENV_DIR%\Scripts\python.exe" -m %HOST_MODULE%
if errorlevel 1 (
    echo.
    echo ERROR: El host fallo. Revisar logs arriba.
    pause
)
goto :eof

:end
echo.
echo Saliendo...
exit /b 0