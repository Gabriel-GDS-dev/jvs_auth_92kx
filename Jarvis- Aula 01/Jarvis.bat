@echo off
title Jarvis - Dev Mode
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo ERRO: Ambiente virtual nao encontrado!
    pause
    exit
)

echo Ativando ambiente virtual...
call venv\Scripts\activate

echo ----------------------------
echo Iniciando Jarvis em modo DEV
echo ----------------------------

python agent.py dev

pause

1.	Abra o bloco de notas
2.	Cole o seguinte comando e salve como Jarvisfront.bat na pasta do projeto
3.	
@echo off
title Jarvis Front - Dev Mode
cd /d "%~dp0"

where pnpm >nul 2>nul
if %errorlevel% neq 0 (
    echo ERRO: pnpm nao esta instalado ou nao esta no PATH!
    pause
    exit
)

echo ----------------------------
echo Iniciando Frontend Jarvis
echo ----------------------------

if not exist "node_modules" (
    echo Instalando dependencias...
    pnpm install
)

pnpm dev

pause
