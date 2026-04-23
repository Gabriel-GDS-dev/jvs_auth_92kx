@echo off
setlocal
title Jarvis Front - Dev Mode
cd /d "%~dp0"

where pnpm >nul 2>nul
if %errorlevel% neq 0 (
	echo ERRO: pnpm não esta instalado ou não esta no PATH!
	pause
	exit /b 1
)

echo ----------------------------
echo Iniciando Frontend Jarvis
echo ----------------------------

if not exist "node_modules" (
	echo Instalando dependências...
	call pnpm install
	if %errorlevel% neq 0 (
		echo.
		echo ERRO: falha ao instalar dependências.
		pause
		exit /b %errorlevel%
	)
)

call pnpm dev

if %errorlevel% neq 0 (
	echo.
	echo ERRO: o frontend encerrou com falha.
)

pause