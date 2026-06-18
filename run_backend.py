"""Wrapper para iniciar o backend garantindo o diretório correto."""
import sys
import os

# Garante que o diretório do projeto está no sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.chdir(PROJECT_DIR)

print(f"CWD: {os.getcwd()}", flush=True)
print(f"sys.path[0]: {sys.path[0]}", flush=True)

# Import app directly to verify correct loading
from backend.main import app
routes_with_api = [r.path for r in app.routes if hasattr(r, 'path') and '/api/' in r.path]
print(f"Routes with /api: {routes_with_api[:5]}", flush=True)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
