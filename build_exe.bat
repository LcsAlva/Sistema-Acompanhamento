@echo off

REM Reabre em janela persistente
if "%1"=="__RODANDO__" goto :MAIN
start "" cmd /k "%~f0" __RODANDO__
exit

:MAIN
title Gerando executavel URFCC
cd /d "%~dp0"

echo.
echo  ============================================
echo   Gerando executavel URFCC
echo   ETM Engenharia
echo  ============================================
echo.

REM ── Instala PyInstaller se necessario ────────────────────────────────────
python -c "import PyInstaller" >nul 2>&1
if %errorLevel% neq 0 (
    echo  Instalando PyInstaller...
    python -m pip install pyinstaller
    if %errorLevel% neq 0 (
        echo.
        echo  [ERRO] Nao foi possivel instalar o PyInstaller.
        pause
        exit /b 1
    )
)

REM ── Remove build anterior ─────────────────────────────────────────────────
echo  Limpando build anterior...
if exist "dist\URFCC" rmdir /s /q "dist\URFCC"
if exist "build\URFCC" rmdir /s /q "build\URFCC"

REM ── Gera o executavel ─────────────────────────────────────────────────────
echo  Gerando executavel (pode demorar 2-3 minutos)...
echo.
python -m PyInstaller URFCC.spec --noconfirm

if %errorLevel% neq 0 (
    echo.
    echo  [ERRO] Falha ao gerar o executavel. Veja o erro acima.
    pause
    exit /b 1
)

REM ── Copia o banco de dados para a pasta dist ──────────────────────────────
if exist "banco.db" (
    echo  Copiando banco de dados...
    copy /y "banco.db" "dist\URFCC\banco.db" >nul
)

echo.
echo  ============================================
echo   Executavel gerado com sucesso!
echo.
echo   Pasta: dist\URFCC\
echo   Arquivo: dist\URFCC\URFCC.exe
echo.
echo   Para distribuir: copie a pasta dist\URFCC\
echo   inteira para onde quiser.
echo   Clique duas vezes em URFCC.exe para abrir.
echo  ============================================
echo.
pause
