from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from ..database import get_db
from ..models import Semana, ProgramacaoSemanal, Tarefa
from ..schemas import SemanaCreate, SemanaOut, ProgramacaoComTarefa, ProgramacaoCreate, ProgramacaoUpdate, ProgramacaoOut
from datetime import date, datetime

from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/semanas", tags=["semanas"])


class SemanaUpdate(BaseModel):
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None


def _agregar_stats(db: Session, codigos: list[str]) -> dict[str, tuple[int, int, int]]:
    """Uma única query com GROUP BY devolve (qcron, qprog, qreal) por semana.

    Evita o N+1 de carregar todas as programações de cada semana em Python
    quando só precisamos das contagens. Retorna dict codigo -> (qcron, qprog, qreal).
    """
    if not codigos:
        return {}
    rows = db.query(
        ProgramacaoSemanal.semana,
        func.count().label("qcron"),
        func.sum(case((ProgramacaoSemanal.no_qprog == True, 1), else_=0)).label("qprog"),
        func.sum(
            case(
                (
                    (ProgramacaoSemanal.no_qprog == True)
                    & (ProgramacaoSemanal.qreal_concluida == True),
                    1,
                ),
                else_=0,
            )
        ).label("qreal"),
    ).filter(
        ProgramacaoSemanal.semana.in_(codigos)
    ).group_by(ProgramacaoSemanal.semana).all()
    return {r.semana: (int(r.qcron or 0), int(r.qprog or 0), int(r.qreal or 0)) for r in rows}


def _enrich_semana(s: Semana, stats: tuple[int, int, int] | None) -> SemanaOut:
    """Adiciona live_qcron/qprog/qreal para semanas não fechadas usando stats agregadas.

    Não re-aplica filtro pct_avanco: o import já é o filtro único do QCRON,
    usando pct_executado (equip_complete_pct). Todos os registros em
    programacao_semanal já são QCRON por definição.
    """
    out = SemanaOut.model_validate(s)
    if not s.fechada:
        qcron, qprog, qreal = stats or (0, 0, 0)
        out.live_qcron = qcron
        out.live_qprog = qprog
        out.live_qreal = qreal
        out.live_pct_exec = round(qreal / qprog * 100, 1) if qprog else 0.0
    return out


@router.get("/", response_model=list[SemanaOut])
def listar_semanas(db: Session = Depends(get_db)):
    semanas = db.query(Semana).order_by(Semana.codigo).all()
    abertas = [s.codigo for s in semanas if not s.fechada]
    stats = _agregar_stats(db, abertas)
    return [_enrich_semana(s, stats.get(s.codigo)) for s in semanas]


@router.get("/{codigo}", response_model=SemanaOut)
def obter_semana(codigo: str, db: Session = Depends(get_db)):
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")
    stats = _agregar_stats(db, [codigo]) if not semana.fechada else {}
    return _enrich_semana(semana, stats.get(codigo))


@router.post("/", response_model=SemanaOut, status_code=201)
def criar_semana(data: SemanaCreate, db: Session = Depends(get_db)):
    if db.query(Semana).filter(Semana.codigo == data.codigo).first():
        raise HTTPException(status_code=409, detail="Semana já existe")
    semana = Semana(**data.model_dump())
    db.add(semana)
    db.commit()
    db.refresh(semana)
    return semana


@router.put("/{codigo}", response_model=SemanaOut)
def atualizar_semana(codigo: str, data: SemanaUpdate, db: Session = Depends(get_db)):
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")
    if data.data_inicio is not None:
        semana.data_inicio = data.data_inicio
    if data.data_fim is not None:
        semana.data_fim = data.data_fim
    db.commit()
    db.refresh(semana)
    return semana


@router.delete("/{codigo}", status_code=204)
def deletar_semana(codigo: str, db: Session = Depends(get_db)):
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")
    # Remove programações vinculadas antes
    db.query(ProgramacaoSemanal).filter(ProgramacaoSemanal.semana == codigo).delete()
    db.delete(semana)
    db.commit()


# ── QCRON da semana ─────────────────────────────────────────────────────────

@router.get("/{codigo}/qcron", response_model=list[ProgramacaoComTarefa])
def qcron_da_semana(codigo: str, db: Session = Depends(get_db)):
    """
    Retorna todas as programacoes do QCRON para a semana:
    - inicio_prog <= data_fim_semana
    - termino_prog >= data_inicio_semana
    - pct_avanco < 100
    """
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")

    # programacao_semanal já contém só QCRON — o import é o filtro único
    progs = (
        db.query(ProgramacaoSemanal)
        .join(Tarefa)
        .filter(ProgramacaoSemanal.semana == codigo)
        .all()
    )
    return progs


@router.get("/{codigo}/qprog", response_model=list[ProgramacaoComTarefa])
def qprog_da_semana(codigo: str, db: Session = Depends(get_db)):
    """Retorna apenas as tarefas marcadas no QPROG (no_qprog=True)."""
    progs = (
        db.query(ProgramacaoSemanal)
        .filter(
            ProgramacaoSemanal.semana == codigo,
            ProgramacaoSemanal.no_qprog == True,
        )
        .all()
    )
    return progs


# ── Programacoes individuais ─────────────────────────────────────────────────

@router.patch("/{codigo}/programacoes/{prog_id}", response_model=ProgramacaoOut)
def atualizar_programacao(
    codigo: str,
    prog_id: int,
    data: ProgramacaoUpdate,
    db: Session = Depends(get_db)
):
    prog = db.query(ProgramacaoSemanal).filter(
        ProgramacaoSemanal.id == prog_id,
        ProgramacaoSemanal.semana == codigo,
    ).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Programação não encontrada")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(prog, field, value)
    db.commit()
    db.refresh(prog)
    return prog


class ProgramacoesBulkUpdate(BaseModel):
    """Payload para atualização em lote de programações da mesma semana."""
    ids: list[int]
    data: ProgramacaoUpdate


@router.patch("/{codigo}/programacoes", response_model=list[ProgramacaoOut])
def atualizar_programacoes_bulk(
    codigo: str,
    payload: ProgramacoesBulkUpdate,
    db: Session = Depends(get_db),
):
    """Atualiza N programações da semana em UMA transação.

    Substitui o padrão de N PATCHs paralelos disparados pelo frontend
    (ex.: "selecionar todas" no MontarQprog), reduzindo de N round-trips
    + N commits para 1 round-trip + 1 commit.
    """
    if not payload.ids:
        return []
    progs = db.query(ProgramacaoSemanal).filter(
        ProgramacaoSemanal.semana == codigo,
        ProgramacaoSemanal.id.in_(payload.ids),
    ).all()
    if len(progs) != len(set(payload.ids)):
        raise HTTPException(status_code=404, detail="Uma ou mais programações não encontradas")

    campos = payload.data.model_dump(exclude_none=True)
    if not campos:
        return progs
    for prog in progs:
        for field, value in campos.items():
            setattr(prog, field, value)
    db.commit()
    for prog in progs:
        db.refresh(prog)
    return progs


# ── Fechar semana (snapshot imutável) ───────────────────────────────────────

@router.post("/{codigo}/fechar")
def fechar_semana(codigo: str, db: Session = Depends(get_db)):
    """
    Congela os indicadores da semana. Após fechar:
    - snap_qcron/qprog/qreal ficam gravados e não são recalculados
    - fechada=True protege o histórico contra novas importações
    """
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")
    if semana.fechada:
        raise HTTPException(status_code=409, detail="Semana já está fechada")

    # programacao_semanal já contém só QCRON — não re-filtra pct_avanco
    todas = db.query(ProgramacaoSemanal).filter(
        ProgramacaoSemanal.semana == codigo
    ).all()

    qcron = todas  # todos os registros são QCRON por definição
    qprog = [p for p in todas if p.no_qprog]
    concluidas = [p for p in qprog if p.qreal_concluida]

    qcron_count = len(qcron)
    qprog_count = len(qprog)
    conc_count = len(concluidas)
    pct = round(conc_count / qprog_count * 100, 1) if qprog_count > 0 else 0.0

    semana.fechada = True
    semana.fechada_em = datetime.now()
    semana.snap_qcron = qcron_count
    semana.snap_qprog = qprog_count
    semana.snap_qreal = conc_count
    semana.snap_pct_exec = pct
    db.commit()
    db.refresh(semana)

    return {
        "semana": codigo,
        "fechada": True,
        "fechada_em": semana.fechada_em,
        "snap_qcron": qcron_count,
        "snap_qprog": qprog_count,
        "snap_qreal": conc_count,
        "snap_pct_exec": pct,
    }


@router.post("/{codigo}/reabrir")
def reabrir_semana(codigo: str, db: Session = Depends(get_db)):
    """Reabre uma semana fechada (apaga o snapshot)."""
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")
    semana.fechada = False
    semana.fechada_em = None
    semana.snap_qcron = None
    semana.snap_qprog = None
    semana.snap_qreal = None
    semana.snap_pct_exec = None
    db.commit()
    return {"semana": codigo, "fechada": False}


# ── Adiantamento manual ──────────────────────────────────────────────────────

class AdiantarRequest(BaseModel):
    tarefa_id: int

@router.post("/{codigo}/adiantar", response_model=ProgramacaoComTarefa, status_code=201)
def adiantar_atividade(codigo: str, data: AdiantarRequest, db: Session = Depends(get_db)):
    """Insere manualmente uma atividade no QPROG de uma semana (adiantamento)."""
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")

    tarefa = db.query(Tarefa).filter(Tarefa.id == data.tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    existing = db.query(ProgramacaoSemanal).filter(
        ProgramacaoSemanal.semana == codigo,
        ProgramacaoSemanal.tarefa_id == data.tarefa_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Atividade já está nesta semana")

    # Usa as datas reais do cronograma salvas na tarefa (Início/Término do P6)
    # inicio_atual/termino_atual são atualizados a cada importação
    inicio_prog = tarefa.inicio_atual or tarefa.inicio_lb
    termino_prog = tarefa.termino_atual or tarefa.termino_lb

    # Descobre a semana original com base no inicio_prog real
    semana_original = None
    ref_date = inicio_prog or termino_prog
    if ref_date:
        sem_orig = db.query(Semana).filter(
            Semana.data_inicio <= ref_date,
            Semana.data_fim >= ref_date,
        ).first()
        if sem_orig:
            semana_original = sem_orig.codigo

    prog = ProgramacaoSemanal(
        semana=codigo,
        tarefa_id=data.tarefa_id,
        inicio_prog=inicio_prog,
        termino_prog=termino_prog,
        no_qprog=True,
        adiantada=True,
        semana_original=semana_original,
    )
    db.add(prog)
    db.commit()
    db.refresh(prog)
    return prog


@router.delete("/{codigo}/programacoes/{prog_id}/adiantada", status_code=204)
def remover_adiantada(codigo: str, prog_id: int, db: Session = Depends(get_db)):
    """Remove uma atividade adiantada manualmente da semana."""
    prog = db.query(ProgramacaoSemanal).filter(
        ProgramacaoSemanal.id == prog_id,
        ProgramacaoSemanal.semana == codigo,
        ProgramacaoSemanal.adiantada == True,
    ).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Atividade adiantada não encontrada")
    db.delete(prog)
    db.commit()


# ── Indicadores ─────────────────────────────────────────────────────────────

@router.get("/{codigo}/indicadores")
def indicadores_da_semana(codigo: str, db: Session = Depends(get_db)):
    """
    Calcula IC, IP e acumulados para a semana.
    IC = QREAL concluidas / QPROG * 100
    IP = QPROG / QCRON * 100
    """
    semana = db.query(Semana).filter(Semana.codigo == codigo).first()
    if not semana:
        raise HTTPException(status_code=404, detail="Semana não encontrada")

    # programacao_semanal já contém só QCRON — não re-filtra pct_avanco
    todas = db.query(ProgramacaoSemanal).filter(
        ProgramacaoSemanal.semana == codigo
    ).all()

    qcron = todas  # todos os registros são QCRON por definição
    qprog = [p for p in todas if p.no_qprog]
    qreal = [p for p in qprog if p.qreal_concluida or p.pct_qreal > 0]
    concluidas = [p for p in qprog if p.qreal_concluida]

    qcron_count = len(qcron)
    qprog_count = len(qprog)
    concluidas_count = len(concluidas)

    ic = round(concluidas_count / qprog_count * 100, 1) if qprog_count > 0 else 0.0
    ip = round(qprog_count / qcron_count * 100, 1) if qcron_count > 0 else 0.0

    return {
        "semana": codigo,
        "qcron": qcron_count,
        "qprog": qprog_count,
        "qreal_concluidas": concluidas_count,
        "ic": ic,
        "ip": ip,
    }
