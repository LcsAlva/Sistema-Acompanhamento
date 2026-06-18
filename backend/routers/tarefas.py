from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import Tarefa
from ..schemas import TarefaCreate, TarefaUpdate, TarefaOut

router = APIRouter(prefix="/tarefas", tags=["tarefas"])


@router.get("/", response_model=list[TarefaOut])
def listar_tarefas(
    disciplina: Optional[str] = None,
    area_unidade: Optional[str] = None,
    busca: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Tarefa)
    if disciplina:
        q = q.filter(Tarefa.disciplina == disciplina)
    if area_unidade:
        q = q.filter(Tarefa.area_unidade == area_unidade)
    if busca:
        termo = f"%{busca}%"
        q = q.filter(
            (Tarefa.activity_id.ilike(termo)) | (Tarefa.nome.ilike(termo))
        )
    return q.order_by(Tarefa.activity_id).limit(50).all()


@router.get("/{tarefa_id}", response_model=TarefaOut)
def obter_tarefa(tarefa_id: int, db: Session = Depends(get_db)):
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return tarefa


@router.post("/", response_model=TarefaOut, status_code=201)
def criar_tarefa(data: TarefaCreate, db: Session = Depends(get_db)):
    existing = db.query(Tarefa).filter(Tarefa.activity_id == data.activity_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="activity_id já existe")
    tarefa = Tarefa(**data.model_dump())
    db.add(tarefa)
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.put("/{tarefa_id}", response_model=TarefaOut)
def atualizar_tarefa(tarefa_id: int, data: TarefaUpdate, db: Session = Depends(get_db)):
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(tarefa, field, value)
    db.commit()
    db.refresh(tarefa)
    return tarefa


@router.delete("/{tarefa_id}", status_code=204)
def deletar_tarefa(tarefa_id: int, db: Session = Depends(get_db)):
    tarefa = db.query(Tarefa).filter(Tarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    db.delete(tarefa)
    db.commit()
