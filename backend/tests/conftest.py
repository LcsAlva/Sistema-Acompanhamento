"""Fixtures de teste — SQLite in-memory.

Cada teste recebe uma sessão limpa e isolada. Não tocamos no banco
de produção; o engine usado aqui é construído à parte para a URI
"sqlite:///:memory:".
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
# Garante que todos os models são registrados no metadata antes do create_all.
from backend import models  # noqa: F401


@pytest.fixture
def db():
    """Session com schema fresco para cada teste."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    sess = Session()
    try:
        yield sess
    finally:
        sess.close()
        engine.dispose()
