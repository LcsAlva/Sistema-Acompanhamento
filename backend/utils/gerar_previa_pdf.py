"""Gerador do PDF da Prévia / BM — Boletim de Medição Mensal.

Replica o modelo oficial da ETM ("PRÉVIA EM AVANÇO"): A4 retrato, com o
cabeçalho de identificação (logos + título + gerência/empresa + caixa
"PREVISTO BM N" + selo de status) e a tabela de medição com as colunas:

  ITEM · NÍVEL EAP · ESCOPO · VALOR (R$) · Previsto (% / R$) · Período (% / R$)

A coluna "Período %" é destacada:
  - verde  (#91CF50) quando o período atingiu/superou o previsto
  - amarelo(#FFFF00) quando o período ficou abaixo do previsto
"""
from __future__ import annotations

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOGO_PETRO = os.path.join(_HERE, '..', 'assets', 'petrobras.svg')
_LOGO_ETM   = os.path.join(_HERE, '..', 'assets', 'etm_logo.png')

# ── Página ────────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4                      # 595.27 × 841.89 pt
MARGIN_L = 24.0
MARGIN_R = 24.0
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R # ≈ 547 pt
MARGIN_T = 24.0                          # margem superior
MARGIN_B = 24.0

# ── Cabeçalho de identificação ────────────────────────────────────────────────
HEADER_H   = 56.0    # bloco de logos / título / status
COLHDR_H   = 26.0    # faixa de cabeçalho de colunas (2 sub-linhas)

# ── Linhas de dados ───────────────────────────────────────────────────────────
ROW_H    = 13.0
FS_DATA  = 5.2
FS_COL   = 5.6
FS_TITLE = 6.2

# ── Cores ─────────────────────────────────────────────────────────────────────
NAVY  = colors.HexColor('#063057')
NAVY2 = colors.HexColor('#0A4778')
NAVY3 = colors.HexColor('#1260A0')
NAVY4 = colors.HexColor('#1A79C8')
WHITE = colors.white
BLACK = colors.black
LGRAY = colors.HexColor('#F4F4F2')
HGRAY = colors.HexColor('#D9D9D9')
GREEN = colors.HexColor('#91CF50')   # período ≥ previsto
YELLOW = colors.HexColor('#FFFF00')  # período < previsto
LINE  = colors.HexColor('#9AA0A6')

WBS_BG = [NAVY, NAVY2, NAVY3, NAVY4]   # níveis 1-4

F_BOLD = 'Helvetica-Bold'
F_REG  = 'Helvetica'

MESES_PT = [
    '', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO',
    'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO',
]

# ── Colunas: (chave, largura, rótulo) — largura None = ESCOPO (flex) ──────────
_COLS = [
    ('item',  40,   'ITEM'),
    ('niv',   32,   'NÍVEL EAP'),
    ('desc',  None, 'ESCOPO'),
    ('valor', 100,  'VALOR (R$)'),
    ('pp',    40,   '%'),    # Previsto %
    ('pr',    62,   'R$'),   # Previsto R$
    ('op',    40,   '%'),    # Período %
    ('or',    62,   'R$'),   # Período R$
]


# ── Formatadores ──────────────────────────────────────────────────────────────

def _fmt_brl(v: float | None) -> str:
    """Número no formato brasileiro, sem o prefixo R$ (desenhado à parte)."""
    if v is None:
        return ''
    s = f'{abs(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return s if v >= 0 else f'-{s}'


def _fmt_pct(frac: float | None) -> str:
    """Fração 0–1 → 'XX,XX%'."""
    if not frac:
        return '—'
    return f'{frac * 100:.2f}'.replace('.', ',') + '%'


def _truncate(c: canvas.Canvas, txt: str, max_w: float, font: str, fs: float) -> str:
    """Trunca texto para caber em max_w (usa a métrica real da fonte)."""
    if not txt:
        return ''
    if c.stringWidth(txt, font, fs) <= max_w:
        return txt
    while txt and c.stringWidth(txt + '…', font, fs) > max_w:
        txt = txt[:-1]
    return txt + '…'


# ── Propagação do previsto para os pais (média ponderada por R$) ─────────────

def _propagar_previsto(itens: list[dict]) -> dict[str, float]:
    """Devolve {codigo: pct_previsto} com os pais calculados pelos filhos."""
    por_cod = {it['codigo']: it for it in itens}
    filhos: dict[str, list[dict]] = {}
    for it in itens:
        p = it.get('parent_codigo')
        if p:
            filhos.setdefault(p, []).append(it)

    prev: dict[str, float] = {}
    # folhas primeiro
    for it in itens:
        if not it.get('is_folha'):
            continue
        prev[it['codigo']] = it.get('pct_previsto') or 0.0

    # pais bottom-up (código mais longo primeiro)
    for it in sorted(itens, key=lambda x: -len(x['codigo'])):
        cod = it['codigo']
        if it.get('is_folha'):
            continue
        fs = filhos.get(cod, [])
        val = it.get('valor') or 0.0
        if not fs or val <= 0:
            prev[cod] = it.get('pct_previsto') or 0.0
            continue
        soma = sum((f.get('valor') or 0.0) * prev.get(f['codigo'], 0.0) for f in fs)
        prev[cod] = soma / val
    return prev


# ── Logos ─────────────────────────────────────────────────────────────────────

def _draw_logo_etm(c: canvas.Canvas, x, y, w, h):
    try:
        from reportlab.lib.utils import ImageReader
        img = ImageReader(os.path.normpath(_LOGO_ETM))
        iw, ih = img.getSize()
        m = 3
        scale = min((w - 2 * m) / iw, (h - 2 * m) / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh,
                    mask='auto', preserveAspectRatio=True)
        return
    except Exception:
        pass
    c.setFillColor(colors.HexColor('#5B8F2E'))
    c.setFont(F_BOLD, min(h * 0.5, 13))
    c.drawCentredString(x + w / 2, y + h * 0.35, 'etm')


def _draw_logo_petrobras(c: canvas.Canvas, x, y, w, h):
    try:
        from svglib.svglib import svg2rlg
        rlg = svg2rlg(os.path.normpath(_LOGO_PETRO))
        if rlg and rlg.width > 0 and rlg.height > 0:
            m = 3
            scale = min((w - 2 * m) / rlg.width, (h - 2 * m) / rlg.height)
            c.saveState()
            c.translate(x + (w - rlg.width * scale) / 2,
                        y + (h - rlg.height * scale) / 2)
            c.scale(scale, scale)
            renderPDF.draw(rlg, c, 0, 0)
            c.restoreState()
            return
    except Exception:
        pass
    c.setFillColor(colors.HexColor('#008542'))
    c.setFont(F_BOLD, min(h * 0.42, 10))
    c.drawCentredString(x + w / 2, y + h * 0.35, 'PETROBRAS')


# ── Cabeçalho de identificação (logos + título + status) ─────────────────────

def _draw_header(c: canvas.Canvas, top_y: float, *, bm_num: int, mes: int,
                 ano, periodo_ini: str, periodo_fim: str, status_lbl: str,
                 box_status: str):
    """Desenha o bloco de cabeçalho. top_y = topo do bloco."""
    x0 = MARGIN_L
    y0 = top_y - HEADER_H
    h  = HEADER_H

    # Larguras das 5 colunas do cabeçalho
    w_logo = 56.0
    w_ger  = 92.0
    w_box  = 96.0
    w_av   = 79.0
    w_tit  = CONTENT_W - w_logo - w_ger - w_box - w_av

    c.setLineWidth(0.6)
    c.setStrokeColor(BLACK)
    c.rect(x0, y0, CONTENT_W, h, fill=0, stroke=1)

    xa = x0
    xb = xa + w_logo
    xc = xb + w_tit
    xd = xc + w_ger
    xe = xd + w_box
    for xv in (xb, xc, xd, xe):
        c.line(xv, y0, xv, y0 + h)

    half = y0 + h / 2

    # ── Col 1 — logos (ETM em cima, Petrobras embaixo) ───────────────────────
    c.line(xa, half, xb, half)
    _draw_logo_etm(c, xa, half, w_logo, h / 2)
    _draw_logo_petrobras(c, xa, y0, w_logo, h / 2)

    # ── Col 2 — título + descrição ───────────────────────────────────────────
    c.line(xb, half, xc, half)
    c.setFillColor(BLACK)
    c.setFont(F_BOLD, FS_TITLE)
    titulo = f'PRÉVIA BOLETIM DE MEDIÇÃO {bm_num:02d} - {MESES_PT[mes]} {ano}'
    c.drawCentredString(xb + w_tit / 2, half + h / 2 - FS_TITLE - 1,
                        _truncate(c, titulo, w_tit - 6, F_BOLD, FS_TITLE))
    desc = ('Serviços de elaboração de engenharia de detalhamento, demolições e '
            'desmontagens, construção civil, montagem eletromecânica, fornecimento '
            'de bens, assistência técnica, comissionamento e operação assistida '
            'para o projeto Revamp URFCC caldeira de CO (U-570), a ser implementado '
            'na Refinaria de Capuava - RECAP, da PETROBRAS.')
    _draw_wrapped(c, desc, xb + 3, half - 3, w_tit - 6, 3.6, F_REG, h / 2 - 4)

    # ── Col 3 — Gerência / Empresa ───────────────────────────────────────────
    c.line(xc, half, xd, half)
    qy = (half + h / 2 + y0 + half) / 2  # não usado; mantemos layout simples
    c.setFont(F_BOLD, 4.6)
    c.setFillColor(BLACK)
    c.drawString(xc + 3, y0 + h - 7, 'GERÊNCIA')
    c.setFont(F_REG, 5.0)
    c.drawString(xc + 3, half + 3, 'SRGE/SI-IV/REF/CMRECAP')
    c.setFont(F_BOLD, 4.6)
    c.drawString(xc + 3, half - 7, 'EMPRESA')
    c.setFont(F_REG, 5.4)
    c.drawString(xc + 3, y0 + 4, 'ETM ENGENHARIA LTDA')

    # ── Col 4 — caixa "PREVISTO BM N" + período ──────────────────────────────
    c.setFillColor(BLACK)
    c.setFont(F_BOLD, 9.0)
    c.drawCentredString(xd + w_box / 2, y0 + h - 13, f'PREVISTO BM {bm_num:02d} -')
    c.drawCentredString(xd + w_box / 2, y0 + h - 23, box_status)
    c.setFont(F_BOLD, 8.0)
    c.drawCentredString(xd + w_box / 2, y0 + h - 35, f'{periodo_ini} A')
    c.drawCentredString(xd + w_box / 2, y0 + h - 44, periodo_fim)

    # ── Col 5 — selo de status ───────────────────────────────────────────────
    c.setFont(F_BOLD, 9.5)
    c.drawCentredString(xe + w_av / 2, half - 4, status_lbl)


def _draw_wrapped(c, txt, x, y_top, max_w, fs, font, max_h):
    """Quebra `txt` em linhas para caber em max_w; desenha de cima para baixo."""
    c.setFont(font, fs)
    palavras = txt.split()
    linhas, cur = [], ''
    for p in palavras:
        teste = (cur + ' ' + p).strip()
        if c.stringWidth(teste, font, fs) <= max_w:
            cur = teste
        else:
            if cur:
                linhas.append(cur)
            cur = p
    if cur:
        linhas.append(cur)
    lh = fs + 1.2
    max_linhas = max(1, int(max_h / lh))
    c.setFillColor(BLACK)
    for i, ln in enumerate(linhas[:max_linhas]):
        c.drawString(x, y_top - (i + 1) * lh + 2, ln)


# ── Cabeçalho de colunas (2 sub-linhas) ──────────────────────────────────────

def _col_x() -> list[tuple]:
    """Resolve a largura do ESCOPO e devolve [(chave, x, w, rótulo), ...]."""
    fixo = sum(w for _, w, _ in _COLS if w is not None)
    desc_w = CONTENT_W - fixo
    out, cx = [], MARGIN_L
    for key, w, lbl in _COLS:
        ww = desc_w if w is None else w
        out.append((key, cx, ww, lbl))
        cx += ww
    return out


def _draw_col_headers(c: canvas.Canvas, top_y: float):
    """Faixa navy de cabeçalho de colunas. top_y = topo da faixa."""
    cols = _col_x()
    y0 = top_y - COLHDR_H
    h  = COLHDR_H
    half = y0 + h / 2

    c.setFillColor(NAVY)
    c.rect(MARGIN_L, y0, CONTENT_W, h, fill=1, stroke=0)
    c.setStrokeColor(WHITE)
    c.setLineWidth(0.3)
    c.setFillColor(WHITE)

    cmap = {k: (x, w) for k, x, w, _ in cols}

    # ITEM, NÍVEL EAP, ESCOPO, VALOR — rótulo único centralizado verticalmente
    for key, lbl1, lbl2 in [('item', 'ITEM', None),
                            ('niv', 'NÍVEL', 'EAP'),
                            ('desc', 'DESCRIÇÃO', 'ESCOPO'),
                            ('valor', 'PONDERAÇÃO (R$)', 'VALOR (R$)')]:
        x, w = cmap[key]
        c.setFont(F_BOLD, FS_COL)
        if lbl2:
            c.drawCentredString(x + w / 2, half + 2, lbl1)
            c.drawCentredString(x + w / 2, half - FS_COL, lbl2)
        else:
            c.drawCentredString(x + w / 2, half - FS_COL / 2 + 1, lbl1)

    # Grupos Previsto / Período
    for grupo, k_pct, k_rs in [('Previsto', 'pp', 'pr'), ('Período', 'op', 'or')]:
        xp, wp = cmap[k_pct]
        xr, wr = cmap[k_rs]
        gx0, gx1 = xp, xr + wr
        c.setFont(F_BOLD, FS_COL)
        c.drawCentredString((gx0 + gx1) / 2, half + 3, grupo)
        c.line(gx0, half, gx1, half)
        c.setFont(F_BOLD, FS_COL - 0.4)
        c.drawCentredString(xp + wp / 2, half - FS_COL, '%')
        c.drawCentredString(xr + wr / 2, half - FS_COL, 'R$')

    # Linhas verticais separadoras. As divisórias INTERNAS dos grupos
    # (% | R$ de Previsto e de Período) só descem da metade para baixo —
    # não cortam o rótulo do grupo, igual ao modelo oficial.
    for key, x, w, _ in cols:
        if key in ('pp', 'op'):
            c.line(x + w, y0, x + w, half)       # apenas o sub-cabeçalho %/R$
        else:
            c.line(x + w, y0, x + w, y0 + h)     # altura total


# ── Linha de dados ───────────────────────────────────────────────────────────

def _draw_money(c: canvas.Canvas, x, w, base_y, valor: float, fg, font, fs):
    """Desenha 'R$' à esquerda e o número à direita dentro da célula."""
    txt = _fmt_brl(valor)
    if not txt or valor == 0:
        c.setFillColor(fg)
        c.setFont(font, fs)
        c.drawCentredString(x + w / 2, base_y, '—')
        return
    c.setFillColor(fg)
    c.setFont(font, fs)
    c.drawString(x + 3, base_y, 'R$')
    c.drawRightString(x + w - 3, base_y, txt)


def _draw_row(c: canvas.Canvas, cols, y: float, *, is_total: bool,
              codigo: str, nivel: int, descricao: str, valor: float,
              pct_prev: float, pct_per: float, leaf: bool):
    """Uma linha da tabela (CONTRATO ou item)."""
    cmap = {k: (x, w, lbl) for k, x, w, lbl in cols}

    # "Linha-folha" visual = níveis 5+ (fundo branco). Níveis 1-4 são tratados
    # como agrupadores (fundo navy) — inclusive folhas rasas como a
    # Administração Local (2.2), seguindo o modelo oficial.
    leaf_style = (not is_total) and (not nivel or nivel >= 5)

    if is_total:
        bg, fg, font = NAVY, WHITE, F_BOLD
    elif not leaf_style:
        bg, fg, font = WBS_BG[min((nivel or 1) - 1, 3)], WHITE, F_BOLD
    else:
        bg, fg, font = WHITE, BLACK, F_REG

    c.setFillColor(bg)
    c.rect(MARGIN_L, y - ROW_H, CONTENT_W, ROW_H, fill=1, stroke=0)

    base = y - ROW_H + (ROW_H - FS_DATA) / 2 + 0.5
    valor_prev = (valor or 0.0) * (pct_prev or 0.0)
    valor_per  = (valor or 0.0) * (pct_per or 0.0)

    # ITEM
    x, w, _ = cmap['item']
    c.setFillColor(fg); c.setFont(font, FS_DATA)
    c.drawCentredString(x + w / 2, base, codigo or '')
    # NÍVEL EAP
    x, w, _ = cmap['niv']
    c.drawCentredString(x + w / 2, base, '' if is_total else str(nivel or ''))
    # ESCOPO — agrupadores centralizados; folhas à esquerda com recuo
    x, w, _ = cmap['desc']
    indent = ((nivel or 1) - 1) * 3
    if not leaf_style:
        c.drawCentredString(x + w / 2, base,
                            _truncate(c, descricao, w - 6, font, FS_DATA))
    else:
        c.drawString(x + 3 + indent, base,
                     _truncate(c, descricao, w - 6 - indent, font, FS_DATA))
    # VALOR (R$)
    x, w, _ = cmap['valor']
    _draw_money(c, x, w, base, valor, fg, font, FS_DATA)
    # Previsto %
    x, w, _ = cmap['pp']
    c.setFillColor(fg); c.setFont(font, FS_DATA)
    c.drawCentredString(x + w / 2, base, _fmt_pct(pct_prev))
    # Previsto R$
    x, w, _ = cmap['pr']
    _draw_money(c, x, w, base, valor_prev, fg, font, FS_DATA)
    # Período % — destaque verde/amarelo só nas linhas-folha
    x, w, _ = cmap['op']
    if leaf_style and (pct_per or 0) > 0:
        hl = GREEN if (pct_per >= (pct_prev or 0) - 1e-6) else YELLOW
        c.setFillColor(hl)
        c.rect(x + 0.4, y - ROW_H + 0.4, w - 0.8, ROW_H - 0.8, fill=1, stroke=0)
        c.setFillColor(BLACK)
        c.setFont(F_BOLD, FS_DATA)
    else:
        c.setFillColor(fg); c.setFont(font, FS_DATA)
    c.drawCentredString(x + w / 2, base, _fmt_pct(pct_per))
    # Período R$
    x, w, _ = cmap['or']
    _draw_money(c, x, w, base, valor_per, fg, font, FS_DATA)

    # Bordas
    c.setStrokeColor(LINE)
    c.setLineWidth(0.25)
    c.line(MARGIN_L, y - ROW_H, MARGIN_L + CONTENT_W, y - ROW_H)
    for _, cx, cw, _ in cols:
        c.line(cx + cw, y - ROW_H, cx + cw, y)
    c.line(MARGIN_L, y - ROW_H, MARGIN_L, y)
    c.line(MARGIN_L + CONTENT_W, y - ROW_H, MARGIN_L + CONTENT_W, y)


# ── Função principal ─────────────────────────────────────────────────────────

def gerar_previa_pdf(dados: dict) -> bytes:
    """Gera o PDF da Prévia/BM no modelo oficial ETM (A4 retrato).

    dados = { 'ciclo': {...}, 'itens': [...], 'bac', 'total_pct_periodo',
              'total_pct_acum', 'total_valor_periodo' }  — pct_* são frações 0–1.
    """
    ciclo_raw = dados['ciclo']
    itens     = dados.get('itens', [])
    bac       = dados.get('bac', 0.0) or 0.0
    total_valor_periodo = dados.get('total_valor_periodo', 0.0) or 0.0

    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    ano    = _get(ciclo_raw, 'ano', 0) or 0
    mes    = _get(ciclo_raw, 'mes', 0) or 0
    status = _get(ciclo_raw, 'status', 'aberto') or 'aberto'
    fechado = status == 'fechado'

    # Número do BM: ago/2025 = BM 01
    bm_num = max(1, (ano - 2025) * 12 + (mes - 8) + 1)

    # Período do ciclo: dia 26 do mês anterior a dia 25 do mês
    fim = date(ano, mes, 25)
    pm_ano, pm_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    ini = date(pm_ano, pm_mes, 26)
    periodo_ini = ini.strftime('%d/%m/%y')
    periodo_fim = fim.strftime('%d/%m/%y')

    status_lbl = 'FECHADO' if fechado else 'EM AVANÇO'
    box_status = 'FECHADO' if fechado else 'PRÉVIA'

    # ── Previsto propagado para os pais ──────────────────────────────────────
    prev_prop = _propagar_previsto(itens)

    # ── Itens visíveis: têm previsão, período ou acumulado ───────────────────
    def _rel(it):
        return ((prev_prop.get(it['codigo'], 0) or 0) > 0
                or (it.get('pct_periodo') or 0) > 0
                or (it.get('pct_acumulado') or 0) > 0
                or (it.get('valor_dist_mes') or 0) > 0)

    itens_vis = [it for it in itens if _rel(it)]

    def _sort_key(it):
        try:
            return [int(p) for p in (it.get('codigo') or '').split('.')]
        except Exception:
            return [0]
    itens_vis.sort(key=_sort_key)

    # ── Totais do contrato ───────────────────────────────────────────────────
    total_prev_valor = sum((it.get('valor') or 0.0) * prev_prop.get(it['codigo'], 0.0)
                           for it in itens if (it.get('nivel') == 1))
    total_pct_prev = (total_prev_valor / bac) if bac else 0.0
    total_pct_per  = (total_valor_periodo / bac) if bac else 0.0

    # ── Canvas ───────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f'Prévia BM {bm_num:02d} — {MESES_PT[mes].title()}/{ano}')
    c.setAuthor('ETM ENGENHARIA LTDA')

    cols = _col_x()

    # Linhas: CONTRATO + itens
    all_rows = [None] + itens_vis
    body_top = PAGE_H - MARGIN_T - HEADER_H - COLHDR_H
    rows_per_page = max(1, int((body_top - MARGIN_B) / ROW_H))

    hdr_kw = dict(bm_num=bm_num, mes=mes, ano=ano,
                  periodo_ini=periodo_ini, periodo_fim=periodo_fim,
                  status_lbl=status_lbl, box_status=box_status)

    idx = 0
    primeira = True
    while idx < len(all_rows):
        if not primeira:
            c.showPage()
        primeira = False

        _draw_header(c, PAGE_H - MARGIN_T, **hdr_kw)
        _draw_col_headers(c, PAGE_H - MARGIN_T - HEADER_H)

        y = body_top
        n = 0
        while idx < len(all_rows) and n < rows_per_page:
            row = all_rows[idx]
            if row is None:
                _draw_row(c, cols, y, is_total=True, codigo='CONTRATO',
                          nivel=0, descricao='', valor=bac,
                          pct_prev=total_pct_prev, pct_per=total_pct_per, leaf=False)
            else:
                _draw_row(
                    c, cols, y, is_total=False,
                    codigo=row.get('codigo') or '',
                    nivel=row.get('nivel') or 1,
                    descricao=row.get('descricao') or '',
                    valor=row.get('valor') or 0.0,
                    pct_prev=prev_prop.get(row['codigo'], 0.0),
                    pct_per=row.get('pct_periodo') or 0.0,
                    leaf=bool(row.get('is_folha')),
                )
            y -= ROW_H
            idx += 1
            n += 1

    c.save()
    return buf.getvalue()
