"""Testes do parser da LD (Módulo 1 — Fase 2A).

Usa workbooks openpyxl em memória. O COLUMN_MAP é calibrado com a amostra
real depois; aqui validamos detecção de colunas, normalização de status,
parsing de datas/A4 e descoberta da linha de cabeçalho.
"""
import io

import openpyxl

from backend.parsers.ld_parser import parse_ld, _norm_header, COLUMN_MAP


def _wb_bytes(rows: list[list]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_detecta_colunas_basicas():
    rows = [
        ["Código Documento", "Título", "Disciplina", "Rev", "Status", "A4", "Data Prevista", "Emissão"],
        ["LD-001", "Planta Baixa", "CIVIL", "0", "SEM WORKFLOW", 2.5, "10/05/2026", "12/05/2026"],
    ]
    res = parse_ld(_wb_bytes(rows))
    assert res["colunas_detectadas"]["codigo_documento"]
    assert res["colunas_detectadas"]["status"]
    docs = res["documentos"]
    assert len(docs) == 1
    d = docs[0]
    assert d["codigo_documento"] == "LD-001"
    assert d["disciplina"] == "CIVIL"
    assert d["status"] == "SEM WORKFLOW"
    assert d["a4_equivalente"] == 2.5
    assert d["data_prevista"].isoformat() == "2026-05-10"
    assert d["data_emissao"].isoformat() == "2026-05-12"


def test_pula_linhas_de_titulo_antes_do_cabecalho():
    rows = [
        ["LISTA DE DOCUMENTOS - LD-5275", None, None],
        ["Contrato XYZ", None, None],
        ["Documento", "Status", "Disciplina"],
        ["LD-009", "EM ELABORACAO", "TUBULACAO"],
    ]
    res = parse_ld(_wb_bytes(rows))
    assert res["linha_cabecalho"] == 3  # cabeçalho real na 3ª linha (1-based)
    assert len(res["documentos"]) == 1
    assert res["documentos"][0]["codigo_documento"] == "LD-009"


def test_ignora_linhas_sem_codigo():
    rows = [
        ["Documento", "Status"],
        ["LD-1", "SEM WORKFLOW"],
        [None, "EM ANALISE"],
        ["", "EM ANALISE"],
    ]
    res = parse_ld(_wb_bytes(rows))
    assert len(res["documentos"]) == 1
    assert res["ignoradas"] == 2


def test_norm_header_remove_acentos_e_pontuacao():
    assert _norm_header("Código do Documento") == "codigo do documento"
    assert _norm_header("A4-Equivalente") == "a4 equivalente"
    assert _norm_header("Revisão") == "revisao"
    # garante que os sinônimos chave estão no mapa
    assert COLUMN_MAP["codigo do documento"] == "codigo_documento"
    assert COLUMN_MAP["status"] == "status"


def test_a4_aceita_virgula_decimal():
    rows = [["Documento", "A4 Equivalente"], ["LD-1", "1,5"]]
    res = parse_ld(_wb_bytes(rows))
    assert res["documentos"][0]["a4_equivalente"] == 1.5


def test_layout_real_ld_5275(tmp_path):
    """Regressão: layout REAL da LD-5275.00-2000-940-E6G-001 (S5).

    Cabeçalho na linha 4; código em 'NÚMERO N-1710'; status em 'STATUS' com a
    grafia oficial 'SEM WORKFLOW'; datas prevista/efetiva e A4 equivalente.
    """
    rows = [
        ["", "", "LISTA DE DOCUMENTOS", "", "", "", "", "", "", "", "", "", "LD-5275", ""],
        ["", "", "ÁREA:", "URFCC", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "TÍTULO:", "LISTA DE DOCS", "", "", "", "", "", "", "", "", "", ""],
        ["ITEM", "NÚMERO N-1710", "REVISÃO", "NÚMERO RECAP", "REVISÃO RECAP", "TÍTULO",
         "UNIDADE/ ÁREA", "DISCIPLINA", "ORIGEM", "FORMATO", "FOLHAS", "A4 EQUIVALENTE",
         "LOG", "DATA PREVISTA DE EMISSÃO", "REPROGRAMAÇÃO", "DATA EFETIVA DE EMISSÃO",
         "ESCOPO", "PROPÓSITO", "OBSERVAÇÃO", "STATUS"],
        ["1", "DE-5275.00-25132-190-E6G-001", "A", "", "", "PRÉDIO TGV - ARQUITETURA",
         "U-25132", "ARQUITETURA", "DWG", "A1", 1, 8, "", "2026-03-25", "", "2026-01-28",
         "", "", "", "SEM WORKFLOW"],
        ["2", "DE-5275.00-5140-190-E6G-002", "0", "", "", "ABRIGO",
         "U-5140", "ARQUITETURA", "DWG", "A1", 1, 8, "", "2026-01-20", "", "",
         "", "", "", "EM ELABORAÇÃO"],
    ]
    res = parse_ld(_wb_bytes(rows))
    assert res["linha_cabecalho"] == 4
    cd = res["colunas_detectadas"]
    assert cd["codigo_documento"] == "NÚMERO N-1710"
    assert cd["status"] == "STATUS"
    assert cd["a4_equivalente"] == "A4 EQUIVALENTE"
    assert cd["data_emissao"] == "DATA EFETIVA DE EMISSÃO"
    docs = res["documentos"]
    assert len(docs) == 2
    assert docs[0]["codigo_documento"] == "DE-5275.00-25132-190-E6G-001"
    assert docs[0]["status"] == "SEM WORKFLOW"
    assert docs[0]["disciplina"] == "ARQUITETURA"
    assert docs[0]["a4_equivalente"] == 8
    assert docs[0]["data_emissao"].isoformat() == "2026-01-28"
    # 'NÚMERO RECAP' (alternativo, vazio) NÃO deve sobrescrever o código oficial
    assert docs[1]["codigo_documento"] == "DE-5275.00-5140-190-E6G-002"
