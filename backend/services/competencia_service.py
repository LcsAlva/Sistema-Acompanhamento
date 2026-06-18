"""Engine de Competência Financeira — camada de governança por mês.

════════════════════════════════════════════════════════════════════════════════
RESPONSABILIDADE
════════════════════════════════════════════════════════════════════════════════
  Controla o ciclo de vida formal de cada competência financeira (ano/mês):
  criação automática, máquina de estados, lock temporal e auditoria.

════════════════════════════════════════════════════════════════════════════════
MÁQUINA DE ESTADOS
════════════════════════════════════════════════════════════════════════════════
  aberta → em_apuracao → fechada → consolidada → encerrada_contabilmente

  Regras:
  - Não é possível retroceder após 'fechada'
  - 'encerrada_contabilmente' seta locked=True automaticamente
  - locked=True bloqueia qualquer alteração independentemente do status

════════════════════════════════════════════════════════════════════════════════
INVARIANTES
════════════════════════════════════════════════════════════════════════════════
  • Não importa lógica do bm_service — sem dependência circular
  • auto-criação via get_or_create_competencia() — transparente ao chamador
  • assert_competencia_editavel() é o ponto único de verificação de lock
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models import CompetenciaFinanceira, CompetenciaLog

logger = logging.getLogger(__name__)

# ── Constantes de status ──────────────────────────────────────────────────────

STATUS_ABERTA      = "aberta"
STATUS_EM_APURACAO = "em_apuracao"
STATUS_FECHADA     = "fechada"
STATUS_CONSOLIDADA = "consolidada"
STATUS_ENCERRADA   = "encerrada_contabilmente"

STATUS_EDITAVEL = {STATUS_ABERTA, STATUS_EM_APURACAO}
STATUS_TERMINAL = {STATUS_ENCERRADA}

# Transições permitidas — sem retorno após fechada
TRANSICOES: dict[str, list[str]] = {
    STATUS_ABERTA:      [STATUS_EM_APURACAO],
    STATUS_EM_APURACAO: [STATUS_FECHADA],
    STATUS_FECHADA:     [STATUS_CONSOLIDADA],
    STATUS_CONSOLIDADA: [STATUS_ENCERRADA],
    STATUS_ENCERRADA:   [],
}

STATUS_LABEL = {
    STATUS_ABERTA:      "Aberta",
    STATUS_EM_APURACAO: "Em Apuração",
    STATUS_FECHADA:     "Fechada",
    STATUS_CONSOLIDADA: "Consolidada",
    STATUS_ENCERRADA:   "Encerrada Contabilmente",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Core: criação e consulta ──────────────────────────────────────────────────

def get_competencia(
    db: Session,
    ano: int,
    mes: int,
) -> Optional[CompetenciaFinanceira]:
    """Retorna a competência do mês ou None se não existir."""
    return (
        db.query(CompetenciaFinanceira)
        .filter(CompetenciaFinanceira.ano == ano, CompetenciaFinanceira.mes == mes)
        .first()
    )


def get_or_create_competencia(
    db: Session,
    ano: int,
    mes: int,
    criado_por: Optional[str] = None,
) -> CompetenciaFinanceira:
    """Retorna competência existente ou cria uma nova como 'aberta'.

    Chamada transparentemente por operações do BM para garantir que a
    competência sempre exista antes de qualquer operação financeira.
    NÃO faz commit — o chamador é responsável pelo commit.
    """
    comp = get_competencia(db, ano, mes)
    if comp:
        return comp

    agora = _utcnow()
    comp = CompetenciaFinanceira(
        ano=ano,
        mes=mes,
        status=STATUS_ABERTA,
        locked=False,
        aberto_em=agora,
        aberto_por=criado_por,
    )
    db.add(comp)
    db.flush()  # garante id para o log

    _log(db, comp, "COMPETENCIA_CRIADA",
         status_antes=None, status_depois=STATUS_ABERTA,
         usuario=criado_por,
         observacao=f"Criada automaticamente para {ano}/{mes:02d}")
    return comp


def criar_competencia_manual(
    db: Session,
    ano: int,
    mes: int,
    criado_por: Optional[str] = None,
    observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    """Cria competência manualmente via endpoint.

    Falha se já existir — use get_or_create para criação idempotente.
    Faz commit.
    """
    existente = get_competencia(db, ano, mes)
    if existente:
        raise ValueError(
            f"Competência {ano}/{mes:02d} já existe com status "
            f"'{STATUS_LABEL.get(existente.status, existente.status)}'."
        )

    agora = _utcnow()
    comp = CompetenciaFinanceira(
        ano=ano, mes=mes,
        status=STATUS_ABERTA,
        locked=False,
        aberto_em=agora,
        aberto_por=criado_por,
        observacao=observacao,
    )
    db.add(comp)
    db.flush()

    _log(db, comp, "COMPETENCIA_ABERTA",
         status_antes=None, status_depois=STATUS_ABERTA,
         usuario=criado_por, observacao=observacao)
    db.commit()
    db.refresh(comp)
    return comp


# ── Core: assert de editabilidade ────────────────────────────────────────────

def assert_competencia_editavel(
    db: Session,
    ano: int,
    mes: int,
) -> None:
    """Verifica se a competência do mês permite alterações financeiras.

    Raises:
        ValueError: se a competência estiver locked ou em status não-editável.

    Comportamento por cenário:
      - Não existe:        OK (implicitamente aberta; será criada ao operar)
      - aberta:            OK
      - em_apuracao:       OK
      - fechada:           BLOQUEADO
      - consolidada:       BLOQUEADO
      - encerrada:         BLOQUEADO
      - locked=True:       BLOQUEADO (independente do status)
    """
    comp = get_competencia(db, ano, mes)
    if comp is None:
        return  # sem competência = aberta implicitamente

    if comp.locked:
        raise ValueError(
            f"A competência {mes:02d}/{ano} está bloqueada (locked) para "
            "alterações financeiras. Contate o responsável contábil."
        )

    if comp.status not in STATUS_EDITAVEL:
        label = STATUS_LABEL.get(comp.status, comp.status)
        raise ValueError(
            f"A competência {mes:02d}/{ano} está '{label}' e não permite "
            "alterações financeiras. "
            "Apenas competências 'Abertas' ou 'Em Apuração' aceitam movimentos."
        )


# ── Máquina de estados ────────────────────────────────────────────────────────

def transicionar_competencia(
    db: Session,
    ano: int,
    mes: int,
    novo_status: str,
    usuario: Optional[str] = None,
    observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    """Transiciona a competência para novo_status respeitando a máquina de estados.

    Cria a competência automaticamente se não existir (apenas para o status inicial).
    Faz commit ao final.

    Raises:
        ValueError: se a transição não for permitida ou a competência estiver locked.
    """
    if novo_status not in STATUS_LABEL:
        raise ValueError(
            f"Status '{novo_status}' inválido. "
            f"Opções: {list(STATUS_LABEL.keys())}"
        )

    comp = get_competencia(db, ano, mes)

    # Auto-cria como aberta se não existir e a transição parte de aberta
    if comp is None:
        if novo_status != STATUS_ABERTA:
            raise ValueError(
                f"Competência {ano}/{mes:02d} não existe. "
                f"Crie-a primeiro via POST /api/competencias/{ano}/{mes}/abrir."
            )
        return criar_competencia_manual(db, ano, mes, criado_por=usuario,
                                        observacao=observacao)

    if comp.locked:
        raise ValueError(
            f"Competência {ano}/{mes:02d} está bloqueada (locked) — "
            "nenhuma transição de status é permitida."
        )

    # Verifica transição válida
    permitidos = TRANSICOES.get(comp.status, [])
    if novo_status not in permitidos:
        raise ValueError(
            f"Transição inválida: '{comp.status}' → '{novo_status}'. "
            f"Próximos estados permitidos: {permitidos or ['nenhum (status terminal)']}"
        )

    status_anterior = comp.status
    agora = _utcnow()

    # Aplica transição e preenche campo rastreável
    comp.status     = novo_status
    comp.updated_at = agora
    if observacao:
        comp.observacao = observacao

    if novo_status == STATUS_EM_APURACAO:
        comp.em_apuracao_em  = agora
        comp.em_apuracao_por = usuario
    elif novo_status == STATUS_FECHADA:
        comp.fechado_em  = agora
        comp.fechado_por = usuario
    elif novo_status == STATUS_CONSOLIDADA:
        comp.consolidado_em  = agora
        comp.consolidado_por = usuario
    elif novo_status == STATUS_ENCERRADA:
        comp.encerrado_em  = agora
        comp.encerrado_por = usuario
        comp.locked = True   # encerramento sempre aplica lock

    _log(db, comp,
         evento=f"COMPETENCIA_{novo_status.upper()}",
         status_antes=status_anterior,
         status_depois=novo_status,
         usuario=usuario,
         observacao=observacao)

    db.commit()
    db.refresh(comp)
    return comp


# ── Conveniências por ação ────────────────────────────────────────────────────

def abrir_competencia(
    db: Session, ano: int, mes: int,
    usuario: Optional[str] = None, observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    return criar_competencia_manual(db, ano, mes, criado_por=usuario,
                                    observacao=observacao)


def mover_para_em_apuracao(
    db: Session, ano: int, mes: int,
    usuario: Optional[str] = None, observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    return transicionar_competencia(db, ano, mes, STATUS_EM_APURACAO,
                                    usuario=usuario, observacao=observacao)


def fechar_competencia(
    db: Session, ano: int, mes: int,
    usuario: Optional[str] = None, observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    return transicionar_competencia(db, ano, mes, STATUS_FECHADA,
                                    usuario=usuario, observacao=observacao)


def consolidar_competencia(
    db: Session, ano: int, mes: int,
    usuario: Optional[str] = None, observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    return transicionar_competencia(db, ano, mes, STATUS_CONSOLIDADA,
                                    usuario=usuario, observacao=observacao)


def encerrar_competencia(
    db: Session, ano: int, mes: int,
    usuario: Optional[str] = None, observacao: Optional[str] = None,
) -> CompetenciaFinanceira:
    """Encerra a competência contabilmente e aplica lock permanente."""
    return transicionar_competencia(db, ano, mes, STATUS_ENCERRADA,
                                    usuario=usuario, observacao=observacao)


def listar_competencias(
    db: Session,
    status: Optional[str] = None,
    ano: Optional[int] = None,
) -> list[CompetenciaFinanceira]:
    """Lista competências com filtros opcionais."""
    q = db.query(CompetenciaFinanceira)
    if status:
        q = q.filter(CompetenciaFinanceira.status == status)
    if ano:
        q = q.filter(CompetenciaFinanceira.ano == ano)
    return q.order_by(CompetenciaFinanceira.ano.desc(),
                      CompetenciaFinanceira.mes.desc()).all()


# ── Auditoria ─────────────────────────────────────────────────────────────────

def _log(
    db: Session,
    comp: CompetenciaFinanceira,
    evento: str,
    status_antes: Optional[str],
    status_depois: Optional[str],
    usuario: Optional[str] = None,
    observacao: Optional[str] = None,
) -> None:
    db.add(CompetenciaLog(
        competencia_id=comp.id,
        evento=evento,
        status_antes=status_antes,
        status_depois=status_depois,
        usuario=usuario,
        observacao=observacao,
    ))
