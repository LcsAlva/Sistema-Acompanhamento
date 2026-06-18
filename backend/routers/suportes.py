from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..services.suportes_service import (
    FILTROS_MATERIAIS,
    carregar_catalogo,
    detalhe_suporte,
    consulta_operacional,
    listar_materiais,
    opcoes_filtros,
    resumo_catalogo,
    salvar_catalogo_upload,
)


router = APIRouter(prefix="/suportes", tags=["suportes"])


@router.get("/resumo")
def get_resumo():
    return resumo_catalogo()


@router.get("/limpeza-103")
def get_limpeza_103():
    return carregar_catalogo().get("limpeza_103")


@router.post("/importar")
def importar_catalogo(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Envie uma planilha .xlsx ou .xlsm")
    return salvar_catalogo_upload(file)


@router.get("/filtros")
def get_filtros():
    return opcoes_filtros()


@router.get("/materiais")
def get_materiais(
    codigo_suporte: str | None = Query(None),
    material: str | None = Query(None),
    tipo_material: str | None = Query(None),
    diametro_tubo: str | None = Query(None),
    faixa_diametro_tubo: str | None = Query(None),
    tipo: str | None = Query(None),
    item: str | None = Query(None),
    condicional: str | None = Query(None),
    status_validacao_material: str | None = Query(None),
    limite: int = Query(500, ge=1, le=2000),
):
    filtros = {
        "codigo_suporte": codigo_suporte,
        "material": material,
        "tipo_material": tipo_material,
        "diametro_tubo": diametro_tubo,
        "faixa_diametro_tubo": faixa_diametro_tubo,
        "tipo": tipo,
        "item": item,
        "condicional": condicional,
        "status_validacao_material": status_validacao_material,
    }
    filtros = {k: v for k, v in filtros.items() if k in FILTROS_MATERIAIS and v not in (None, "")}
    return listar_materiais(filtros, limite=limite)


@router.get("/consulta")
def consultar_material(
    codigo_suporte: str = Query(..., min_length=1),
    item: str | None = Query(None),
    tipo: str | None = Query(None),
    dn: str | None = Query(None),
):
    resultado = consulta_operacional(codigo_suporte, item=item, tipo=tipo, dn=dn)
    if not resultado:
        raise HTTPException(status_code=404, detail="Suporte nao encontrado")
    return resultado


@router.get("/{codigo_suporte}")
def get_detalhe(codigo_suporte: str):
    detalhe = detalhe_suporte(codigo_suporte)
    if not detalhe:
        raise HTTPException(status_code=404, detail="Suporte nao encontrado")
    return detalhe
