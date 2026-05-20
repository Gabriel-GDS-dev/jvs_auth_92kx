@echo off
setlocal
title Jarvis
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE="
    set "PYTHON_ARGS="

    py -3 -c "import sys" >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )

    if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
    )

    if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    )

    if not defined PYTHON_EXE (
        echo ERRO: Python nao encontrado. Instale Python 3.11+ ou adicione ao PATH.
        pause
        exit /b 1
    )

    echo Criando ambiente virtual...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m venv venv
    if %errorlevel% neq 0 (
        echo.
        echo ERRO: nao foi possivel criar o ambiente virtual.
        pause
        exit /b %errorlevel%
    )
)

echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

if %errorlevel% neq 0 (
    echo.
    echo ERRO: falha ao ativar o ambiente virtual.
    pause
    exit /b %errorlevel%
)

if exist "requirements.txt" (
    echo Instalando/atualizando dependencias...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo ERRO: falha ao instalar dependencias.
        pause
        exit /b %errorlevel%
    )
)

echo ----------------------------
echo Iniciando Jarvis
echo ----------------------------

call python agent.py start

if %errorlevel% neq 0 (
    echo.
    echo ERRO: o Jarvis encerrou com falha.
)

pause
