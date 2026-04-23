@echo off
setlocal
title Jarvis - Dev Mode
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo ERRO: Ambiente virtual nao encontrado!
    pause
    exit /b 1
)

echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

if %errorlevel% neq 0 (
    echo.
    echo ERRO: falha ao ativar o ambiente virtual.
    pause
    exit /b %errorlevel%
)

echo ----------------------------
echo Iniciando Jarvis em modo DEV
echo ----------------------------

call python agent.py dev

if %errorlevel% neq 0 (
    echo.
    echo ERRO: o Jarvis encerrou com falha.
)

pause
