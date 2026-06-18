import io

import openpyxl

from backend.parsers.sigem_parser import parse_sigem


def _wb_bytes(rows: list[list]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_layout_real_consulta_geral_sigem():
    rows = [
        ["Consulta Geral - NOTIFICA GRUPO"],
        [""],
        ["Projeto: RECAP", "Documento: %", "Status: %"],
        [""],
        ["Documento", "Revisão", "Atalho", "Modificado em", "Incluido em", "Título", "Status",
         "Finalidade da Revisão", "Nível 1", "Nível 2", "Nível 3", "Nível 4", "Nível 5", "Nível 6",
         "Nível 7", "Nível 8"],
        ["DE-5275.00-25132-190-E6G-001", "A", "NÃO", "31/05/2026 08:01:10",
         "01/03/2026 09:15:00", "Titulo", "SEM WORKFLOW", "", "DOCUMENTACAO",
         "ENGENHARIA", "DESENHOS", "", "", "", "", ""],
    ]

    res = parse_sigem(_wb_bytes(rows))

    assert res["linha_cabecalho"] == 5
    assert res["colunas_detectadas"]["codigo_documento"] == "Documento"
    assert res["colunas_detectadas"]["modificado_em"] == "Modificado em"
    assert len(res["documentos"]) == 1
    doc = res["documentos"][0]
    assert doc["codigo_documento"] == "DE-5275.00-25132-190-E6G-001"
    assert doc["revisao"] == "A"
    assert doc["status"] == "SEM WORKFLOW"
    assert doc["modificado_em"].isoformat() == "2026-05-31T08:01:10"
    assert doc["nivel_2"] == "ENGENHARIA"
