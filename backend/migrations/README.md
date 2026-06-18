# Migrações Alembic — URFCC

A partir desta versão o schema do banco é versionado por Alembic. As
ALTER TABLEs ad-hoc do `main.py` permanecem só como rede de segurança
para bancos antigos; novas alterações devem ser feitas via Alembic.

## Comandos básicos

```bash
# Gerar migração após editar models.py
alembic revision --autogenerate -m "descrição curta"

# Aplicar migrações pendentes
alembic upgrade head

# Reverter última migração
alembic downgrade -1

# Marcar banco existente como já no head sem aplicar nada
alembic stamp head
```

## Bancos existentes

Para bancos que já tinham o schema antes da adoção do Alembic:

```bash
alembic stamp head
```

Isso cria a tabela `alembic_version` apontando para a migração mais
recente, sem rodar SQL. As migrações futuras tomam o curso normal.

## Por que `render_as_batch=True` em `env.py`

SQLite não suporta a maioria dos `ALTER TABLE` (drop column, alter
type). Alembic em modo "batch" recria a tabela de forma transparente.
