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

echo Encerrando servidor antigo do frontend, se existir...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=(Resolve-Path '.').Path; $all=Get-CimInstance Win32_Process; $targets=$all | Where-Object { $_.CommandLine -and $_.Name -eq 'node.exe' -and $_.CommandLine.Contains($root) }; foreach ($p in $targets) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"

echo ----------------------------
echo Iniciando Frontend Jarvis
echo ----------------------------

if exist ".next" (
	echo Limpando cache antigo do Next.js...
	rmdir /s /q ".next"
	if exist ".next" (
		echo.
		echo ERRO: nao foi possivel limpar a pasta .next.
		echo Feche terminais/processos do frontend e tente novamente.
		pause
		exit /b 1
	)
)

if not exist "node_modules\next\dist\bin\next" (
	echo Instalando/reparando dependencias...
	call pnpm install
	if %errorlevel% neq 0 (
		echo.
		echo ERRO: falha ao instalar dependencias.
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
