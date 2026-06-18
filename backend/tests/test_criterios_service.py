"""Testes da Matriz de Critérios (Módulo 3 — Fase 2A)."""
from backend.models import CriterioMedicao, EapItem, LdDocumento
from backend.services import criterios_service as svc


def _eap(db, codigo, descricao="Item", nivel=1, valor=100.0):
    it = EapItem(codigo=codigo, descricao=descricao, nivel=nivel, valor=valor)
    db.add(it)
    db.flush()
    return it


def test_seed_cria_um_criterio_por_eap(db):
    _eap(db, "1")
    _eap(db, "1.1")
    db.commit()
    res = svc.seed_from_eap(db)
    assert res["criados"] == 2
    assert db.query(CriterioMedicao).count() == 2
    # idempotente
    res2 = svc.seed_from_eap(db)
    assert res2["criados"] == 0


def test_upsert_e_listagem(db):
    svc.upsert_criterio(db, {"codigo_eap": "2.1", "tipo_criterio": "DOCUMENTO_SEM_WORKFLOW",
                             "parametros": {"disciplina": "CIVIL"}, "peso": 2.0})
    crit = svc.get_criterio(db, "2.1")
    assert crit.tipo_criterio == "DOCUMENTO_SEM_WORKFLOW"
    assert crit.peso == 2.0
    assert '"disciplina": "CIVIL"' in crit.parametros
    # update no mesmo codigo_eap não duplica
    svc.upsert_criterio(db, {"codigo_eap": "2.1", "tipo_criterio": "MANUAL"})
    assert db.query(CriterioMedicao).filter_by(codigo_eap="2.1").count() == 1
    assert svc.get_criterio(db, "2.1").tipo_criterio == "MANUAL"


def test_handler_documento_sem_workflow_calcula_da_ld(db):
    _eap(db, "2.1.1", descricao="Engenharia")
    db.add(LdDocumento(codigo_documento="D1", status="SEM WORKFLOW", disciplina="CIVIL", a4_equivalente=1.0))
    db.add(LdDocumento(codigo_documento="D2", status="EM ANALISE", disciplina="CIVIL", a4_equivalente=1.0))
    svc.upsert_criterio(db, {"codigo_eap": "2.1.1", "tipo_criterio": "DOCUMENTO_SEM_WORKFLOW",
                             "parametros": {"disciplina": "CIVIL"}})
    res = svc.avaliar_criterio(db, "2.1.1")
    assert res["implementado"] is True
    assert res["pct"] == 0.5          # 1 apto de 2 (A4 1/2)
    assert res["evidencias"]


def test_tipo_nao_implementado_retorna_pendente(db):
    _eap(db, "3.1")
    svc.upsert_criterio(db, {"codigo_eap": "3.1", "tipo_criterio": "PESO_TUBULACAO"})
    res = svc.avaliar_criterio(db, "3.1")
    assert res["implementado"] is False
    assert res["fonte_pendente"] is True
    assert res["pct"] == 0.0


def test_manual_e_default_para_item_sem_criterio(db):
    _eap(db, "4.1")
    db.commit()
    res = svc.avaliar_criterio(db, "4.1")   # sem critério cadastrado
    assert res["tipo_criterio"] == "MANUAL"
    assert res["manual"] is True
    assert res["pct"] is None


def test_listar_tipos_catalogo():
    assert "DOCUMENTO_SEM_WORKFLOW" in svc.TIPOS_CRITERIO
    assert svc.TIPOS_CRITERIO["MANUAL"]["implementado"] is True
    assert svc.TIPOS_CRITERIO["ESTACA"]["implementado"] is False
