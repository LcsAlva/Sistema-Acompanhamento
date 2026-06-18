from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sys
import os

# Quando rodando como .exe (PyInstaller), usa o diretório do executável
# Quando rodando normalmente, usa a raiz do projeto
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'banco.db')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Habilita WAL (Write-Ahead Logging) para permitir leituras concorrentes
# durante escritas — reduz deadlocks quando múltiplos usuários acessam
# o sistema simultaneamente (ex.: importação de XER + visualização).
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency FastAPI: fornece sessão com rollback automático em exceção.

    O rollback em except garante que uma exceção não-tratada dentro de um
    endpoint nunca persiste dados parcialmente gravados. O commit explícito
    nos services continua sendo obrigatório — este é apenas o safety net.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
