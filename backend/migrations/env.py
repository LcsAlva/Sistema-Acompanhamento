"""Alembic environment — usa o engine e o Base do projeto.

Mantém a compatibilidade com o caminho dinâmico do banco usado pelo
PyInstaller (banco.db ao lado do .exe). Em vez de ler a URL do
alembic.ini, importa diretamente o `engine` configurado em
backend.database.
"""
from logging.config import fileConfig

from alembic import context

from backend.database import engine, Base
# Importa todos os models para que o autogenerate enxergue todas as tabelas.
from backend import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo offline: gera SQL sem conexão ativa."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite — ALTER TABLE em modo batch
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: usa o engine real."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
