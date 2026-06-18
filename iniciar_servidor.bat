@echo off

REM Reabre em janela persistente
if "%1"=="__RODANDO__" goto :MAIN
start "" cmd /k "%~f0" __RODANDO__
exit

:MAIN
title Sistema URFCC - Servidor
cd /d "%~dp0"

echo.
echo  ETM Engenharia - Programacao Semanal URFCC
echo  ============================================
echo.
echo  Servidor iniciado!
echo  Acesse: http://localhost:8001
echo.
echo  Ctrl+C para encerrar
echo.

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001

echo.
echo  Servidor encerrado.
pause
