@echo off
if "%1"=="__RODANDO__" goto :MAIN
start "" cmd /k "%~f0" __RODANDO__
exit

:MAIN
title URFCC COMPLETO - Dev (porta 8002 / 5176)
cd /d "%~dp0"

echo.
echo  ============================================
echo   URFCC COMPLETO - Ambiente de Desenvolvimento
echo   Backend  : http://localhost:8002
echo   Frontend : http://localhost:5176
echo  ============================================
echo.

REM ── Inicia o backend em segundo plano ─────────────────────────────────────
echo  Iniciando backend na porta 8002...
start "URFCC-COMPLETO Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --reload --host localhost --port 8002"

REM Aguarda o backend subir
timeout /t 3 /nobreak >nul

REM ── Inicia o frontend ──────────────────────────────────────────────────────
echo  Iniciando frontend na porta 5176...
cd frontend
call npm run dev

pause
