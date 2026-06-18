@echo off
title Configuracao de Rede - Sistema URFCC
color 1F

REM ── Precisa de permissao de administrador ──────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [!] Este script precisa ser executado como Administrador.
    echo      Clique com o botao direito e escolha "Executar como administrador".
    echo.
    pause
    exit /b 1
)

echo.
echo  ==========================================
echo   ETM Engenharia - Sistema URFCC
echo   Configuracao de Acesso em Rede
echo  ==========================================
echo.

REM ── Abre a porta 8001 no Firewall do Windows ──────────────────────────────
echo  [1/3] Configurando regra no Firewall do Windows...
netsh advfirewall firewall delete rule name="URFCC Sistema Web" >nul 2>&1
netsh advfirewall firewall add rule ^
    name="URFCC Sistema Web" ^
    dir=in ^
    action=allow ^
    protocol=TCP ^
    localport=8001 ^
    description="Sistema de Programacao Semanal URFCC - ETM Engenharia"
if %errorLevel% equ 0 (
    echo  [OK] Porta 8001 liberada no Firewall.
) else (
    echo  [ERRO] Nao foi possivel configurar o Firewall.
)

REM ── Mostra o IP local da maquina ──────────────────────────────────────────
echo.
echo  [2/3] Identificando IP da maquina na rede...
echo.

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1" ^| findstr /v "169.254"') do (
    set IP=%%a
    set IP=!IP: =!
)

REM Metodo alternativo mais confiavel
for /f "tokens=4 delims= " %%a in ('route print ^| findstr "0.0.0.0.*0.0.0.0" ^| head -1') do (
    set GATEWAY_IF=%%a
)

REM Exibe todos os IPs encontrados
echo  IPs disponiveis nesta maquina:
ipconfig | findstr /i "IPv4" | findstr /v "127.0.0.1" | findstr /v "169.254"

echo.
echo  [3/3] Configuracao concluida!
echo.
echo  ==========================================
echo   COMO OS COLEGAS ACESSAM:
echo.
echo   1. Abra o navegador (Chrome, Edge)
echo   2. Digite na barra de endereco:
echo.
echo      http://SEU-IP-ACIMA:8001
echo.
echo   Exemplo: http://192.168.1.50:8001
echo.
echo   Obs: este PC precisa estar com o
echo   servidor iniciado (iniciar_servidor.bat)
echo  ==========================================
echo.
pause
