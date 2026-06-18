"""Endpoints da EAP Financeira.

Cobre as 4 fases do plano:
  Fase 1 — POST /eap/importar, GET /eap/itens, GET /eap/curva-prevista
  Fase 2 — GET/POST /eap/links, POST /eap/auto-mapear
  Fase 3 — GET /eap/curva-realizada, GET /eap/kpis/{semana}
  Fase 4 — GET /eap/medicao/{ano}/{mes}  (boletim)
"""
from __future__ import annotations

import io
import json
import logging
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..utils.validators import normalize_pct_100
from ..services.competencia_service import assert_competencia_editavel
from ..services.bm_service import previsto_fases_lb_eap_j
from ..models import (
    EapItem, EapPrevisaoMensal, EapAvancoSemanal,
    ProgramacaoSemanal, Semana, Tarefa, TarefaEapLink,
)
from ..parsers.eap_parser import parse_eap_xlsx
from ..services.eap_integrity import sintetizar_intermediarios, checar_integridade
from ..utils.gerar_eap_pdf import gerar_eap_pdf
from ..schemas import (
    AutoMapearSugestao,
    CicloMedicaoOut,
    CurvaPonto,
    EapAvancoBulk, EapAvancoOut,
    EapImportResultado,
    EapItemMedicaoOut,
    EapItemOut, EapItemUpdate, EapAtividadeManualIn,
    EapAdiantarIn,
    EapPrevisaoBulk, EapPrevisaoOut,
    EvmKpis,
    LancamentoBulk,
    MedicaoItemOut,
    MedicaoMesOut,
    TarefaEapLinkBase,
    TarefaEapLinkOut,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eap", tags=["eap"])


# ── Helpers ─────────────────────────────────────────────────────────────

def _eap_to_out(item: EapItem) -> dict:
    """Converte EapItem ORM em dict pro schema EapItemOut, parseando JSON."""
    dist = None
    if item.dist_mensal:
        try:
            dist = json.loads(item.dist_mensal)
        except json.JSONDecodeError:
            dist = None
    return {
        'id': item.id,
        'codigo': item.codigo,
        'descricao': item.descricao,
        'nivel': item.nivel,
        'parent_codigo': item.parent_codigo,
        'valor': item.valor or 0.0,
        'dist_mensal': dist,
    }


_MES_PT = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
           7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}


def _label_mes(iso: str) -> str:
    """De '2025-08-01' -> 'ago/25'."""
    d = date.fromisoformat(iso)
    return f"{_MES_PT[d.month]}/{str(d.year)[2:]}"


def _bac(db: Session) -> float:
    """Budget at Completion = soma dos itens de NÍVEL 1 (entregas top-level).

    Por que nível 1 e não folhas: a EAP da Petrobras tem códigos duplicados
    em folhas (32 deles, com valores diferentes — diferentes revisões/agrupa-
    mentos da mesma planilha). Já o nível 1 é a hierarquia limpa do contrato
    e sua soma bate com o "CONTRATO" declarado no cabeçalho.
    """
    total = (
        db.query(func.sum(EapItem.valor))
        .filter(EapItem.nivel == 1)
        .scalar()
    ) or 0.0
    return float(total)


def _curva_prevista_mensal(db: Session) -> list[CurvaPonto]:
    """Constrói a curva-S financeira prevista a partir das distribuições
    mensais dos itens de NÍVEL 1.

    Por que nível 1: cada entrega nível 1 já carrega a distribuição mensal
    agregada de toda sua sub-hierarquia. Somar nível 1 evita o problema de
    códigos-folha duplicados na planilha (32 ocorrências).
    """
    itens = (
        db.query(EapItem)
        .filter(EapItem.dist_mensal.isnot(None))
        .filter(EapItem.nivel == 1)
        .all()
    )
    por_mes: dict[str, float] = {}
    for it in itens:
        try:
            dist = json.loads(it.dist_mensal or '{}')
        except json.JSONDecodeError:
            continue
        for iso, valor_mes in dist.items():
            por_mes[iso] = por_mes.get(iso, 0.0) + float(valor_mes)

    if not por_mes:
        return []

    # Ordena por data e calcula acumulado
    pontos: list[CurvaPonto] = []
    pv_acum = 0.0
    for iso in sorted(por_mes):
        pv_acum += por_mes[iso]
        pontos.append(CurvaPonto(
            label=_label_mes(iso),
            data=iso,
            pv_mes=round(por_mes[iso], 2),
            ev_mes=0.0,
            pv_acum=round(pv_acum, 2),
            ev_acum=0.0,
        ))
    return pontos


def _ev_por_tarefa(db: Session) -> dict[int, float]:
    """Para cada tarefa com link à EAP, calcula o EV (R$ ganhos):

      EV_tarefa = pct_avanco_max_progs / 100 * Σ(valor_eap × peso)

    pct_avanco_max é o melhor avanço lançado em qualquer ProgramacaoSemanal
    daquela tarefa (entre as semanas).
    """
    # Pega o melhor pct conhecido por tarefa (pct_executado || pct_avanco)
    progs = (
        db.query(
            ProgramacaoSemanal.tarefa_id,
            func.max(
                func.coalesce(ProgramacaoSemanal.pct_executado,
                              ProgramacaoSemanal.pct_avanco, 0.0)
            ).label('pct_max'),
        )
        .group_by(ProgramacaoSemanal.tarefa_id)
        .all()
    )
    pct_por_tarefa = {p.tarefa_id: float(p.pct_max or 0) for p in progs}

    # Soma valor*peso da EAP por tarefa
    links = (
        db.query(TarefaEapLink.tarefa_id, EapItem.valor, TarefaEapLink.peso)
        .join(EapItem, EapItem.codigo == TarefaEapLink.eap_codigo)
        .all()
    )
    valor_por_tarefa: dict[int, float] = {}
    for tid, valor, peso in links:
        valor_por_tarefa[tid] = valor_por_tarefa.get(tid, 0.0) + (valor or 0.0) * (peso or 1.0)

    return {
        tid: (pct_por_tarefa.get(tid, 0.0) / 100.0) * v
        for tid, v in valor_por_tarefa.items()
    }


# ── Fase 1 — Importação e listagem ──────────────────────────────────────

@router.post("/importar", response_model=EapImportResultado)
async def importar_eap(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Lê o XLSX da EAP financeira e popula `eap_item` (substitui o anterior)."""
    conteudo = await file.read()
    try:
        itens, meses = parse_eap_xlsx(io.BytesIO(conteudo))
    except Exception as e:
        logger.exception("Erro ao parsear EAP")
        raise HTTPException(422, f"Erro ao ler XLSX da EAP: {e}")

    if not itens:
        raise HTTPException(422, "Nenhum item encontrado na aba 'EAP'.")

    # ── Integridade hierárquica: sintetiza nós-pai intermediários ausentes ────
    # A planilha-fonte omite linhas-resumo de nível intermediário (ex.: existe
    # '1.3.4.12' mas não '1.3.4'). Sem o pai, a subárvore fica órfã e seu valor
    # não rola para o nível 1. Sintetizamos recursivamente (valor = Σ filhos).
    itens, sintetizados = sintetizar_intermediarios(itens)

    # ── GATE: após a síntese, a EAP deve estar 100% íntegra ───────────────────
    integridade = checar_integridade(itens)
    if not integridade["ok"]:
        raise HTTPException(
            422,
            "EAP rejeitada: integridade hierárquica não pôde ser garantida mesmo "
            "após síntese de intermediários. "
            f"Nós-pai ainda ausentes: {integridade['orfaos'][:20]}. "
            f"Itens sem cadeia até o nível 1: {integridade['quebrados'][:20]}. "
            "Corrija a EAP de origem (linhas-resumo faltantes) e reimporte.",
        )

    valor_total = 0.0
    folhas_set = {it['codigo'] for it in itens}
    pais_set = {it['parent_codigo'] for it in itens if it['parent_codigo']}
    folhas_qtd = len(folhas_set - pais_set)

    try:
        # ── Upsert: atualiza existentes, insere novos, remove os que sumiram ──
        # Evita DELETE em massa que viola FK constraints (foreign_keys=ON).
        existing: dict[str, EapItem] = {
            it.codigo: it for it in db.query(EapItem).all()
        }
        new_codes = {it['codigo'] for it in itens}

        # Remove itens que não existem mais na nova EAP (sem refs em outras tabelas)
        for codigo, obj in existing.items():
            if codigo not in new_codes:
                try:
                    db.delete(obj)
                    db.flush()
                except Exception:
                    db.expunge(obj)   # ignora se houver FK pendente
                    db.rollback()

        # Upsert
        for it in itens:
            dist_json = json.dumps(it['dist_mensal']) if it['dist_mensal'] else None
            if it['codigo'] in existing:
                obj = existing[it['codigo']]
                obj.descricao   = it['descricao']
                obj.nivel       = it['nivel']
                obj.parent_codigo = it['parent_codigo']
                obj.valor       = it['valor']
                obj.dist_mensal = dist_json
            else:
                db.add(EapItem(
                    codigo        = it['codigo'],
                    descricao     = it['descricao'],
                    nivel         = it['nivel'],
                    parent_codigo = it['parent_codigo'],
                    valor         = it['valor'],
                    dist_mensal   = dist_json,
                ))
            if it['codigo'] not in pais_set:
                valor_total += it['valor']

        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception("Erro ao salvar EAP no banco")
        raise HTTPException(500, f"Erro ao salvar EAP: {type(e).__name__}: {e}")

    return EapImportResultado(
        itens_total=len(itens),
        itens_folha=folhas_qtd,
        valor_total=round(valor_total, 2),
        meses=meses,
        intermediarios_sintetizados=len(sintetizados),
        codigos_sintetizados=sorted(s['codigo'] for s in sintetizados),
    )


@router.get("/itens")
def listar_itens(
    q: Optional[str] = None,
    nivel: Optional[int] = None,
    so_folhas: bool = False,
    parent: Optional[str] = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    """Lista itens da EAP. Suporta filtros por busca, nível, parent e folhas."""
    query = db.query(EapItem)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (func.lower(EapItem.descricao).like(like)) | (EapItem.codigo.like(f"{q}%"))
        )
    if nivel is not None:
        query = query.filter(EapItem.nivel == nivel)
    if parent is not None:
        query = query.filter(EapItem.parent_codigo == parent)
    if so_folhas:
        # Folhas = itens cujo codigo NÃO é parent_codigo de nenhum outro
        sub = db.query(EapItem.parent_codigo).filter(EapItem.parent_codigo.isnot(None))
        query = query.filter(~EapItem.codigo.in_(sub))
    itens = query.order_by(EapItem.codigo).limit(limit).all()
    return [_eap_to_out(i) for i in itens]


@router.get("/curva-prevista", response_model=list[CurvaPonto])
def curva_prevista(db: Session = Depends(get_db)):
    """Curva-S financeira prevista (mensal acumulada)."""
    return _curva_prevista_mensal(db)


# ── Fase 2 — Mapeamento Tarefa ↔ EAP ────────────────────────────────────

@router.get("/links", response_model=list[TarefaEapLinkOut])
def listar_links(tarefa_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(TarefaEapLink)
    if tarefa_id is not None:
        q = q.filter(TarefaEapLink.tarefa_id == tarefa_id)
    return q.all()


@router.post("/links", response_model=TarefaEapLinkOut, status_code=201)
def criar_link(payload: TarefaEapLinkBase, db: Session = Depends(get_db)):
    if not db.query(Tarefa).filter(Tarefa.id == payload.tarefa_id).first():
        raise HTTPException(404, "Tarefa não encontrada")
    if not db.query(EapItem).filter(EapItem.codigo == payload.eap_codigo).first():
        raise HTTPException(404, "Item EAP não encontrado")
    link = TarefaEapLink(**payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/links/{link_id}", status_code=204)
def remover_link(link_id: int, db: Session = Depends(get_db)):
    link = db.query(TarefaEapLink).filter(TarefaEapLink.id == link_id).first()
    if not link:
        raise HTTPException(404, "Link não encontrado")
    db.delete(link)
    db.commit()


@router.post("/auto-mapear", response_model=list[AutoMapearSugestao])
def auto_mapear(
    top_n: int = 3,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """Sugere mapeamentos por similaridade de descrição (Tarefa.nome ↔ EapItem.descricao).

    Para evitar custo O(N×M) inviável (com 3000 tarefas × 1100 folhas),
    fazemos pré-filtro por **bag of words**: só passa pro algoritmo de
    similaridade os itens-folha que compartilham pelo menos 1 palavra
    com a descrição da tarefa. Retorna top_n por tarefa, processando até
    `limit` tarefas por chamada (paginar do lado do frontend se precisar).
    """
    sub = db.query(EapItem.parent_codigo).filter(EapItem.parent_codigo.isnot(None))
    folhas = db.query(EapItem).filter(~EapItem.codigo.in_(sub)).all()

    # Indexa folhas por palavra (palavra → set de codigos)
    palavra_index: dict[str, set[str]] = {}
    folha_por_codigo: dict[str, EapItem] = {}
    folha_palavras: dict[str, set[str]] = {}
    for item in folhas:
        folha_por_codigo[item.codigo] = item
        words = {w for w in (item.descricao or '').lower().split() if len(w) > 3}
        folha_palavras[item.codigo] = words
        for w in words:
            palavra_index.setdefault(w, set()).add(item.codigo)

    ja_linkadas = {t for (t,) in db.query(TarefaEapLink.tarefa_id).distinct()}
    tarefas = (
        db.query(Tarefa)
        .filter(~Tarefa.id.in_(ja_linkadas) if ja_linkadas else True)
        .limit(limit)
        .all()
    )

    sugestoes: list[AutoMapearSugestao] = []
    for tar in tarefas:
        nome = (tar.nome or '').lower().strip()
        if not nome:
            continue
        tar_words = {w for w in nome.split() if len(w) > 3}
        # Candidatos: união dos códigos cujas palavras intersectam
        candidatos: set[str] = set()
        for w in tar_words:
            candidatos |= palavra_index.get(w, set())
        if not candidatos:
            continue
        scored = []
        for cod in candidatos:
            item = folha_por_codigo[cod]
            desc = (item.descricao or '').lower()
            score = SequenceMatcher(None, nome, desc).ratio()
            if score >= 0.4:
                scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        top = [
            {'eap_codigo': it.codigo, 'descricao': it.descricao,
             'valor': it.valor or 0.0, 'score': round(s, 3)}
            for s, it in scored[:top_n]
        ]
        if top:
            sugestoes.append(AutoMapearSugestao(
                tarefa_id=tar.id,
                activity_id=tar.activity_id,
                nome=tar.nome or '—',
                sugestoes=top,
            ))
    return sugestoes


# ── Fase 3 — Curva realizada e KPIs EVM ─────────────────────────────────

def _ev_por_mes(db: Session) -> dict[str, float]:
    """Distribui o EV mensalmente a partir dos AVANÇOS lançados direto
    na EAP (fonte de verdade do BM da Petrobras).

    Para cada `EapAvancoSemanal`, usa a `data_fim` da semana (1º dia do
    mês como bucket) e calcula `pct_delta × valor_item / 100`. Itens sem
    semana correspondente caem no mês corrente.

    Quando NÃO há avanços lançados (ex.: importou EAP mas ainda não
    começou a medir), faz fallback para o cálculo via P6 (pct_executado
    da Tarefa × valor da EAP linkada). Isso mantém compatibilidade.
    """
    from datetime import date

    # Caminho principal: avanços lançados na EAP
    avancos = (
        db.query(EapAvancoSemanal, EapItem.valor, Semana.data_fim)
        .join(EapItem, EapItem.codigo == EapAvancoSemanal.eap_codigo)
        .outerjoin(Semana, Semana.codigo == EapAvancoSemanal.semana_codigo)
        .all()
    )

    por_mes: dict[str, float] = {}
    for av, valor, data_fim in avancos:
        delta = av.pct_delta or 0.0
        if not delta:
            continue
        ref = data_fim or date.today()
        iso = ref.replace(day=1).isoformat()
        por_mes[iso] = por_mes.get(iso, 0.0) + (valor or 0.0) * delta / 100.0

    if por_mes:
        return por_mes

    # Fallback: P6
    ev_tarefa = _ev_por_tarefa(db)
    if not ev_tarefa:
        return {}
    tarefas_dict = {t.id: t for t in db.query(Tarefa).filter(Tarefa.id.in_(ev_tarefa.keys())).all()}
    for tid, ev in ev_tarefa.items():
        if ev <= 0:
            continue
        t = tarefas_dict.get(tid)
        if not t:
            continue
        d = t.termino_atual or t.termino_lb
        if not d:
            continue
        iso = d.replace(day=1).isoformat()
        por_mes[iso] = por_mes.get(iso, 0.0) + ev
    return por_mes


@router.get("/curva-realizada", response_model=list[CurvaPonto])
def curva_realizada(db: Session = Depends(get_db)):
    """[DEPRECATED] Curva-S com EV derivado de TAREFAS (avanço semanal/P6).

    Mantido por compatibilidade; NÃO é consumido pelo frontend e hoje retorna
    EV=0 (sem TarefaEapLink/EapAvancoSemanal). A fonte única de verdade do EVM
    é bm_service.get_curva_s_consolidada (BMs fechados). Use /bm/dashboard/curva-s
    ou /eap/curva-realizada-bm."""
    pv_pontos = _curva_prevista_mensal(db)
    ev_por_mes = _ev_por_mes(db)

    # Garante que meses do EV apareçam mesmo sem PV
    todos_meses = sorted(set(p.data for p in pv_pontos) | set(ev_por_mes.keys()))
    pv_dict = {p.data: p for p in pv_pontos}

    pv_acum = 0.0
    ev_acum = 0.0
    pontos: list[CurvaPonto] = []
    for iso in todos_meses:
        pv_mes = pv_dict[iso].pv_mes if iso in pv_dict else 0.0
        ev_mes = ev_por_mes.get(iso, 0.0)
        pv_acum += pv_mes
        ev_acum += ev_mes
        pontos.append(CurvaPonto(
            label=_label_mes(iso),
            data=iso,
            pv_mes=round(pv_mes, 2),
            ev_mes=round(ev_mes, 2),
            pv_acum=round(pv_acum, 2),
            ev_acum=round(ev_acum, 2),
        ))
    return pontos


@router.get("/kpis/{semana}", response_model=EvmKpis)
def kpis_semana(semana: str, db: Session = Depends(get_db)):
    """[DEPRECATED] KPIs EVM por semana com EV derivado de TAREFAS.

    Mantido por compatibilidade; não é consumido pelo frontend. A fonte única de
    verdade do EVM é o dashboard de BM (/bm/dashboard/kpis), que usa o escopo
    medido (snapshot do BM). Este endpoint pode reportar SPI sem significado
    quando não há avanço de tarefas vinculado à EAP."""
    sem = db.query(Semana).filter(Semana.codigo == semana).first()
    if not sem:
        raise HTTPException(404, "Semana não encontrada")
    if not sem.data_fim:
        raise HTTPException(422, "Semana sem data_fim definida")

    pontos = curva_realizada(db)
    # PV e EV acumulados até a data_fim
    cutoff = sem.data_fim
    pv = ev = 0.0
    for p in pontos:
        if date.fromisoformat(p.data) <= cutoff:
            pv = p.pv_acum
            ev = p.ev_acum

    bac = _bac(db)
    spi = (ev / pv) if pv > 0 else 0.0
    cv_pct = ((ev - pv) / pv * 100) if pv > 0 else 0.0

    # EAC simples = BAC / SPI (assumindo a tendência atual continua)
    eac = (bac / spi) if spi > 0 else bac
    vac = bac - eac
    pct_pv = (pv / bac * 100) if bac > 0 else 0.0
    pct_ev = (ev / bac * 100) if bac > 0 else 0.0

    return EvmKpis(
        semana=semana,
        bac=round(bac, 2),
        pv=round(pv, 2),
        ev=round(ev, 2),
        spi=round(spi, 4),
        cv_pct=round(cv_pct, 2),
        vac=round(vac, 2),
        pct_pv=round(pct_pv, 2),
        pct_ev=round(pct_ev, 2),
    )


# ── Fase 4 — Boletim de medição mensal ──────────────────────────────────

@router.get("/medicao/{ano}/{mes}")
def boletim_medicao(ano: int, mes: int, db: Session = Depends(get_db)):
    """Devolve, para o mês informado, a lista de itens-folha com:
       - valor total
       - fração prevista para o mês (curva-S original)
       - EV gerado pelas tarefas vinculadas (avanço × valor × peso)
       - status visual (atrasado, em dia, adiantado)
    """
    iso_mes = f"{ano:04d}-{mes:02d}-01"

    # Folhas
    sub = db.query(EapItem.parent_codigo).filter(EapItem.parent_codigo.isnot(None))
    folhas = db.query(EapItem).filter(~EapItem.codigo.in_(sub)).all()

    # EV por tarefa
    ev_tarefa = _ev_por_tarefa(db)

    # Mapeia codigo EAP -> lista de (tarefa_id, peso)
    links = (
        db.query(TarefaEapLink.eap_codigo, TarefaEapLink.tarefa_id, TarefaEapLink.peso)
        .all()
    )
    eap_to_tarefas: dict[str, list[tuple[int, float]]] = {}
    for codigo, tid, peso in links:
        eap_to_tarefas.setdefault(codigo, []).append((tid, peso or 1.0))

    linhas = []
    total_pv = 0.0
    total_ev = 0.0
    for it in folhas:
        try:
            dist = json.loads(it.dist_mensal or '{}')
        except json.JSONDecodeError:
            dist = {}
        # dist_mensal já em R$ absoluto desde a importação
        pv_mes = float(dist.get(iso_mes, 0.0))
        frac_mes = (pv_mes / (it.valor or 1.0)) if it.valor else 0.0
        # EV: parte proporcional do valor que já foi ganho
        ev = 0.0
        for tid, peso in eap_to_tarefas.get(it.codigo, []):
            # ev_tarefa já contabiliza Σ valor*peso; é necessário
            # reverter pra contribuição deste item específico
            ev_tar = ev_tarefa.get(tid, 0.0)
            # Aproximação: assume distribuição uniforme entre links
            n_links = len(eap_to_tarefas.get(it.codigo, [])) or 1
            ev += ev_tar / n_links
        total_pv += pv_mes
        total_ev += ev
        linhas.append({
            'codigo': it.codigo,
            'descricao': it.descricao,
            'valor': round(it.valor or 0.0, 2),
            'pv_mes': round(pv_mes, 2),
            'ev': round(ev, 2),
            'pct_mes': round(frac_mes * 100, 2),
        })

    return {
        'mes': iso_mes,
        'pv_total': round(total_pv, 2),
        'ev_total': round(total_ev, 2),
        'itens': linhas,
    }


# ── Ciclo de medição mensal ───────────────────────────────────────────
# Previsão (mês a mês) + Avanço (semana a semana, em delta).

@router.patch("/itens/{codigo}", response_model=EapItemOut)
def atualizar_item(codigo: str, payload: EapItemUpdate, db: Session = Depends(get_db)):
    """Atualiza campos editáveis do item EAP (critério, unidade)."""
    item = db.query(EapItem).filter(EapItem.codigo == codigo).first()
    if not item:
        raise HTTPException(404, "Item EAP não encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return _eap_to_out(item)


# ── Previsão Mensal ──────────────────────────────────────────────────


def _is_manual_codigo(codigo: str) -> bool:
    return any(part.upper().startswith("M") and part[1:].isdigit() for part in (codigo or "").split("."))


def _proximo_codigo_manual(db: Session, parent_codigo: str) -> str:
    prefix = f"{parent_codigo}.M"
    codigos = [
        c for (c,) in db.query(EapItem.codigo)
        .filter(EapItem.codigo.like(f"{prefix}%"))
        .all()
    ]
    usados: set[int] = set()
    for codigo in codigos:
        sufixo = codigo.replace(prefix, "", 1)
        if sufixo.isdigit():
            usados.add(int(sufixo))
    n = 1
    while n in usados:
        n += 1
    return f"{prefix}{n:03d}"


@router.post("/atividades-manuais", response_model=EapItemOut, status_code=201)
def criar_atividade_manual(payload: EapAtividadeManualIn, db: Session = Depends(get_db)):
    parent = db.query(EapItem).filter(EapItem.codigo == payload.parent_codigo).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Item pai da EAP nao encontrado")

    valor_parent = float(parent.valor or 0.0)
    if valor_parent > 0 and float(payload.valor or 0.0) > valor_parent:
        raise HTTPException(
            status_code=422,
            detail="O peso/valor estimado da atividade nao pode ser maior que o valor do item pai.",
        )
    soma_filhos = (
        db.query(func.sum(EapItem.valor))
        .filter(EapItem.parent_codigo == parent.codigo)
        .scalar()
    ) or 0.0
    if valor_parent > 0 and float(soma_filhos or 0.0) + float(payload.valor or 0.0) > valor_parent + 0.01:
        raise HTTPException(
            status_code=422,
            detail=(
                "A soma das atividades filhas excede 100% do item de origem. "
                "Reduza o percentual equivalente ou escolha uma folha sem desdobramento."
            ),
        )

    codigo = _proximo_codigo_manual(db, parent.codigo)
    item = EapItem(
        codigo=codigo,
        descricao=payload.descricao.strip(),
        nivel=int(parent.nivel or 0) + 1,
        parent_codigo=parent.codigo,
        valor=float(payload.valor or 0.0),
        dist_mensal=json.dumps({}, ensure_ascii=False),
        criterio=payload.criterio,
        unidade=payload.unidade or "%",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _eap_to_out(item)


@router.delete("/atividades-manuais/{codigo}", status_code=204)
def remover_atividade_manual(codigo: str, db: Session = Depends(get_db)):
    item = db.query(EapItem).filter(EapItem.codigo == codigo).first()
    if not item:
        raise HTTPException(status_code=404, detail="Atividade manual nao encontrada")
    if not _is_manual_codigo(item.codigo):
        raise HTTPException(status_code=422, detail="Somente atividades manuais podem ser removidas por este endpoint")

    tem_filhos = db.query(EapItem.id).filter(EapItem.parent_codigo == item.codigo).first() is not None
    if tem_filhos:
        raise HTTPException(status_code=422, detail="Nao e possivel remover uma atividade manual que possui filhos")

    from ..models import BmSnapshotPrevisao, BmLancamento, BmConsolidado
    usado_em_bm = (
        db.query(BmSnapshotPrevisao.id).filter(BmSnapshotPrevisao.eap_codigo == codigo).first()
        or db.query(BmLancamento.id).filter(BmLancamento.eap_codigo == codigo).first()
        or db.query(BmConsolidado.id).filter(BmConsolidado.eap_codigo == codigo).first()
    )
    if usado_em_bm:
        raise HTTPException(status_code=409, detail="Esta atividade ja foi usada em BM e nao pode ser removida")

    prevs = db.query(EapPrevisaoMensal).filter(EapPrevisaoMensal.eap_codigo == codigo).all()
    if any(p.status_previsao == "convertida" for p in prevs):
        raise HTTPException(status_code=409, detail="Esta atividade ja foi convertida em snapshot de BM")
    for p in prevs:
        db.delete(p)
    db.flush()
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.get("/previsao/{ano}/{mes}", response_model=list[EapPrevisaoOut])
def listar_previsao(ano: int, mes: int, db: Session = Depends(get_db)):
    return (
        db.query(EapPrevisaoMensal)
        .filter(EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes)
        .all()
    )


@router.post("/previsao/{ano}/{mes}/puxar-p6")
def puxar_previsao_do_p6_endpoint(ano: int, mes: int, db: Session = Depends(get_db)):
    """Pré-popula a previsão com base no que o P6 prevê para esse mês.

    Para cada item-folha da EAP que tem dist_mensal[YYYY-MM] > 0, sugere
    pct_previsto = (R$ daquele mês / valor total do item) × 100, mas
    NUNCA sobrescreve previsões já existentes.

    Bloqueado se o mês já tem BM fechado/consolidado (previsões são convertidas).
    """
    try:
        assert_competencia_editavel(db, ano, mes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    from ..models import BmCiclo as _BmCiclo
    bm_fechado = db.query(_BmCiclo).filter(
        _BmCiclo.ano == ano, _BmCiclo.mes == mes,
        _BmCiclo.status.in_(["fechada", "consolidada"]),
    ).first()
    if bm_fechado:
        raise HTTPException(
            400,
            f"Não é possível puxar previsão do P6 para {ano}/{mes:02d}: "
            f"o BM {bm_fechado.numero_bm} já está {bm_fechado.status}."
        )
    iso_mes = f"{ano:04d}-{mes:02d}-01"

    sub = db.query(EapItem.parent_codigo).filter(EapItem.parent_codigo.isnot(None))
    folhas = (
        db.query(EapItem)
        .filter(~EapItem.codigo.in_(sub))
        .filter(EapItem.dist_mensal.isnot(None))
        .all()
    )

    ja_existem = {
        p.eap_codigo
        for (p,) in db.query(EapPrevisaoMensal.eap_codigo)
        .filter(EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes)
        .all()
    }

    inseridos = 0
    for it in folhas:
        if it.codigo in ja_existem:
            continue
        try:
            dist = json.loads(it.dist_mensal or '{}')
        except json.JSONDecodeError:
            continue
        valor_mes = float(dist.get(iso_mes, 0.0))
        if valor_mes <= 0:
            continue
        pct = (valor_mes / it.valor * 100.0) if it.valor else 0.0
        db.add(EapPrevisaoMensal(
            ano=ano, mes=mes, eap_codigo=it.codigo,
            pct_previsto=pct,
        ))
        inseridos += 1
    db.commit()
    return {'inseridos': inseridos, 'ja_existiam': len(ja_existem)}



def _validar_previsao_hierarquia(db: Session, pct_por_codigo: dict[str, float], codigos_afetados: set[str] | None = None) -> None:
    todos = db.query(EapItem).order_by(EapItem.codigo).all()
    filhos_por_pai: dict[str, list[EapItem]] = {}
    item_por_codigo = {it.codigo: it for it in todos}
    for it in todos:
        if it.parent_codigo:
            filhos_por_pai.setdefault(it.parent_codigo, []).append(it)

    validar_codigos: set[str] | None = None
    if codigos_afetados is not None:
        validar_codigos = set(codigos_afetados)
        for codigo in list(codigos_afetados):
            atual = item_por_codigo.get(codigo)
            while atual and atual.parent_codigo:
                validar_codigos.add(atual.parent_codigo)
                atual = item_por_codigo.get(atual.parent_codigo)

    valor_previsto: dict[str, float] = {}
    for it in sorted(todos, key=lambda x: (-len(x.codigo), x.codigo)):
        filhos = filhos_por_pai.get(it.codigo, [])
        if filhos:
            previsto = sum(valor_previsto.get(f.codigo, 0.0) for f in filhos)
        else:
            pct = max(0.0, min(100.0, float(pct_por_codigo.get(it.codigo, 0.0) or 0.0)))
            previsto = float(it.valor or 0.0) * pct / 100.0
        valor_previsto[it.codigo] = previsto
        limite = float(it.valor or 0.0)
        valor_filhos = sum(float(f.valor or 0.0) for f in filhos)
        hierarquia_inconsistente = filhos and limite > 0 and valor_filhos > limite + 0.01
        deve_validar = validar_codigos is None or it.codigo in validar_codigos
        if deve_validar and filhos and limite > 0 and not hierarquia_inconsistente and previsto > limite + 0.01:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Previs?o excede 100% no item {it.codigo}. "
                    f"Previsto R$ {previsto:.2f} para limite R$ {limite:.2f}. "
                    "Reduza o percentual ou o peso das atividades filhas."
                ),
            )

@router.post("/previsao/{ano}/{mes}")
def lancar_previsao(ano: int, mes: int, payload: EapPrevisaoBulk, db: Session = Depends(get_db)):
    """Upsert em lote da previsão do mês.

    Para cada item recebido:
      - Se já existe registro (ano,mes,eap_codigo) → atualiza pct_previsto/observacao
      - Senão → cria
    Itens com pct_previsto == 0 e observacao vazia são DELETADOS (limpa previsão).

    IMUTABILIDADE: itens com status_previsao='convertida' (BM aberto) são ignorados.
    Previsão convertida só pode ser alterada via redistribuição de pendências.
    """
    try:
        assert_competencia_editavel(db, ano, mes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    pct_final = {
        p.eap_codigo: float(p.pct_previsto or 0.0)
        for p in db.query(EapPrevisaoMensal)
        .filter(EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes)
        .all()
    }
    for item in payload.itens:
        pct_val = float(item.pct_previsto or 0.0)
        eh_zero = pct_val == 0 and not (item.observacao or '').strip()
        if eh_zero:
            pct_final.pop(item.eap_codigo, None)
        else:
            pct_final[item.eap_codigo] = pct_val
    _validar_previsao_hierarquia(db, pct_final, {item.eap_codigo for item in payload.itens})

    inseridos = atualizados = removidos = bloqueados = 0
    for item in payload.itens:
        existente = (
            db.query(EapPrevisaoMensal)
            .filter(
                EapPrevisaoMensal.ano == ano,
                EapPrevisaoMensal.mes == mes,
                EapPrevisaoMensal.eap_codigo == item.eap_codigo,
            )
            .first()
        )
        # Ponto 7: previsão convertida (snapshot já tirado pelo BM) é imutável
        if existente and existente.status_previsao == "convertida":
            bloqueados += 1
            continue

        # Validação financeira: pct_previsto deve estar em 0–100 (escala legada)
        pct_val = item.pct_previsto or 0
        if pct_val != 0:
            try:
                normalize_pct_100(pct_val, campo="pct_previsto", codigo=item.eap_codigo)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

        eh_zero = pct_val == 0 and not (item.observacao or '').strip()
        if existente:
            if eh_zero:
                db.delete(existente)
                removidos += 1
            else:
                existente.pct_previsto = item.pct_previsto
                existente.observacao = item.observacao
                existente.lancado_por = payload.lancado_por
                atualizados += 1
        elif not eh_zero:
            db.add(EapPrevisaoMensal(
                ano=ano, mes=mes, eap_codigo=item.eap_codigo,
                pct_previsto=item.pct_previsto,
                observacao=item.observacao,
                lancado_por=payload.lancado_por,
            ))
            inseridos += 1
    db.commit()
    return {
        'inseridos': inseridos, 'atualizados': atualizados,
        'removidos': removidos, 'bloqueados_convertida': bloqueados,
    }


# ── Adiantar atividade na Previsão Mensal ───────────────────────────

@router.post("/previsao/{ano}/{mes}/adiantar", response_model=EapPrevisaoOut)
def adiantar_atividade(ano: int, mes: int, payload: EapAdiantarIn, db: Session = Depends(get_db)):
    """Adiciona (ou atualiza) uma atividade adiantada de outro mês na previsão atual."""
    try:
        assert_competencia_editavel(db, ano, mes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Validação financeira central
    try:
        normalize_pct_100(
            payload.pct_previsto or 0,
            campo="pct_previsto",
            codigo=payload.eap_codigo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    existente = (
        db.query(EapPrevisaoMensal)
        .filter(
            EapPrevisaoMensal.ano == ano,
            EapPrevisaoMensal.mes == mes,
            EapPrevisaoMensal.eap_codigo == payload.eap_codigo,
        )
        .first()
    )
    if existente:
        existente.pct_previsto = payload.pct_previsto
        existente.adiantada = True
        existente.mes_original_ano = payload.mes_original_ano
        existente.mes_original_mes = payload.mes_original_mes
        existente.observacao = payload.observacao
        existente.lancado_por = payload.lancado_por
    else:
        existente = EapPrevisaoMensal(
            ano=ano, mes=mes,
            eap_codigo=payload.eap_codigo,
            pct_previsto=payload.pct_previsto,
            adiantada=True,
            mes_original_ano=payload.mes_original_ano,
            mes_original_mes=payload.mes_original_mes,
            observacao=payload.observacao,
            lancado_por=payload.lancado_por,
        )
        db.add(existente)
    db.commit()
    db.refresh(existente)
    return existente


@router.delete("/previsao/{ano}/{mes}/adiantada/{eap_codigo}", status_code=204)
def remover_adiantada(ano: int, mes: int, eap_codigo: str, db: Session = Depends(get_db)):
    """Remove uma atividade adiantada da previsão do mês."""
    reg = (
        db.query(EapPrevisaoMensal)
        .filter(
            EapPrevisaoMensal.ano == ano,
            EapPrevisaoMensal.mes == mes,
            EapPrevisaoMensal.eap_codigo == eap_codigo,
            EapPrevisaoMensal.adiantada == True,
        )
        .first()
    )
    if not reg:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Atividade adiantada não encontrada")
    db.delete(reg)
    db.commit()


# ── Pendências do mês anterior ──────────────────────────────────────

@router.get("/previsao/{ano}/{mes}/pendencias")
def pendencias_mes_anterior(ano: int, mes: int, db: Session = Depends(get_db)):
    """Itens previstos no mês anterior que não foram totalmente realizados.

    Retorna lista de {eap_codigo, descricao, nivel, parent_codigo, valor,
    pct_previsto, pct_realizado, gap} onde gap = pct_previsto - pct_realizado > 0.
    Todos os % estão em escala 0–100.
    """
    from ..models import CicloMedicao as _CM, LancamentoMedicao as _LM

    # Mês anterior
    mes_ant = mes - 1
    ano_ant = ano
    if mes_ant == 0:
        mes_ant = 12
        ano_ant = ano - 1

    # Previsões do mês anterior (0–100)
    prevs = {
        p.eap_codigo: float(p.pct_previsto or 0)
        for p in db.query(EapPrevisaoMensal)
        .filter(EapPrevisaoMensal.ano == ano_ant, EapPrevisaoMensal.mes == mes_ant)
        .all()
    }
    if not prevs:
        return []

    # Ciclo fechado do mês anterior
    ciclo_ant = (
        db.query(_CM)
        .filter(_CM.ano == ano_ant, _CM.mes == mes_ant, _CM.status == "fechado")
        .first()
    )

    # pct_acumulado ao fim do mês anterior (0–1) por item
    pct_acum_ant: dict[str, float] = {}
    if ciclo_ant:
        for l in db.query(_LM).filter(_LM.ciclo_id == ciclo_ant.id).all():
            pct_acum_ant[l.eap_codigo] = float(l.pct_acumulado or 0)

    # pct_acumulado ao fim do mês anterior-1 (para calcular o delta do período)
    ciclos_antes = (
        db.query(_CM)
        .filter(
            (_CM.ano < ano_ant) | ((_CM.ano == ano_ant) & (_CM.mes < mes_ant)),
            _CM.status == "fechado",
        )
        .all()
    )
    # Pega o ciclo mais recente antes do mês anterior
    ciclos_antes.sort(key=lambda c: (c.ano, c.mes))
    pct_acum_prev_ant: dict[str, float] = {}
    if ciclos_antes:
        ultimo = ciclos_antes[-1]
        for l in db.query(_LM).filter(_LM.ciclo_id == ultimo.id).all():
            pct_acum_prev_ant[l.eap_codigo] = float(l.pct_acumulado or 0)

    # Delta realizado no mês anterior (0–100)
    def pct_real_periodo(codigo: str) -> float:
        acum = pct_acum_ant.get(codigo, 0.0)
        ant  = pct_acum_prev_ant.get(codigo, 0.0)
        return max(0.0, acum - ant) * 100.0

    itens_map = {it.codigo: it for it in db.query(EapItem).all()}

    result = []
    for codigo, pct_prev in prevs.items():
        it = itens_map.get(codigo)
        if not it:
            continue
        pct_real = pct_real_periodo(codigo)
        gap = round(pct_prev - pct_real, 4)
        if gap <= 0.01:
            continue
        result.append({
            "eap_codigo": codigo,
            "descricao": it.descricao,
            "nivel": it.nivel,
            "parent_codigo": it.parent_codigo,
            "valor": float(it.valor or 0),
            "pct_previsto": round(pct_prev, 2),
            "pct_realizado": round(pct_real, 2),
            "gap": gap,
        })

    result.sort(key=lambda x: x["eap_codigo"])
    return result


# ── Avanço Semanal ───────────────────────────────────────────────────

@router.get("/avanco/{semana_codigo}", response_model=list[EapAvancoOut])
def listar_avanco_semana(semana_codigo: str, db: Session = Depends(get_db)):
    return (
        db.query(EapAvancoSemanal)
        .filter(EapAvancoSemanal.semana_codigo == semana_codigo)
        .all()
    )


@router.post("/avanco")
def lancar_avanco(payload: EapAvancoBulk, db: Session = Depends(get_db)):
    """Lança o DELTA da semana para cada item.

    Faz upsert por (semana, eap_codigo). Delta zerado + observação vazia
    remove o registro.
    """
    inseridos = atualizados = removidos = 0
    for item in payload.itens:
        existente = (
            db.query(EapAvancoSemanal)
            .filter(
                EapAvancoSemanal.semana_codigo == payload.semana_codigo,
                EapAvancoSemanal.eap_codigo == item.eap_codigo,
            )
            .first()
        )
        eh_zero = (item.pct_delta or 0) == 0 and not (item.observacao or '').strip()
        if existente:
            if eh_zero:
                db.delete(existente)
                removidos += 1
            else:
                existente.pct_delta = item.pct_delta
                existente.observacao = item.observacao
                existente.lancado_por = payload.lancado_por
                atualizados += 1
        elif not eh_zero:
            db.add(EapAvancoSemanal(
                semana_codigo=payload.semana_codigo,
                eap_codigo=item.eap_codigo,
                pct_delta=item.pct_delta,
                observacao=item.observacao,
                lancado_por=payload.lancado_por,
            ))
            inseridos += 1
    db.commit()
    return {'inseridos': inseridos, 'atualizados': atualizados, 'removidos': removidos}


# ── View consolidada para BM e telas ──────────────────────────────────

# ── Ciclo de Medição Mensal ──────────────────────────────────────────────

def _pct_acum_ant(it, todos, lancs_ant):
    """Propaga o acumulado anterior para itens pai recursivamente."""
    filhos = [x for x in todos if x.parent_codigo == it.codigo]
    if not filhos:
        return float(lancs_ant.get(it.codigo, 0.0))
    val_pai = float(it.valor or 0.0)
    if val_pai <= 0:
        return 0.0
    soma = sum(float(f.valor or 0.0) * _pct_acum_ant(f, todos, lancs_ant) for f in filhos)
    return soma / val_pai


def _montar_medicao(ciclo, db: Session) -> dict:
    """Monta MedicaoMesOut: propaga % dos itens folha para os pais."""
    from ..models import CicloMedicao as _CM, LancamentoMedicao as _LM

    # Todos os itens EAP
    todos = db.query(EapItem).order_by(EapItem.codigo).all()
    codigos_com_filhos = {it.parent_codigo for it in todos if it.parent_codigo}
    folhas = {it.codigo for it in todos if it.codigo not in codigos_com_filhos}

    # Lançamentos deste ciclo
    lancs_ciclo = {l.eap_codigo: l for l in db.query(_LM).filter(_LM.ciclo_id == ciclo.id).all()}

    # Acumulado anterior: último ciclo FECHADO antes deste
    ciclo_ant = (
        db.query(_CM)
        .filter(_CM.status == "fechado")
        .filter((_CM.ano < ciclo.ano) | ((_CM.ano == ciclo.ano) & (_CM.mes < ciclo.mes)))
        .order_by(_CM.ano.desc(), _CM.mes.desc())
        .first()
    )
    lancs_ant = {}
    if ciclo_ant:
        lancs_ant = {l.eap_codigo: l.pct_acumulado for l in
                     db.query(_LM).filter(_LM.ciclo_id == ciclo_ant.id).all()}

    # Previsão do mês
    _prevs_rows = db.query(EapPrevisaoMensal)\
        .filter(EapPrevisaoMensal.ano == ciclo.ano, EapPrevisaoMensal.mes == ciclo.mes)\
        .all()
    prevs = {p.eap_codigo: p.pct_previsto for p in _prevs_rows}
    prevs_adiantada = {p.eap_codigo: bool(p.adiantada) for p in _prevs_rows}

    # Monta dict de pct_acumulado por codigo (folhas primeiro)
    pct_acum: dict[str, float] = {}
    for it in todos:
        if it.codigo in folhas:
            l = lancs_ciclo.get(it.codigo)
            pct_acum[it.codigo] = float(l.pct_acumulado) if l else float(lancs_ant.get(it.codigo, 0.0))

    # Propaga para pais (bottom-up)
    sorted_todos = sorted(todos, key=lambda x: (-len(x.codigo), x.codigo))
    for it in sorted_todos:
        if it.codigo in folhas:
            continue
        filhos = [x for x in todos if x.parent_codigo == it.codigo]
        if not filhos:
            continue
        val_pai = float(it.valor or 0.0)
        if val_pai <= 0:
            continue
        soma = sum(float(f.valor or 0.0) * pct_acum.get(f.codigo, 0.0) for f in filhos)
        pct_acum[it.codigo] = soma / val_pai

    # Monta lista de saída
    bac = sum(float(it.valor or 0.0) for it in todos if it.nivel == 1)
    month_key = f"{ciclo.ano}-{ciclo.mes:02d}-01"   # chave para dist_mensal
    itens_out = []
    for it in sorted(todos, key=lambda x: x.codigo):
        pa = float(lancs_ant.get(it.codigo, 0.0)) if it.codigo in folhas else _pct_acum_ant(it, todos, lancs_ant)
        pa_atual = pct_acum.get(it.codigo, pa)
        periodo = max(0.0, pa_atual - pa)
        val = float(it.valor or 0.0)
        # Valor planejado para o mês segundo a curva de desembolso
        try:
            dist = json.loads(it.dist_mensal) if it.dist_mensal else {}
        except (ValueError, TypeError):
            dist = {}
        valor_dist_mes = float(dist.get(month_key, 0.0))
        itens_out.append({
            "codigo": it.codigo,
            "descricao": it.descricao,
            "nivel": it.nivel,
            "parent_codigo": it.parent_codigo,
            "valor": val,
            "is_folha": it.codigo in folhas,
            "pct_previsto": float(prevs.get(it.codigo, 0.0)) / 100.0,   # normaliza 0-100 → 0-1
            "pct_acum_anterior": pa,
            "pct_acumulado": pa_atual,
            "pct_periodo": periodo,
            "valor_periodo": periodo * val,
            "valor_acumulado": pa_atual * val,
            "valor_dist_mes": valor_dist_mes,
            "observacao": lancs_ciclo[it.codigo].observacao if it.codigo in lancs_ciclo else None,
            "adiantada": prevs_adiantada.get(it.codigo, False),
        })

    total_pct_periodo = sum(i["valor_periodo"] for i in itens_out if i["nivel"] == 1) / bac if bac else 0
    total_pct_acum = sum(i["valor_acumulado"] for i in itens_out if i["nivel"] == 1) / bac if bac else 0
    total_valor_periodo = sum(i["valor_periodo"] for i in itens_out if i["nivel"] == 1)

    return {
        "ciclo": ciclo,
        "itens": itens_out,
        "bac": bac,
        "total_pct_acum": total_pct_acum,
        "total_pct_periodo": total_pct_periodo,
        "total_valor_periodo": total_valor_periodo,
    }


@router.get("/ciclos", response_model=list[CicloMedicaoOut])
def listar_ciclos(db: Session = Depends(get_db)):
    """Lista todos os ciclos de medição, do mais recente ao mais antigo."""
    from ..models import CicloMedicao as _CM
    return db.query(_CM).order_by(_CM.ano.desc(), _CM.mes.desc()).all()


@router.post("/ciclos", response_model=CicloMedicaoOut)
def abrir_ciclo(ano: int, mes: int, db: Session = Depends(get_db)):
    """Abre (ou retorna existente) o ciclo de medição para o mês/ano."""
    from ..models import CicloMedicao as _CM
    ciclo = db.query(_CM).filter(_CM.ano == ano, _CM.mes == mes).first()
    if not ciclo:
        ciclo = _CM(ano=ano, mes=mes, status="aberto")
        db.add(ciclo)
        db.commit()
        db.refresh(ciclo)
    return ciclo


@router.get("/ciclos/mes/{ano}/{mes}", response_model=MedicaoMesOut)
def get_ciclo_mes(ano: int, mes: int, db: Session = Depends(get_db)):
    """Abre (ou cria) e retorna o ciclo do mês/ano."""
    from ..models import CicloMedicao as _CM
    ciclo = db.query(_CM).filter(_CM.ano == ano, _CM.mes == mes).first()
    if not ciclo:
        ciclo = _CM(ano=ano, mes=mes, status="aberto")
        db.add(ciclo)
        db.commit()
        db.refresh(ciclo)
    return _montar_medicao(ciclo, db)


@router.get("/ciclos/resumo-fases/{ano}/{mes}")
def resumo_fases(ano: int, mes: int, db: Session = Depends(get_db)):
    """Retorna comparativo Previsto × Realizado por fase (nivel 1) para o mês."""
    from ..models import CicloMedicao as _CM, LancamentoMedicao as _LM

    ciclos_ate_mes = (
        db.query(_CM)
        .filter((_CM.ano < ano) | ((_CM.ano == ano) & (_CM.mes <= mes)))
        .all()
    )
    pct_real_acum: dict[str, float] = {}
    for ciclo in sorted(ciclos_ate_mes, key=lambda c: (c.ano, c.mes)):
        for l in db.query(_LM).filter(_LM.ciclo_id == ciclo.id).all():
            pct_real_acum[l.eap_codigo] = float(l.pct_acumulado)

    ciclo_ant = (
        db.query(_CM)
        .filter((_CM.ano < ano) | ((_CM.ano == ano) & (_CM.mes < mes)))
        .filter(_CM.status == "fechado")
        .order_by(_CM.ano.desc(), _CM.mes.desc())
        .first()
    )
    pct_real_ant: dict[str, float] = {}
    if ciclo_ant:
        for l in db.query(_LM).filter(_LM.ciclo_id == ciclo_ant.id).all():
            pct_real_ant[l.eap_codigo] = float(l.pct_acumulado)

    # pct_previsto é armazenado em 0–100; normaliza para 0–1 (mesma escala
    # de pct_acumulado em LancamentoMedicao) antes de propagar.
    prevs_acum: dict[str, float] = {}
    prevs_periodo: dict[str, float] = {}
    for p in db.query(EapPrevisaoMensal).filter(
        (EapPrevisaoMensal.ano < ano) | ((EapPrevisaoMensal.ano == ano) & (EapPrevisaoMensal.mes <= mes))
    ).all():
        prevs_acum[p.eap_codigo] = prevs_acum.get(p.eap_codigo, 0.0) + float(p.pct_previsto or 0) / 100.0
    for p in db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes
    ).all():
        prevs_periodo[p.eap_codigo] = float(p.pct_previsto or 0) / 100.0

    todos = db.query(EapItem).all()
    codigos_com_filhos = {it.parent_codigo for it in todos if it.parent_codigo}
    folhas = {it.codigo for it in todos if it.codigo not in codigos_com_filhos}

    def propagar(pct_map):
        vals = dict(pct_map)
        sorted_its = sorted(todos, key=lambda x: (-len(x.codigo), x.codigo))
        for it in sorted_its:
            if it.codigo in folhas:
                continue
            filhos = [x for x in todos if x.parent_codigo == it.codigo]
            if not filhos or not it.valor:
                continue
            soma = sum(float(f.valor or 0) * vals.get(f.codigo, 0.0) for f in filhos)
            vals[it.codigo] = soma / float(it.valor)
        return vals

    acum_real = propagar(pct_real_acum)
    ant_real = propagar(pct_real_ant)
    acum_prev = propagar(prevs_acum)
    periodo_prev = propagar(prevs_periodo)

    fases_nivel_1 = sorted([x for x in todos if x.nivel == 1], key=lambda x: x.codigo)
    tem_previsao_cadastrada = db.query(EapPrevisaoMensal.id).first() is not None
    previsto_fase_lb = (
        previsto_fases_lb_eap_j(
            {it.codigo: float(it.valor or 0) for it in fases_nivel_1},
            ano,
            mes,
        )
        if tem_previsao_cadastrada or ciclos_ate_mes
        else {}
    )

    fases = []
    for it in fases_nivel_1:
        val = float(it.valor or 0)
        pct_ra = acum_real.get(it.codigo, 0.0)
        pct_rp = max(0.0, pct_ra - ant_real.get(it.codigo, 0.0))
        pct_pa = acum_prev.get(it.codigo, 0.0)
        pct_pp = periodo_prev.get(it.codigo, 0.0)
        previsto_lb = previsto_fase_lb.get(it.codigo)
        if previsto_lb:
            pct_pa = previsto_lb["pct_previsto_acum"]
            pct_pp = previsto_lb["pct_previsto_periodo"]
            val_prev_periodo = previsto_lb["valor_previsto_periodo"]
            val_prev_acum = previsto_lb["valor_previsto_acum"]
        else:
            val_prev_periodo = pct_pp * val
            val_prev_acum = pct_pa * val
        fases.append({
            "codigo": it.codigo,
            "descricao": it.descricao,
            "valor": round(val, 2),
            "pct_previsto_periodo": round(pct_pp, 6),
            "pct_previsto_acum": round(pct_pa, 6),
            "valor_previsto_periodo": round(val_prev_periodo, 2),
            "valor_previsto_acum": round(val_prev_acum, 2),
            "pct_realizado_periodo": round(pct_rp, 6),
            "pct_realizado_acum": round(pct_ra, 6),
            "valor_realizado_periodo": round(pct_rp * val, 2),
            "valor_realizado_acum": round(pct_ra * val, 2),
            "desvio_periodo": round(pct_rp - pct_pp, 6),
        })

    bac = sum(float(it.valor or 0) for it in todos if it.nivel == 1)
    return {
        "ano": ano, "mes": mes, "bac": round(bac, 2),
        "fases": fases,
        "total_pct_prev_periodo": round(sum(f["valor_previsto_periodo"] for f in fases) / bac if bac else 0, 6),
        "total_pct_real_periodo": round(sum(f["valor_realizado_periodo"] for f in fases) / bac if bac else 0, 6),
        "total_valor_prev_periodo": round(sum(f["valor_previsto_periodo"] for f in fases), 2),
        "total_valor_real_periodo": round(sum(f["valor_realizado_periodo"] for f in fases), 2),
        "total_pct_real_acum": round(sum(f["valor_realizado_acum"] for f in fases) / bac if bac else 0, 6),
        "total_pct_prev_acum": round(sum(f["valor_previsto_acum"] for f in fases) / bac if bac else 0, 6),
    }


@router.get("/curva-realizada-bm", response_model=list[CurvaPonto])
def curva_realizada_bm(db: Session = Depends(get_db)):
    """Curva-S EV (BMs fechados/consolidados) — DELEGADA à fonte única de verdade.

    Unificação (Achado B): a lógica de curva PV×EV vive APENAS em
    bm_service.get_curva_s_consolidada (escopo medido + correção de back-fill).
    Este endpoint apenas adapta a saída para o schema CurvaPonto, evitando uma
    segunda implementação divergente (que tinha back-fill incorreto e o guard
    de valor 0 quebrando a propagação)."""
    from ..services.bm_service import get_curva_s_consolidada
    pontos = get_curva_s_consolidada(db)
    return [
        CurvaPonto(
            label=p["label"], data=p["data"],
            pv_mes=p["pv_mes"], ev_mes=p["ev_mes"],
            pv_acum=p["pv_acum"], ev_acum=p["ev_acum"],
        )
        for p in pontos
    ]


@router.get("/ciclos/historico-bm")
def historico_bm(db: Session = Depends(get_db)):
    """Lista BMs fechados com resumo financeiro."""
    from ..models import CicloMedicao as _CM, LancamentoMedicao as _LM

    ciclos = db.query(_CM).filter(_CM.status == "fechado").order_by(_CM.ano.desc(), _CM.mes.desc()).all()
    todos = db.query(EapItem).all()
    nivel1_val = {it.codigo: float(it.valor or 0) for it in todos if it.nivel == 1}
    codigos_com_filhos = {it.parent_codigo for it in todos if it.parent_codigo}
    folhas = {it.codigo for it in todos if it.codigo not in codigos_com_filhos}
    bac = sum(nivel1_val.values())

    resultado = []
    for ciclo in ciclos:
        lancs = {l.eap_codigo: float(l.pct_acumulado) for l in
                 db.query(_LM).filter(_LM.ciclo_id == ciclo.id).all()}
        vals = dict(lancs)
        for it in sorted(todos, key=lambda x: (-len(x.codigo), x.codigo)):
            if it.codigo in folhas:
                continue
            filhos = [x for x in todos if x.parent_codigo == it.codigo]
            if not filhos or not it.valor:
                continue
            soma = sum(float(f.valor or 0) * vals.get(f.codigo, 0.0) for f in filhos)
            vals[it.codigo] = soma / float(it.valor)

        ev_acum = sum(vals.get(cod, 0.0) * v for cod, v in nivel1_val.items())
        meses_pt = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
                    7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}
        resultado.append({
            "ciclo_id": ciclo.id,
            "ano": ciclo.ano,
            "mes": ciclo.mes,
            "label": f"{meses_pt[ciclo.mes]}/{str(ciclo.ano)[2:]}",
            "status": ciclo.status,
            "fechado_em": ciclo.fechado_em.isoformat() if ciclo.fechado_em else None,
            "fechado_por": ciclo.fechado_por,
            "ev_acum": round(ev_acum, 2),
            "pct_acum": round(ev_acum / bac, 6) if bac else 0,
        })
    return resultado


@router.get("/ciclos/{ciclo_id}", response_model=MedicaoMesOut)
def get_ciclo(ciclo_id: int, db: Session = Depends(get_db)):
    """Retorna o ciclo completo com todos os itens EAP e valores propagados."""
    from ..models import CicloMedicao as _CM
    ciclo = db.query(_CM).filter(_CM.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "Ciclo não encontrado.")
    return _montar_medicao(ciclo, db)


@router.put("/ciclos/{ciclo_id}/salvar", response_model=MedicaoMesOut)
def salvar_previa(ciclo_id: int, body: LancamentoBulk, db: Session = Depends(get_db)):
    """Salva os lançamentos de avanço para o ciclo (PRÉVIA — pode ser chamado N vezes)."""
    from ..models import CicloMedicao as _CM, LancamentoMedicao as _LM
    ciclo = db.query(_CM).filter(_CM.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "Ciclo não encontrado.")
    if ciclo.status == "fechado":
        raise HTTPException(400, "BM já fechado. Reabertura não permitida.")

    for item in body.itens:
        lanc = db.query(_LM).filter(_LM.ciclo_id == ciclo_id, _LM.eap_codigo == item.eap_codigo).first()
        if lanc:
            lanc.pct_acumulado = item.pct_acumulado
            lanc.observacao = item.observacao
        else:
            db.add(_LM(ciclo_id=ciclo_id, eap_codigo=item.eap_codigo,
                       pct_acumulado=item.pct_acumulado, observacao=item.observacao))
    db.commit()
    return _montar_medicao(ciclo, db)


@router.post("/ciclos/{ciclo_id}/fechar", response_model=MedicaoMesOut)
def fechar_bm(ciclo_id: int, fechado_por: Optional[str] = None, db: Session = Depends(get_db)):
    """Fecha o BM — torna imutável."""
    from ..models import CicloMedicao as _CM
    from datetime import datetime as _dt
    ciclo = db.query(_CM).filter(_CM.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "Ciclo não encontrado.")
    if ciclo.status == "fechado":
        raise HTTPException(400, "BM já está fechado.")
    ciclo.status = "fechado"
    ciclo.fechado_em = _dt.utcnow()
    ciclo.fechado_por = fechado_por
    db.commit()
    return _montar_medicao(ciclo, db)


@router.get("/ciclos/{ciclo_id}/previa-pdf")
def get_previa_pdf(ciclo_id: int, db: Session = Depends(get_db)):
    """Gera PDF da prévia/BM do ciclo."""
    from ..models import CicloMedicao as _CM
    ciclo = db.query(_CM).filter(_CM.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "Ciclo não encontrado.")
    dados = _montar_medicao(ciclo, db)
    from ..utils.gerar_previa_pdf import gerar_previa_pdf
    try:
        pdf_bytes = gerar_previa_pdf(dados)
    except Exception as e:
        logger.exception("Erro ao gerar PDF da prévia")
        raise HTTPException(500, f"Erro ao gerar PDF: {type(e).__name__}: {e}")
    status_lbl = "FECHADO" if ciclo.status == "fechado" else "PREVIA"
    filename = f"BM-{ciclo.ano}-{ciclo.mes:02d}-{status_lbl}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/medicao-mes/{ano}/{mes}", response_model=list[EapItemMedicaoOut])
def medicao_mes(ano: int, mes: int, db: Session = Depends(get_db)):
    """View consolidada do mês para a tela de medição e geração do BM.

    Devolve, para cada item EAP que aparece na previsão do mês ou tem
    avanço lançado em alguma semana até o fim do mês:

      - pct_previsto (do EapPrevisaoMensal)
      - pct_acum_anterior (soma dos deltas de TODAS as semanas anteriores
        ao primeiro dia do mês selecionado)
      - pct_acum_atual (acum_anterior + soma dos deltas das semanas
        que caem dentro do mês)
      - pct_periodo = pct_acum_atual - pct_acum_anterior
      - valor_periodo = pct_periodo / 100 × valor_total_item
      - valor_acum_total = pct_acum_atual / 100 × valor
    """
    from datetime import date

    primeiro_dia = date(ano, mes, 1)
    if mes == 12:
        primeiro_dia_seguinte = date(ano + 1, 1, 1)
    else:
        primeiro_dia_seguinte = date(ano, mes + 1, 1)

    # Previsões do mês
    previsoes = {
        p.eap_codigo: p
        for p in db.query(EapPrevisaoMensal)
        .filter(EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes)
        .all()
    }

    # Avanços com data: precisamos da data fim de cada semana lançada
    avancos = (
        db.query(EapAvancoSemanal, Semana)
        .outerjoin(Semana, Semana.codigo == EapAvancoSemanal.semana_codigo)
        .all()
    )
    # Acumulados por código: anterior e atual
    acum_anterior: dict[str, float] = {}
    acum_atual: dict[str, float] = {}
    for av, sem in avancos:
        codigo = av.eap_codigo
        delta = av.pct_delta or 0.0
        # Data de referência prioriza data_fim da semana; senão usa
        # data de lançamento; em último caso, hoje (não perde o registro).
        if sem and sem.data_fim:
            ref = sem.data_fim
        elif av.lancado_em:
            ref = av.lancado_em.date()
        else:
            ref = date.today()
        if ref < primeiro_dia:
            acum_anterior[codigo] = acum_anterior.get(codigo, 0.0) + delta
            acum_atual[codigo] = acum_atual.get(codigo, 0.0) + delta
        elif ref < primeiro_dia_seguinte:
            acum_atual[codigo] = acum_atual.get(codigo, 0.0) + delta

    # Codigos a incluir: previsão do mês ∪ qualquer item com acum
    codigos = set(previsoes) | set(acum_atual) | set(acum_anterior)
    if not codigos:
        return []

    itens_db = {i.codigo: i for i in db.query(EapItem).filter(EapItem.codigo.in_(codigos)).all()}

    out: list[EapItemMedicaoOut] = []
    for codigo in sorted(codigos):
        it = itens_db.get(codigo)
        if not it:
            continue
        ant = acum_anterior.get(codigo, 0.0)
        atu = acum_atual.get(codigo, 0.0)
        periodo = atu - ant
        valor = it.valor or 0.0
        out.append(EapItemMedicaoOut(
            eap_codigo=codigo,
            descricao=it.descricao,
            valor=valor,
            unidade=it.unidade or '%',
            criterio=it.criterio,
            pct_previsto=previsoes[codigo].pct_previsto if codigo in previsoes else 0.0,
            pct_acum_anterior=ant,
            pct_acum_atual=atu,
            pct_periodo=periodo,
            valor_periodo=valor * periodo / 100.0,
            valor_acum_total=valor * atu / 100.0,
        ))
    return out


# ── Geração do PDF da EAP (padrão Petrobras) ─────────────────────────────────

@router.get("/gerar-pdf")
def endpoint_gerar_eap_pdf(
    revisao:     str = Query(default="H",   description="Letra da revisão"),
    data_doc:    Optional[str] = Query(default=None, description="Data DD/MM/YYYY"),
    execucao:    str = Query(default="Diego Souza"),
    verificacao: str = Query(default="Lucas Barros"),
    aprovacao:   str = Query(default="Eduardo Carnaúba"),
    db: Session = Depends(get_db),
):
    """Gera o PDF da EAP Financeira no padrão Petrobras (A3 landscape)."""
    itens = db.query(EapItem).order_by(EapItem.codigo).all()
    if not itens:
        raise HTTPException(404, "Nenhum item EAP importado.")
    try:
        pdf_bytes = gerar_eap_pdf(
            itens_db=itens,
            revisao=revisao,
            data_doc=data_doc,
            execucao=execucao,
            verificacao=verificacao,
            aprovacao=aprovacao,
        )
    except Exception as e:
        logger.exception("Erro ao gerar PDF da EAP")
        raise HTTPException(500, f"Erro ao gerar PDF: {type(e).__name__}: {e}")

    filename = f"ET-5275.00-2000-911-E6G-002={revisao}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
