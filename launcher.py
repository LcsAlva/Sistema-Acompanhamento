"""
Ponto de entrada do executável URFCC.
- Ajusta caminhos para modo PyInstaller
- Abre o navegador automaticamente
- Inicia o servidor Uvicorn
"""
import sys
import os
import threading
import webbrowser
import time

# ── Ajusta diretório de trabalho ─────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # Rodando como .exe
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(APP_DIR)

# ── Abre o navegador após 2.5 segundos ───────────────────────────────────────
def _abrir_navegador():
    time.sleep(2.5)
    webbrowser.open("http://localhost:8001")

threading.Thread(target=_abrir_navegador, daemon=True).start()

# ── Inicia o servidor ────────────────────────────────────────────────────────
import uvicorn
from backend.main import app

print()
print("  ETM Engenharia - Sistema URFCC")
print("  ================================")
print("  Acesse: http://localhost:8001")
print("  O navegador abrira automaticamente.")
print("  Feche esta janela para encerrar.")
print()

uvicorn.run(app, host="127.0.0.1", port=8001)
