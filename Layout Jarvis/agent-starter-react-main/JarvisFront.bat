@echo off
title Jarvis Front - Dev Mode
cd /d "%~dp0"

where pnpm >nul 2>nul
if %errorlevel% neq 0 (
	echo ERRO: pnpm não esta instalado ou não esta no PATH!
	pause
	exit
)

echo ----------------------------
echo Iniciando Frontend Jarvis
echo ----------------------------

if not exist "node_modules" (
	echo Instalando dependências...
	pnpm install
)

pnpm dev

pause