from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging
import os

from .database import engine, Base  # noqa: F401 — engine importado para compatibilidade PyInstaller
from .models import (
    Tarefa, Semana, ProgramacaoSemanal, RelatorioSemana, Import, Usuario, SubTarefa,
    PainelSnapshot, PainelFaseSemana, EapItem, TarefaEapLink, EapPrevisaoMensal,
    EapAvancoSemanal, CicloMedicao, LancamentoMedicao, DocumentoEngenharia, FotoMedicao,
    # Módulo BM refatorado
    BmCiclo, BmSnapshotPrevisao, BmLancamento, BmVersao, BmConsolidado,
    BmPendencia, BmPendenciaRedistrib, BmLog,
    # Engine de Competência Financeira
    CompetenciaFinanceira, CompetenciaLog,
    # Fase 2A — Sistema de Medição Petrobras (Integração LD/SIGEM + Critérios)
    CriterioMedicao, LdDocumento, LdHistoricoStatus, SigemDocumento, SigemHistoricoStatus,
    DocumentoRevisao, ControleDocumento, EventoRevisaoDocumento,
    # Módulo Produção (cronograma XER)
    ProdProjeto, ProdWbs, ProdAtividade,
    EconomicoImportacao, EconomicoValor, EconomicoAuditoria,
)
from .routers import (
    tarefas, semanas, imports, relatorio, clima, sub_tarefas, painel, eap,
    documentos, fotos, bm, export, competencias,
    criterios, ld, medicao_engenharia, sigem, revisoes, producao, economico, performance,
    suportes,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA: gerenciado EXCLUSIVAMENTE pelo Alembic.
# NÃO usar Base.metadata.create_all() aqui — isso bypassa migrações e pode
# criar tabelas sem as constraints/índices/defaults definidos em Alembic.
# Para inicializar ou atualizar o banco: alembic upgrade head
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sistema de Programação Semanal URFCC",
    description="ETM Engenharia | Petrobras URFCC - Backend API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tarefas.router, prefix="/api")
app.include_router(semanas.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(relatorio.router, prefix="/api")
app.include_router(clima.router, prefix="/api")
app.include_router(sub_tarefas.router, prefix="/api")
app.include_router(painel.router, prefix="/api")
app.include_router(eap.router, prefix="/api")
app.include_router(documentos.router, prefix="/api")
app.include_router(fotos.router, prefix="/api")
app.include_router(bm.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(competencias.router, prefix="/api")
# Fase 2A — Sistema de Medição Petrobras
app.include_router(criterios.router, prefix="/api")
app.include_router(ld.router, prefix="/api")
app.include_router(sigem.router, prefix="/api")
app.include_router(medicao_engenharia.router, prefix="/api")
app.include_router(revisoes.router, prefix="/api")
# Módulo Produção (cronograma XER)
app.include_router(producao.router, prefix="/api")
app.include_router(economico.router, prefix="/api")
app.include_router(performance.router, prefix="/api")
app.include_router(suportes.router, prefix="/api")

# Diretório de uploads (fotos do relatório fotográfico)
_UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(os.path.join(_UPLOADS_DIR, "fotos"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")

# Health endpoint must be registered before the SPA catch-all
@app.get("/api/health", tags=["sistema"])
def health_check():
    return {"status": "ok", "sistema": "Programação Semanal URFCC"}

# Serve o frontend React compilado
# Quando rodando como .exe (PyInstaller), os arquivos estão em _internal/frontend/dist
# Quando rodando normalmente, estão em frontend/dist relativo à raiz do projeto
import sys as _sys
if getattr(_sys, 'frozen', False):
    _BASE = os.path.dirname(_sys.executable)
    FRONTEND_DIR = os.path.join(_BASE, "_internal", "frontend", "dist")
    if not os.path.isdir(FRONTEND_DIR):
        FRONTEND_DIR = os.path.join(_BASE, "frontend", "dist")
else:
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/suportes", include_in_schema=False)
    def serve_suportes():
        suportes_html = os.path.join(FRONTEND_DIR, "suportes.html")
        if os.path.isfile(suportes_html):
            return FileResponse(suportes_html)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/pedidos-suporte", include_in_schema=False)
    def serve_pedidos_suporte():
        suportes_html = os.path.join(FRONTEND_DIR, "suportes.html")
        if os.path.isfile(suportes_html):
            return FileResponse(suportes_html)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/pedidos-material", include_in_schema=False)
    def serve_pedidos_material():
        suportes_html = os.path.join(FRONTEND_DIR, "suportes.html")
        if os.path.isfile(suportes_html):
            return FileResponse(suportes_html)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/analise-revisoes", include_in_schema=False)
    def serve_analise_revisoes():
        analise_html = os.path.join(FRONTEND_DIR, "analise-revisoes.html")
        if os.path.isfile(analise_html):
            return FileResponse(analise_html)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        # Não interceptar rotas da API — deixar o 404 normal do FastAPI
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Rota de API não encontrada")
        # SPA fallback - serve index.html para rotas do React Router
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    @app.get("/", include_in_schema=False)
    def root():
        return {
            "mensagem": "Backend URFCC rodando",
            "docs": "/docs",
            "status": "Frontend ainda não compilado - acesse /docs para testar a API",
        }
