from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SubTarefa, ProgramacaoSemanal
from ..schemas import SubTarefaCreate, SubTarefaUpdate, SubTarefaOut

router = APIRouter(prefix="/programacoes", tags=["sub-tarefas"])


@router.get("/{prog_id}/sub-tarefas", response_model=list[SubTarefaOut])
def listar_sub_tarefas(prog_id: int, db: Session = Depends(get_db)):
    prog = db.query(ProgramacaoSemanal).filter(ProgramacaoSemanal.id == prog_id).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Programação não encontrada")
    return prog.sub_tarefas


@router.post("/{prog_id}/sub-tarefas", response_model=SubTarefaOut, status_code=201)
def criar_sub_tarefa(prog_id: int, data: SubTarefaCreate, db: Session = Depends(get_db)):
    prog = db.query(ProgramacaoSemanal).filter(ProgramacaoSemanal.id == prog_id).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Programação não encontrada")
    sub = SubTarefa(programacao_id=prog_id, **data.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.patch("/{prog_id}/sub-tarefas/{sub_id}", response_model=SubTarefaOut)
def atualizar_sub_tarefa(prog_id: int, sub_id: int, data: SubTarefaUpdate, db: Session = Depends(get_db)):
    sub = db.query(SubTarefa).filter(
        SubTarefa.id == sub_id,
        SubTarefa.programacao_id == prog_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-tarefa não encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(sub, field, value)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{prog_id}/sub-tarefas/{sub_id}", status_code=204)
def deletar_sub_tarefa(prog_id: int, sub_id: int, db: Session = Depends(get_db)):
    sub = db.query(SubTarefa).filter(
        SubTarefa.id == sub_id,
        SubTarefa.programacao_id == prog_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-tarefa não encontrada")
    db.delete(sub)
    db.commit()
