"""Gerador do PDF ANEXO I - RESUMO BM.

Documento separado do PDF de avanco (`gerar_previa_pdf`). Ele usa a mesma
saida de `montar_bm_completo`, mas apresenta um resumo executivo do BM em A3.
"""
from __future__ import annotations

import io
import os
from datetime import date
from math import ceil

from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOGO_PETRO = os.path.join(_HERE, "..", "assets", "petrobras.svg")
_LOGO_ETM = os.path.join(_HERE, "..", "assets", "etm_logo.png")

PAGE_W, PAGE_H = landscape(A3)
MARGIN = 24.0
CONTENT_W = PAGE_W - 2 * MARGIN

NAVY = colors.HexColor("#063057")
NAVY2 = colors.HexColor("#0A4778")
NAVY3 = colors.HexColor("#1260A0")
LIGHT = colors.HexColor("#F4F7FB")
GRID = colors.HexColor("#B8C2CC")
GREEN = colors.HexColor("#166534")
RED = colors.HexColor("#B91C1C")
BLACK = colors.black
WHITE = colors.white

F_REG = "Helvetica"
F_BOLD = "Helvetica-Bold"

MESES_PT = [
    "", "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _fmt_brl(v: float | None) -> str:
    if v is None:
        return "-"
    sinal = "-" if v < 0 else ""
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {s}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.2f}%".replace(".", ",")


def _truncate(c: canvas.Canvas, txt: str, max_w: float, font: str, fs: float) -> str:
    txt = str(txt or "")
    if c.stringWidth(txt, font, fs) <= max_w:
        return txt
    while txt and c.stringWidth(txt + "...", font, fs) > max_w:
        txt = txt[:-1]
    return txt + "..."


def _periodo(ano: int, mes: int) -> tuple[str, str]:
    fim = date(ano, mes, 25)
    ant_ano, ant_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    ini = date(ant_ano, ant_mes, 26)
    return ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")


def _bm_numero(ano: int, mes: int) -> int:
    return max(1, (ano - 2025) * 12 + (mes - 8) + 1)


def _draw_logo_etm(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    try:
        img = ImageReader(os.path.normpath(_LOGO_ETM))
        iw, ih = img.getSize()
        scale = min(w / iw, h / ih)
        c.drawImage(
            img, x + (w - iw * scale) / 2, y + (h - ih * scale) / 2,
            iw * scale, ih * scale, mask="auto", preserveAspectRatio=True,
        )
        return
    except Exception:
        pass
    c.setFillColor(NAVY)
    c.setFont(F_BOLD, 12)
    c.drawCentredString(x + w / 2, y + h / 2 - 4, "ETM")


def _draw_logo_petrobras(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    try:
        from svglib.svglib import svg2rlg

        rlg = svg2rlg(os.path.normpath(_LOGO_PETRO))
        if rlg and rlg.width and rlg.height:
            scale = min(w / rlg.width, h / rlg.height)
            c.saveState()
            c.translate(x + (w - rlg.width * scale) / 2, y + (h - rlg.height * scale) / 2)
            c.scale(scale, scale)
            renderPDF.draw(rlg, c, 0, 0)
            c.restoreState()
            return
    except Exception:
        pass
    c.setFillColor(colors.HexColor("#008542"))
    c.setFont(F_BOLD, 10)
    c.drawCentredString(x + w / 2, y + h / 2 - 4, "PETROBRAS")


def _draw_header(c: canvas.Canvas, dados: dict) -> float:
    ciclo = dados.get("ciclo") or {}
    ano = int(_get(ciclo, "ano", 0) or 0)
    mes = int(_get(ciclo, "mes", 0) or 0)
    numero_bm = _get(ciclo, "numero_bm", None) or f"BM-{ano}-{mes:02d}"
    status = _get(ciclo, "status", "") or ""
    bm_num = _bm_numero(ano, mes)
    ini, fim = _periodo(ano, mes)

    top = PAGE_H - MARGIN
    h = 72
    y = top - h

    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.rect(MARGIN, y, CONTENT_W, h, fill=0, stroke=1)

    logo_w = 92
    meta_w = 260
    resumo_w = 190
    title_w = CONTENT_W - logo_w - meta_w - resumo_w
    x0 = MARGIN
    x1 = x0 + logo_w
    x2 = x1 + title_w
    x3 = x2 + meta_w
    x4 = x3 + resumo_w

    for x in (x1, x2, x3):
        c.line(x, y, x, y + h)
    c.line(x0, y + h / 2, x1, y + h / 2)

    _draw_logo_etm(c, x0 + 8, y + h / 2 + 8, logo_w - 16, h / 2 - 14)
    _draw_logo_petrobras(c, x0 + 8, y + 7, logo_w - 16, h / 2 - 14)

    c.setFillColor(BLACK)
    c.setFont(F_BOLD, 16)
    c.drawCentredString(x1 + title_w / 2, y + h - 24, "ANEXO I - RESUMO BOLETIM DE MEDICAO")
    c.setFont(F_BOLD, 12)
    c.drawCentredString(x1 + title_w / 2, y + h - 43, f"{numero_bm} - {MESES_PT[mes]} {ano}")
    c.setFont(F_REG, 8)
    objeto = (
        "Servicos de engenharia, construcao civil, montagem eletromecanica, "
        "fornecimento de bens, comissionamento e operacao assistida - RECAP."
    )
    c.drawCentredString(x1 + title_w / 2, y + 12, _truncate(c, objeto, title_w - 14, F_REG, 8))

    c.setFont(F_BOLD, 8)
    c.drawString(x2 + 8, y + h - 16, "GERENCIA")
    c.setFont(F_REG, 8)
    c.drawString(x2 + 84, y + h - 16, "SRGE/SI-IV/REF/CMRECAP")
    c.setFont(F_BOLD, 8)
    c.drawString(x2 + 8, y + h - 32, "EMPRESA")
    c.setFont(F_REG, 8)
    c.drawString(x2 + 84, y + h - 32, "ETM ENGENHARIA LTDA")
    c.setFont(F_BOLD, 8)
    c.drawString(x2 + 8, y + h - 48, "PERIODO")
    c.setFont(F_REG, 8)
    c.drawString(x2 + 84, y + h - 48, f"{ini} A {fim}")
    c.setFont(F_BOLD, 8)
    c.drawString(x2 + 8, y + h - 64, "STATUS")
    c.setFont(F_REG, 8)
    c.drawString(x2 + 84, y + h - 64, str(status).upper() or "-")

    c.setFillColor(NAVY)
    c.rect(x3, y, resumo_w, h, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(F_BOLD, 11)
    c.drawCentredString(x3 + resumo_w / 2, y + h - 20, "RESUMO BM")
    c.setFont(F_BOLD, 22)
    c.drawCentredString(x3 + resumo_w / 2, y + 28, f"{bm_num:02d}")
    c.setFont(F_REG, 8)
    c.drawCentredString(x3 + resumo_w / 2, y + 12, f"{MESES_PT[mes]} / {ano}")

    return y - 14


def _kpi(c: canvas.Canvas, x: float, y: float, w: float, h: float, titulo: str, valor: str, detalhe: str, cor=BLACK):
    c.setFillColor(WHITE)
    c.setStrokeColor(GRID)
    c.roundRect(x, y, w, h, 4, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#4B5563"))
    c.setFont(F_BOLD, 7)
    c.drawString(x + 10, y + h - 14, titulo)
    c.setFillColor(cor)
    c.setFont(F_BOLD, 15)
    c.drawString(x + 10, y + h - 34, _truncate(c, valor, w - 20, F_BOLD, 15))
    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont(F_REG, 7)
    c.drawString(x + 10, y + 10, _truncate(c, detalhe, w - 20, F_REG, 7))


def _draw_kpis(c: canvas.Canvas, dados: dict, top_y: float) -> float:
    y = top_y - 48
    gap = 10
    w = (CONTENT_W - gap * 4) / 5
    vals = [
        ("ORCAMENTO (BAC)", _fmt_brl(dados.get("bac")), "total do contrato", NAVY),
        ("PREVISTO NO BM", _fmt_brl(dados.get("total_valor_previsto")), _fmt_pct(dados.get("total_pct_previsto")), NAVY2),
        ("REALIZADO NO BM", _fmt_brl(dados.get("total_valor_periodo")), _fmt_pct(dados.get("total_pct_periodo")), GREEN),
        ("DESVIO DO BM", _fmt_brl(dados.get("desvio_valor_periodo")), _fmt_pct(dados.get("desvio_pct_periodo")), GREEN if (dados.get("desvio_valor_periodo") or 0) >= 0 else RED),
        ("ACUMULADO REAL", _fmt_brl(dados.get("total_valor_acum")), _fmt_pct(dados.get("total_pct_acum")), NAVY3),
    ]
    for i, item in enumerate(vals):
        _kpi(c, MARGIN + i * (w + gap), y, w, 48, *item)
    return y - 18


def _sort_key(it: dict):
    try:
        return [int(p) for p in str(it.get("codigo") or "").split(".")]
    except Exception:
        return [0]


def _itens_visiveis(itens: list[dict]) -> list[dict]:
    out = []
    for it in itens:
        if (
            (it.get("pct_previsto") or 0) > 0
            or (it.get("pct_periodo") or 0) > 0
            or (it.get("pct_acumulado") or 0) > 0
            or (it.get("valor_previsto") or 0) > 0
            or (it.get("valor_periodo") or 0) > 0
        ):
            out.append(it)
    return sorted(out, key=_sort_key)


def _draw_table_header(c: canvas.Canvas, y: float) -> None:
    cols = _cols()
    c.setFillColor(NAVY)
    c.rect(MARGIN, y - 24, CONTENT_W, 24, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(F_BOLD, 7)
    for key, x, w, label, align in cols:
        if align == "left":
            c.drawString(x + 4, y - 15, label)
        else:
            c.drawCentredString(x + w / 2, y - 15, label)


def _cols():
    defs = [
        ("codigo", 72, "ITEM", "left"),
        ("descricao", None, "ESCOPO", "left"),
        ("valor", 92, "VALOR (R$)", "right"),
        ("prev_pct", 58, "% PREV.", "right"),
        ("prev_rs", 92, "R$ PREV.", "right"),
        ("real_pct", 58, "% REAL.", "right"),
        ("real_rs", 92, "R$ REAL.", "right"),
        ("desvio", 92, "DESVIO (R$)", "right"),
        ("acum", 58, "% ACUM.", "right"),
    ]
    fixo = sum(w for _, w, _, _ in defs if w is not None)
    flex = CONTENT_W - fixo
    x = MARGIN
    out = []
    for key, w, label, align in defs:
        width = flex if w is None else w
        out.append((key, x, width, label, align))
        x += width
    return out


def _draw_cell(c: canvas.Canvas, txt: str, x: float, y: float, w: float, align: str, font=F_REG, fs=6.2, color=BLACK):
    c.setFillColor(color)
    c.setFont(font, fs)
    txt = _truncate(c, txt, w - 8, font, fs)
    if align == "right":
        c.drawRightString(x + w - 4, y, txt)
    elif align == "center":
        c.drawCentredString(x + w / 2, y, txt)
    else:
        c.drawString(x + 4, y, txt)


def _draw_row(c: canvas.Canvas, y: float, it: dict, idx: int) -> None:
    cols = {key: (x, w, align) for key, x, w, _, align in _cols()}
    h = 15
    nivel = int(it.get("nivel") or 1)
    is_pai = not bool(it.get("is_folha"))
    bg = WHITE if idx % 2 else LIGHT
    fg = BLACK
    font = F_REG
    if is_pai:
        pal = [NAVY, NAVY2, NAVY3, colors.HexColor("#1A79C8")]
        bg = pal[min(max(nivel - 1, 0), len(pal) - 1)]
        fg = WHITE
        font = F_BOLD

    c.setFillColor(bg)
    c.rect(MARGIN, y - h, CONTENT_W, h, fill=1, stroke=0)
    c.setStrokeColor(GRID)
    c.setLineWidth(0.25)
    c.line(MARGIN, y - h, MARGIN + CONTENT_W, y - h)

    valor = float(it.get("valor") or 0.0)
    vp = float(it.get("valor_previsto") or 0.0)
    vr = float(it.get("valor_periodo") or 0.0)
    desvio = vr - vp
    base = y - 10.5

    _draw_cell(c, str(it.get("codigo") or ""), *cols["codigo"][:2], base, cols["codigo"][2], font, 6.2, fg)
    desc_x, desc_w, desc_align = cols["descricao"]
    _draw_cell(c, str(it.get("descricao") or ""), desc_x + (nivel - 1) * 5, base, desc_w - (nivel - 1) * 5, desc_align, font, 6.2, fg)
    _draw_cell(c, _fmt_brl(valor), *cols["valor"][:2], base, cols["valor"][2], font, 6.2, fg)
    _draw_cell(c, _fmt_pct(it.get("pct_previsto")), *cols["prev_pct"][:2], base, cols["prev_pct"][2], font, 6.2, fg)
    _draw_cell(c, _fmt_brl(vp), *cols["prev_rs"][:2], base, cols["prev_rs"][2], font, 6.2, fg)
    _draw_cell(c, _fmt_pct(it.get("pct_periodo")), *cols["real_pct"][:2], base, cols["real_pct"][2], font, 6.2, fg)
    _draw_cell(c, _fmt_brl(vr), *cols["real_rs"][:2], base, cols["real_rs"][2], font, 6.2, fg)
    dcolor = fg if is_pai else (GREEN if desvio >= 0 else RED)
    _draw_cell(c, _fmt_brl(desvio), *cols["desvio"][:2], base, cols["desvio"][2], F_BOLD if not is_pai else font, 6.2, dcolor)
    _draw_cell(c, _fmt_pct(it.get("pct_acumulado")), *cols["acum"][:2], base, cols["acum"][2], font, 6.2, fg)


def _footer(c: canvas.Canvas, page: int, pages: int) -> None:
    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont(F_REG, 7)
    c.drawString(MARGIN, 12, "ANEXO I - RESUMO BM")
    c.drawRightString(PAGE_W - MARGIN, 12, f"Pagina {page} de {pages}")


def gerar_fiscalizacao_pdf(dados: dict) -> bytes:
    """Gera o PDF ANEXO I - RESUMO BM a partir de montar_bm_completo."""
    itens = _itens_visiveis(dados.get("itens", []))
    row_h = 15
    first_table_top = PAGE_H - MARGIN - 72 - 14 - 48 - 18
    rows_first = max(1, int((first_table_top - MARGIN - 28) / row_h))
    rows_next = max(1, int((PAGE_H - MARGIN - 24 - MARGIN - 28) / row_h))
    total_pages = 1 if len(itens) <= rows_first else 1 + ceil((len(itens) - rows_first) / rows_next)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    ciclo = dados.get("ciclo") or {}
    ano = int(_get(ciclo, "ano", 0) or 0)
    mes = int(_get(ciclo, "mes", 0) or 0)
    c.setTitle(f"ANEXO I - RESUMO BM {ano}-{mes:02d}")
    c.setAuthor("ETM ENGENHARIA LTDA")

    page = 1
    y = _draw_header(c, dados)
    y = _draw_kpis(c, dados, y)
    _draw_table_header(c, y)
    y -= 24
    row_count = 0
    capacity = rows_first

    for idx, it in enumerate(itens):
        if row_count >= capacity:
            _footer(c, page, total_pages)
            c.showPage()
            page += 1
            y = PAGE_H - MARGIN
            _draw_table_header(c, y)
            y -= 24
            row_count = 0
            capacity = rows_next
        _draw_row(c, y, it, idx)
        y -= row_h
        row_count += 1

    if not itens:
        c.setFillColor(BLACK)
        c.setFont(F_REG, 10)
        c.drawString(MARGIN + 8, y - 20, "Nenhum item com previsto ou realizado para este BM.")

    _footer(c, page, total_pages)
    c.save()
    return buf.getvalue()
