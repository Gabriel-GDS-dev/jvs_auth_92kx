@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Jarvis
cd /d "%~dp0"

set "FORCE_REINSTALL_DEPS=0"
set "SETUP_ONLY=0"
if /I "%~1"=="--reinstall-deps" set "FORCE_REINSTALL_DEPS=1"
if /I "%~1"=="--reinstall" set "FORCE_REINSTALL_DEPS=1"
if /I "%~1"=="--setup-only" set "SETUP_ONLY=1"

if exist "venv\Scripts\python.exe" (
    call :check_venv_python
    if errorlevel 1 (
        echo.
        echo O ambiente virtual atual esta quebrado ou foi criado com Python incompativel.
        echo Para as dependencias de audio/video do Jarvis, use Python 3.11 ou 3.12.
        echo Recriando automaticamente para evitar essa pergunta toda vez...
        rmdir /S /Q "venv"
    )
)

if not exist "venv\Scripts\python.exe" (
    call :find_python
    if errorlevel 1 (
        echo ERRO: Python 3.11 ou 3.12 nao encontrado. Instale uma dessas versoes ou adicione ao PATH.
        echo.
        echo Dica: para este projeto, evite Python 3.13 por enquanto.
        echo Algumas dependencias de imagem/audio ainda puxam wheels mais estaveis no Python 3.11/3.12.
        pause
        exit /b 1
    )

    echo Criando ambiente virtual...
    if defined PYTHON_ARGS (
        "!PYTHON_EXE!" !PYTHON_ARGS! -m venv venv
    ) else (
        "!PYTHON_EXE!" -m venv venv
    )
    if errorlevel 1 (
        echo.
        echo ERRO: nao foi possivel criar o ambiente virtual.
        pause
        exit /b 1
    )

    call :check_venv_python
    if errorlevel 1 (
        echo.
        echo ERRO: o ambiente virtual foi criado, mas nao esta usando Python 3.11/3.12.
        pause
        exit /b 1
    )
)

echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

if errorlevel 1 (
    echo.
    echo ERRO: falha ao ativar o ambiente virtual.
    pause
    exit /b 1
)

if exist "requirements.txt" (
    set "DEPS_STAMP_FILE=venv\.jarvis_deps_stamp"
    set "NEED_INSTALL_DEPS=%FORCE_REINSTALL_DEPS%"

    call :read_venv_python_version
    call :get_requirements_hash
    if errorlevel 1 (
        echo.
        echo Aviso: nao foi possivel calcular o hash de requirements.txt.
        echo As dependencias serao verificadas agora.
        set "NEED_INSTALL_DEPS=1"
    )

    if "!NEED_INSTALL_DEPS!"=="0" (
        if not exist "!DEPS_STAMP_FILE!" (
            set "NEED_INSTALL_DEPS=1"
        ) else (
            call :read_deps_stamp
            if /I not "!STAMP_REQUIREMENTS_HASH!"=="!REQUIREMENTS_HASH!" (
                set "NEED_INSTALL_DEPS=1"
            ) else if /I not "!STAMP_PYTHON_VERSION!"=="!VENV_PYTHON_VERSION!" (
                echo Marcador de dependencias antigo/incompleto; validando ambiente rapidamente...
                call :check_required_packages
                if errorlevel 1 (
                    set "NEED_INSTALL_DEPS=1"
                ) else (
                    call :write_deps_stamp
                )
            )
        )
    )

    if "!NEED_INSTALL_DEPS!"=="0" (
        call :check_required_packages
        if errorlevel 1 (
            echo Dependencias essenciais ausentes; instalando agora...
            set "NEED_INSTALL_DEPS=1"
        )
    )

    if "!NEED_INSTALL_DEPS!"=="0" (
        echo Dependencias ja instaladas; pulando verificacao.
    ) else (
        if "!FORCE_REINSTALL_DEPS!"=="1" echo Reinstalacao/verificacao de dependencias solicitada.

        echo Garantindo pip no ambiente virtual...
        python -m ensurepip --upgrade
        if errorlevel 1 (
            echo.
            echo ERRO: falha ao preparar pip no ambiente virtual.
            pause
            exit /b 1
        )

        echo Instalando/atualizando dependencias...
        python -m pip install -r requirements.txt
        if errorlevel 1 (
            echo.
            echo ERRO: falha ao instalar dependencias.
            pause
            exit /b 1
        )

        call :write_deps_stamp
        if errorlevel 1 (
            echo.
            echo Aviso: dependencias instaladas, mas nao foi possivel gravar o marcador.
            echo O proximo inicio pode verificar as dependencias novamente.
        )
    )
)

if "%SETUP_ONLY%"=="1" (
    echo.
    echo Ambiente pronto. Use Jarvis.bat para iniciar o Jarvis.
    exit /b 0
)

echo ----------------------------
echo Iniciando Jarvis
echo ----------------------------

call python agent.py start

if errorlevel 1 (
    echo.
    echo ERRO: o Jarvis encerrou com falha.
)

pause
exit /b 0

:find_python
set "PYTHON_EXE="
set "PYTHON_ARGS="

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.11"
    exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    exit /b 0
)

py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.12"
    exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in [(3, 11), (3, 12)] else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    exit /b 0
)

exit /b 1

:check_venv_python
call :read_venv_python_version
if "!VENV_PYTHON_VERSION!"=="3.11" exit /b 0
if "!VENV_PYTHON_VERSION!"=="3.12" exit /b 0
if defined VENV_PYTHON_VERSION (
    echo Python do venv atual: !VENV_PYTHON_VERSION!
) else (
    echo Python do venv atual: nao foi possivel detectar
)
exit /b 1

:read_venv_python_version
set "VENV_PYTHON_VERSION="
if not exist "venv\Scripts\python.exe" exit /b 1
for /f "delims=" %%V in ('venv\Scripts\python.exe -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" 2^>nul') do set "VENV_PYTHON_VERSION=%%V"
if not defined VENV_PYTHON_VERSION exit /b 1
exit /b 0

:get_requirements_hash
set "REQUIREMENTS_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath 'requirements.txt').Hash" 2^>nul`) do set "REQUIREMENTS_HASH=%%H"
if not defined REQUIREMENTS_HASH exit /b 1
exit /b 0

:read_deps_stamp
set "STAMP_PYTHON_VERSION="
set "STAMP_REQUIREMENTS_HASH="
for /f "usebackq tokens=1,* delims==" %%A in ("!DEPS_STAMP_FILE!") do (
    if /I "%%A"=="PYTHON_VERSION" set "STAMP_PYTHON_VERSION=%%B"
    if /I "%%A"=="REQUIREMENTS_HASH" set "STAMP_REQUIREMENTS_HASH=%%B"
)
exit /b 0

:check_required_packages
python -m pip show python-dotenv livekit-agents livekit-plugins-openai livekit-plugins-google livekit-plugins-silero >nul 2>nul
if errorlevel 1 exit /b 1
exit /b 0

:write_deps_stamp
if not defined VENV_PYTHON_VERSION call :read_venv_python_version
(
    echo PYTHON_VERSION=!VENV_PYTHON_VERSION!
    echo REQUIREMENTS_HASH=!REQUIREMENTS_HASH!
) > "!DEPS_STAMP_FILE!"
if errorlevel 1 exit /b 1
exit /b 0
