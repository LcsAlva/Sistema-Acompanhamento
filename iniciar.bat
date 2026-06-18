@echo off
title Sistema de Programacao Semanal - URFCC
echo ==========================================
echo  ETM Engenharia - Programacao Semanal
echo  URFCC / Petrobras
echo ==========================================
echo.
echo Iniciando servidor...
cd /d "%~dp0"
start "" http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
