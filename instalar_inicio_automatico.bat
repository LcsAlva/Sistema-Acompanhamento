@echo off
title Inicializacao Automatica - Sistema URFCC
color 1F

REM ── Precisa de administrador ──────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [!] Execute como Administrador.
    pause
    exit /b 1
)

cd /d "%~dp0"
set PROJETO=%~dp0
set TAREFA=URFCC_Servidor

echo.
echo  ==========================================
echo   Instalacao de Inicio Automatico
echo   Sistema URFCC - ETM Engenharia
echo  ==========================================
echo.
echo  Opcoes:
echo.
echo  [1] Instalar - servidor sobe quando o PC ligar
echo  [2] Remover  - desinstalar inicio automatico
echo  [3] Cancelar
echo.
set /p OPCAO=  Escolha:

if "%OPCAO%"=="1" goto INSTALAR
if "%OPCAO%"=="2" goto REMOVER
goto FIM

:INSTALAR
echo.
echo  Instalando tarefa agendada...

REM Remove tarefa antiga se existir
schtasks /delete /tn "%TAREFA%" /f >nul 2>&1

REM Cria script auxiliar sem janela visivel (roda minimizado)
set SCRIPT_BAT=%PROJETO%_iniciar_silencioso.bat
echo @echo off > "%SCRIPT_BAT%"
echo cd /d "%PROJETO%" >> "%SCRIPT_BAT%"
echo python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 >> "%SCRIPT_BAT%"

REM Cria a tarefa agendada para rodar no logon do sistema
schtasks /create ^
    /tn "%TAREFA%" ^
    /tr "cmd /c \"%SCRIPT_BAT%\"" ^
    /sc onlogon ^
    /delay 0000:30 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f

if %errorLevel% equ 0 (
    echo.
    echo  [OK] Instalado com sucesso!
    echo.
    echo  O servidor URFCC vai iniciar automaticamente
    echo  30 segundos apos o login neste computador.
    echo.
    echo  Para iniciar agora sem reiniciar:
    echo    execute "iniciar_servidor.bat"
) else (
    echo.
    echo  [ERRO] Nao foi possivel criar a tarefa.
)
goto FIM

:REMOVER
echo.
schtasks /delete /tn "%TAREFA%" /f
if %errorLevel% equ 0 (
    echo  [OK] Inicio automatico removido.
) else (
    echo  [!] Tarefa nao encontrada ou ja removida.
)
del /q "%PROJETO%_iniciar_silencioso.bat" >nul 2>&1
goto FIM

:FIM
echo.
pause
