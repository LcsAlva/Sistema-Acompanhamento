import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from backend.main import app
import uvicorn

uvicorn.run(app, host='0.0.0.0', port=8004, log_level='info')
