"""Gerador do PDF da EAP Financeira — padrão Petrobras.

Layout: A3 landscape, cabeçalho de norma em cada folha, rodapé com bloco
de título padrão ETM/PETROBRAS.

Medidas derivadas do PDF original via pdfplumber (em pontos — 1pt = 1/72"):
  - ROW_H = 5.8pt  (espaçamento entre linhas consecutivas)
  - FS_DATA = 3.0pt (fonte de dados ≈ Excel 13pt × 22% ≈ 2.9pt)
  - MARGIN_L = 18pt (x0 do código do item ≈ 33.8, centro da col ITEM)
  - BODY_DATA_TOP = 780pt  (baseline 1ª linha de dados, da base da página)
  - BODY_BOT = 95pt  (baseline última linha antes do rodapé)
  - Col ITEM = 39pt, NÍV = 18pt, ESCOPO = 123pt,
    VALOR = 45pt, % = 18pt, R$ACUM = 41pt, col mensal = 27.3pt
"""
from __future__ import annotations

import io
import json
from datetime import date
from typing import Optional

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF

# Caminho do logo Petrobras (SVG)
_HERE = os.path.dirname(os.path.abspath(__file__))
_LOGO_SVG = os.path.join(_HERE, '..', 'assets', 'petrobras.svg')

# ── Tamanho de página ─────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(A3)          # 1190.55 × 841.89 pt

# ── Margens (em pontos, medidas no PDF original) ──────────────────────────────
MARGIN_L  = 18.0    # pt — margem esquerda
MARGIN_R  = 42.0    # pt — margem direita  → CONTENT_W ≈ 1130.55 pt
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# ── Área de dados ─────────────────────────────────────────────────────────────
# Coordenadas ReportLab: y = 0 na base, y = PAGE_H no topo
BODY_DATA_TOP = 780.0   # y (da base) onde fica o baseline da 1ª linha de dados
COL_HDR_H     = 12.0    # pt — faixa de cabeçalho de colunas (acima dos dados)
BODY_TOP      = BODY_DATA_TOP + COL_HDR_H   # = 792.0 pt
BODY_BOT      = 55.0    # pt — y mínimo; abaixo fica o rodapé

# Cabeçalho de página (acima de BODY_TOP, até PAGE_H)
HDR_TOTAL = PAGE_H - BODY_TOP          # ≈ 49.89 pt  (duas faixas coloridas)
HDR_H1    = round(HDR_TOTAL * 0.55)    # faixa 1 — maior (título / rev)
HDR_H2    = HDR_TOTAL - HDR_H1         # faixa 2 — menor (contrato / folha)

# Rodapé (abaixo de BODY_BOT)
FTR_BOT   = 3.0                        # pt de margem na borda inferior
FTR_H     = BODY_BOT - FTR_BOT         # ≈ 92 pt para o bloco título Petrobras

# ── Altura de linha ───────────────────────────────────────────────────────────
ROW_H = 5.8     # pt — medido no PDF original (y-diff entre linhas consecutivas)

# ── Larguras das colunas fixas (pt) ──────────────────────────────────────────
COL_ITEM  = 39
COL_NIVEL = 18
COL_DESC  = 123
COL_VALOR = 45
COL_PCT   = 18
COL_RACUM = 41
COL_FIXED = COL_ITEM + COL_NIVEL + COL_DESC + COL_VALOR + COL_PCT + COL_RACUM
# = 284 pt  →  col mensais de 27.3 pt cada para 31 meses: (1130.55-284)/31 ≈ 27.3 ✓

# ── Tamanhos de fonte (pt) ────────────────────────────────────────────────────
FS_DATA  = 3.0     # dados (≈ Excel 13pt × 22%)
FS_COL   = 3.5     # cabeçalho de colunas
FS_HDR   = 7.0     # faixas do cabeçalho de página
FS_FOOT  = 5.5     # texto do rodapé
FS_TITLE = 7.0     # título grande no rodapé

# ── Paleta de cores ───────────────────────────────────────────────────────────
NAVY  = colors.HexColor('#063057')
NAVY2 = colors.HexColor('#0A4778')
NAVY3 = colors.HexColor('#1260A0')
NAVY4 = colors.HexColor('#1A79C8')
NAVY5 = colors.HexColor('#2E86C1')
NAVY6 = colors.HexColor('#5DADE2')
WHITE = colors.white
LGRAY = colors.HexColor('#E8E8E8')
MGRAY = colors.HexColor('#B0B0B0')
BLACK = colors.black

WBS_BG = [NAVY, NAVY2, NAVY3, NAVY4, NAVY5, NAVY6]

F_BOLD = 'Helvetica-Bold'
F_REG  = 'Helvetica'


# ── Formatadores ──────────────────────────────────────────────────────────────

def _fmt_brl(v: float) -> str:
    if not v:
        return '-'
    s = f'{abs(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {s}' if v >= 0 else f'R$ -{s}'


def _fmt_pct(v: float) -> str:
    return f'{v:.2f}%' if v is not None else '-'


def _label_mes(iso: str) -> str:
    """'2025-08-01' → 'ago/25'"""
    meses = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
             'jul', 'ago', 'set', 'out', 'nov', 'dez']
    try:
        y, m, _ = iso.split('-')
        return f'{meses[int(m)-1]}/{y[2:]}'
    except Exception:
        return iso


def _truncate(txt: str, max_w: float, fs: float) -> str:
    """Trunca texto para caber em max_w pontos (Helvetica ≈ 0.52 × fs / char)."""
    if not txt:
        return ''
    avg = fs * 0.52
    limit = max(2, int(max_w / avg))
    if len(txt) <= limit:
        return txt
    return txt[:limit - 1] + '…'


# ── Função principal ──────────────────────────────────────────────────────────

def gerar_eap_pdf(
    itens_db: list,
    revisao: str = 'H',
    data_doc: Optional[str] = None,
    execucao: str = 'Diego Souza',
    verificacao: str = 'Lucas Barros',
    aprovacao: str = 'Eduardo Carnaúba',
    num_contrato: str = '5900.0131550.25.2',
    razao_social: str = 'ETM ENGENHARIA',
    resp_tecnico: str = 'Eduardo Carnaúba',
    reg_crea: str = '5071701282-SP',
    cliente: str = 'RECAP - REFINARIA DE CAPUAVA',
    programa: str = 'RECAP - REVAMP URFCC CALDEIRA DE CO',
    cod_doc: str = 'ET-5275.00-2000-911-E6G-002',
    area: str = 'URFCC (U-570) E UTGV (U-25132)',
    titulo: str = 'EAP FINANCEIRA',
    srge: str = 'SRGE/SI-IV/REF/CMRECAP',
) -> bytes:
    if not data_doc:
        data_doc = date.today().strftime('%d/%m/%Y')

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    c.setTitle(f'{cod_doc}={revisao} — {titulo}')
    c.setAuthor(razao_social)

    # ── Ordena itens por código numérico ──────────────────────────────────────
    def _sort_key(x):
        try:
            return [int(p) for p in x.codigo.split('.')]
        except Exception:
            return [0]

    itens = sorted(itens_db, key=_sort_key)

    # ── Detecta itens-pai (têm ao menos um filho) ─────────────────────────────
    codigos: set[str] = {it.codigo for it in itens if it.codigo}
    pais: set[str] = set()
    for cod in codigos:
        partes = cod.split('.')
        for i in range(1, len(partes)):
            pais.add('.'.join(partes[:i]))

    # ── Coleta e ordena meses ─────────────────────────────────────────────────
    meses_set: set[str] = set()
    for it in itens:
        if it.dist_mensal:
            try:
                meses_set.update(json.loads(it.dist_mensal).keys())
            except Exception:
                pass
    meses: list[str] = sorted(meses_set)
    n_meses = len(meses)

    # largura de coluna mensal: divide o espaço restante igualmente
    col_mes_w = (CONTENT_W - COL_FIXED) / max(n_meses, 1) if n_meses else 27.3

    # ── Totais do contrato (linha de cabeçalho de dados) ─────────────────────
    valor_total = sum(it.valor or 0 for it in itens if (it.nivel or 99) == 1)
    dist_total: dict[str, float] = {m: 0.0 for m in meses}
    for it in itens:
        if (it.nivel or 99) == 1 and it.dist_mensal:
            try:
                for m, v in json.loads(it.dist_mensal).items():
                    if m in dist_total:
                        dist_total[m] += v
            except Exception:
                pass

    # ── Calcula número total de páginas ──────────────────────────────────────
    rpp = max(1, int((BODY_DATA_TOP - BODY_BOT) / ROW_H))   # linhas por página
    all_rows = [None] + itens   # None = linha CONTRATO
    n_data_pages = max(1, -(-len(all_rows) // rpp))          # ceil
    total_pages = 1 + n_data_pages                            # capa + dados

    page_num = [0]

    def _new_page():
        page_num[0] += 1
        if page_num[0] > 1:
            c.showPage()

    ctx = dict(
        revisao=revisao, data_doc=data_doc,
        execucao=execucao, verificacao=verificacao, aprovacao=aprovacao,
        num_contrato=num_contrato, razao_social=razao_social,
        resp_tecnico=resp_tecnico, reg_crea=reg_crea,
        cliente=cliente, programa=programa, cod_doc=cod_doc,
        area=area, titulo=titulo, srge=srge,
    )

    # ── FOLHA 1 — CAPA ────────────────────────────────────────────────────────
    _new_page()
    _draw_capa(c, page_num[0], total_pages, **ctx)

    # ── FOLHAS DE DADOS ───────────────────────────────────────────────────────
    idx = 0
    while idx < len(all_rows):
        _new_page()
        _draw_page_header(c, page_num[0], total_pages, **ctx)
        _draw_page_footer(c, page_num[0], total_pages, **ctx)
        _draw_col_headers(c, meses, col_mes_w)

        y = BODY_DATA_TOP
        while idx < len(all_rows) and y - ROW_H >= BODY_BOT - 0.01:
            row = all_rows[idx]
            if row is None:
                _draw_row_total(c, valor_total, dist_total, meses, col_mes_w, y)
            else:
                try:
                    dm = json.loads(row.dist_mensal) if row.dist_mensal else {}
                except Exception:
                    dm = {}
                is_leaf = (row.codigo not in pais)
                _draw_row_item(c, row, dm, meses, col_mes_w, y, is_leaf)
            y -= ROW_H
            idx += 1

    c.save()
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de desenho
# ─────────────────────────────────────────────────────────────────────────────

def _draw_page_header(c: canvas.Canvas, pnum: int, total: int, **ctx):
    """Duas faixas navy no topo de cada página de dados."""
    x0 = MARGIN_L
    y1 = BODY_TOP           # base da faixa 2 = topo da área de dados
    y2 = y1 + HDR_H2        # base da faixa 1
    ytop = y2 + HDR_H1      # = PAGE_H (topo)

    # Faixa 1 (superior) — título
    c.setFillColor(NAVY)
    c.rect(x0, y2, CONTENT_W, HDR_H1, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(F_BOLD, FS_HDR)
    mid1 = y2 + HDR_H1 * 0.38
    c.drawString(x0 + 4, mid1, f'Rev.: {ctx["revisao"]}')
    c.drawCentredString(x0 + CONTENT_W * 0.42, mid1,
                        'RESUMO DA DISTRIBUIÇÃO CONTRATUAL')
    c.drawRightString(x0 + CONTENT_W - 4, mid1,
                      'DISTRIBUIÇÃO FINANCEIRA MENSAL (R$)')

    # Faixa 2 (inferior) — contrato / folha
    c.setFillColor(NAVY2)
    c.rect(x0, y1, CONTENT_W, HDR_H2, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(F_REG, FS_HDR - 1)
    mid2 = y1 + HDR_H2 * 0.35
    c.drawString(x0 + 4, mid2, f'CONTRATO Nº {ctx["num_contrato"]}')
    c.setFont(F_BOLD, FS_HDR - 1)
    c.drawCentredString(x0 + CONTENT_W * 0.42, mid2, 'DESCRIÇÃO')
    c.drawRightString(x0 + CONTENT_W - 4, mid2,
                      f'FOLHA {pnum} de {total}')


def _draw_page_footer(c: canvas.Canvas, pnum: int, total: int, **ctx):
    """Bloco título padrão ETM/Petrobras no rodapé."""
    x0 = MARGIN_L
    yb = FTR_BOT            # base do bloco
    h  = FTR_H              # altura do bloco ≈ 92 pt
    w  = CONTENT_W

    c.setLineWidth(0.4)
    c.setStrokeColor(BLACK)
    c.setFillColor(WHITE)

    # Borda externa
    c.rect(x0, yb, w, h, fill=0, stroke=1)

    mid = yb + h / 2
    c.line(x0, mid, x0 + w, mid)   # divisória horizontal

    # ── Linha inferior ──────────────────────────────────────────────────────
    c1w = w * 0.25
    c2w = w * 0.25
    c3w = w * 0.50
    c.line(x0 + c1w,       yb, x0 + c1w,       mid)
    c.line(x0 + c1w + c2w, yb, x0 + c1w + c2w, mid)

    fs = FS_FOOT - 0.5
    c.setFont(F_BOLD, fs)
    c.setFillColor(BLACK)
    _txt(c, f'RAZÃO SOCIAL: {ctx["razao_social"]}',
         x0 + 2, yb + h * 0.18, c1w - 4, fs)

    c.setFont(F_REG, fs)
    _txt(c, f'Nº CONTRATO: {ctx["num_contrato"]}',
         x0 + c1w + 2, yb + h * 0.30, c2w - 4, fs)
    _txt(c, f'REG CREA: {ctx["reg_crea"]}',
         x0 + c1w + 2, yb + h * 0.08, c2w - 4, fs)

    c4w = c3w * 0.60
    c5w = c3w * 0.40
    x34 = x0 + c1w + c2w
    c.line(x34 + c4w, yb, x34 + c4w, mid)
    _txt(c, f'ESPECIFICAÇÃO TÉCNICA: {ctx["cod_doc"]}',
         x34 + 2, yb + h * 0.30, c4w - 4, fs)
    _txt(c, f'RESPONSÁVEL TÉCNICO: {ctx["resp_tecnico"]}',
         x34 + 2, yb + h * 0.08, c4w - 4, fs)

    x5 = x34 + c4w
    c.setFont(F_BOLD, FS_FOOT)
    _txt(c, f'FOLHA {pnum} de {total}', x5 + 2, yb + h * 0.30, c5w - 4, FS_FOOT)
    c.setFont(F_REG, fs)
    _txt(c, f'REV. {ctx["revisao"]}   {ctx["data_doc"]}',
         x5 + 2, yb + h * 0.08, c5w - 4, fs)

    # ── Linha superior ──────────────────────────────────────────────────────
    t1w = w * 0.35
    t2w = w * 0.35
    t3w = w * 0.30
    c.line(x0 + t1w,       mid, x0 + t1w,       yb + h)
    c.line(x0 + t1w + t2w, mid, x0 + t1w + t2w, yb + h)

    c.setFont(F_REG, fs)
    _txt(c, f'CLIENTE: {ctx["cliente"]}',
         x0 + 2, mid + h * 0.22, t1w - 4, fs)
    _txt(c, f'PROGRAMA: {ctx["programa"]}',
         x0 + t1w + 2, mid + h * 0.22, t2w - 4, fs)
    c.setFont(F_BOLD, FS_TITLE)
    _txt(c, ctx['titulo'],
         x0 + t1w + t2w + 2, mid + h * 0.25, t3w - 4, FS_TITLE)
    c.setFont(F_REG, FS_FOOT - 1.5)
    _txt(c, f'ÁREA: {ctx["area"]}  |  {ctx["srge"]}',
         x0 + 2, mid + h * 0.04, w - 4, FS_FOOT - 1.5)

    # Execução / Verificação / Aprovação
    evw = t3w / 3
    xi  = x0 + t1w + t2w
    for i, (lbl, nome) in enumerate(
            [('EXECUÇÃO', ctx['execucao']),
             ('VERIFICAÇÃO', ctx['verificacao']),
             ('APROVAÇÃO', ctx['aprovacao'])]):
        xb = xi + i * evw
        if i > 0:
            c.line(xb, mid, xb, yb + h)
        c.setFont(F_BOLD, FS_FOOT - 1.5)
        c.drawString(xb + 2, mid + h * 0.14, lbl)
        c.setFont(F_REG, FS_FOOT - 1.5)
        _txt(c, nome, xb + 2, mid + h * 0.04, evw - 3, FS_FOOT - 1.5)


def _draw_capa(c: canvas.Canvas, pnum: int, total: int, **ctx):
    """Capa padrão Petrobras N-381: ÍNDICE + DESCRIÇÕES + DESENHOS + bloco título + barra de revisões."""
    # ── Coordenadas gerais (medidas no PDF oficial N-381 rev H) ─────────────
    x0  = 51.0               # margem esquerda oficial
    xR  = 1156.5             # margem direita oficial
    yB  = 39.7               # base oficial (margem inferior simétrica)
    yT  = PAGE_H - 39.7      # = 802.2 pt (margem superior simétrica)

    # Divisor vertical esquerda / direita (x_div = 773.9 medido no oficial)
    x_div   = x0 + (xR - x0) * 0.654   # = 773.9 pt
    left_W  = x_div - x0               # = 722.9 pt
    right_W = xR - x_div               # = 382.6 pt

    # ── Barra de revisões (baixo, largura total) ──────────────────────────────
    RBH  = 62.0          # altura total da barra de revisões
    RB_y = yB            # base
    RB_T = yB + RBH      # topo

    # ── Bloco título Petrobras (coluna direita, acima da barra) ──────────────
    TBH  = 192.0
    TB_y = RB_T
    TB_T = TB_y + TBH

    # ── NOTAS (coluna esquerda, mesma faixa que base do bloco título) ─────────
    NTH  = TBH
    NT_y = TB_y
    NT_T = TB_T

    # ── Conteúdo esquerdo (acima de NOTAS, até topo) ─────────────────────────
    LC_y  = NT_T
    LC_T  = yT
    LC_H  = LC_T - LC_y        # ~580 pt

    IDX_H   = LC_H * 0.54      # ~313 pt — ÍNDICE DE REVISÃO
    IDX_T   = LC_T
    IDX_y   = LC_T - IDX_H

    DESC_T  = IDX_y
    DESC_y  = LC_y
    DESC_H  = DESC_T - DESC_y  # ~267 pt — Tabela REV | DESCRIÇÃO

    # ── DESENHOS DE REFERÊNCIA (coluna direita, acima do bloco título) ────────
    DES_y = TB_T
    DES_T = yT
    DES_H = DES_T - DES_y

    LW = 0.5
    c.setLineWidth(LW)
    c.setStrokeColor(BLACK)

    # ─── 1. ÍNDICE DE REVISÃO DE FOLHAS ──────────────────────────────────────
    _capa_indice(c, x0, IDX_y, left_W, IDX_H)

    # ─── 2. Tabela REV | DESCRIÇÃO | ABREVIATURA ─────────────────────────────
    _capa_rev_desc(c, x0, DESC_y, left_W, DESC_H, rev_data=ctx.get('rev_data'))

    # ─── 3. NOTAS ────────────────────────────────────────────────────────────
    c.setFillColor(WHITE)
    c.rect(x0, NT_y, left_W, NTH, fill=1, stroke=1)
    c.setFillColor(BLACK)
    c.setFont(F_BOLD, 6)
    c.drawString(x0 + 4, NT_T - 10, 'NOTAS:')

    # ─── 4. DESENHOS DE REFERÊNCIA ───────────────────────────────────────────
    c.setFillColor(WHITE)
    c.rect(x_div, DES_y, right_W, DES_H, fill=1, stroke=1)
    c.setFillColor(BLACK)
    c.setFont(F_BOLD, 8)
    c.drawCentredString(x_div + right_W / 2, DES_T - 14, 'DESENHOS DE REFERÊNCIA')

    # ─── 5. Bloco título Petrobras ────────────────────────────────────────────
    _capa_title_block(c, x_div, TB_y, right_W, TBH, pnum, total, **ctx)

    # ─── 6. Barra de revisões (largura total, base) ───────────────────────────
    _capa_rev_bar(c, x0, RB_y, CONTENT_W, RBH, **ctx)


# ── Sub-funções da capa ───────────────────────────────────────────────────────

def _cell(c: canvas.Canvas, x, y, w, h, txt='', fs=6.5,
          bold=False, bg=None, fg=None, align='L', stroke=True):
    """Desenha uma célula retangular com texto."""
    if bg is None:
        bg = WHITE
    if fg is None:
        fg = BLACK
    c.setFillColor(bg)
    c.rect(x, y, w, h, fill=1, stroke=1 if stroke else 0)
    if not txt:
        return
    c.setFillColor(fg)
    c.setFont(F_BOLD if bold else F_REG, fs)
    pad = 2.0
    # Posiciona baseline verticalmente centrada na célula
    baseline = y + max(2.0, (h - fs) / 2)
    if align == 'C':
        c.drawCentredString(x + w / 2, baseline, _truncate(txt, w - pad * 2, fs))
    elif align == 'R':
        c.drawRightString(x + w - pad, baseline, _truncate(txt, w - pad * 2, fs))
    else:
        c.drawString(x + pad, baseline, _truncate(txt, w - pad * 2, fs))


def _capa_indice(c: canvas.Canvas, x0, y0, W, H):
    """Tabela 'ÍNDICE DE REVISÃO DE FOLHAS'."""
    # Título
    TH = 16.0   # altura do título
    c.setFillColor(WHITE)
    c.rect(x0, y0 + H - TH, W, TH, fill=1, stroke=1)
    c.setFillColor(BLACK)
    c.setFont(F_BOLD, 9)
    c.drawCentredString(x0 + W / 2, y0 + H - TH + TH * 0.38, 'ÍNDICE DE REVISÃO DE FOLHAS')

    # Sub-cabeçalho: N pares FOLHA | REV.
    N_PAIRS = 9
    SH = 12.0   # altura do sub-cabeçalho
    sub_y = y0 + H - TH - SH
    pair_w = W / N_PAIRS
    folha_w = pair_w * 0.6
    rev_w   = pair_w * 0.4
    for i in range(N_PAIRS):
        px = x0 + i * pair_w
        _cell(c, px,           sub_y, folha_w, SH, 'FOLHA', fs=5, bold=True)
        _cell(c, px + folha_w, sub_y, rev_w,   SH, 'REV.',  fs=5, bold=True)

    # Linhas de dados (vazias)
    body_H = H - TH - SH
    n_rows = 20
    rh = body_H / n_rows
    for r in range(n_rows):
        ry = y0 + body_H - (r + 1) * rh
        for i in range(N_PAIRS):
            px = x0 + i * pair_w
            _cell(c, px,           ry, folha_w, rh, '')
            _cell(c, px + folha_w, ry, rev_w,   rh, '')


def _capa_rev_desc(c: canvas.Canvas, x0, y0, W, H, rev_data=None):
    """Tabela REV. | DESCRIÇÃO | ABREVIATURA com histórico de revisões.

    `rev_data` permite reaproveitar a capa em outros documentos (ex.: o
    Boletim de Medição). Se None, usa o histórico padrão da EAP.
    """
    if rev_data is None:
        rev_data = [
            ('0',  'EMISSÃO ORIGINAL', ''),
            ('A',  'ATENDIMENTO AOS COMENTÁRIOS', ''),
            ('B',  'CORREÇÃO DO CÓDIGO DA ÁREA (0000 PARA 2000) E TRIGRAMA DO DOCUMENTO (ECG PARA E6G)', ''),
            ('C',  'REVISÃO DAS MEDIÇÕES OCORRIDAS DOS MESES DE AGOSTO/25 A NOVEMBRO/25, '
                   'INCLUINDO A LINHA DE TENDÊNCIA DOS PRÓXIMOS MESES.', ''),
            ('D',  'REVISÃO DA MEDIÇÃO DE DEZEMBRO/25, INCLUINDO A LINHA DE TENDÊNCIA DOS PRÓXIMOS MESES.', ''),
            ('E',  'REVISÃO DA MEDIÇÃO DE JANEIRO/26, REVISANDO A LINHA DE TENDÊNCIA DOS PRÓXIMOS MESES.', ''),
            ('F',  'REVISÃO DA MEDIÇÃO DE FEVEREIRO/26, REVISANDO A LINHA DE TENDÊNCIA DOS PRÓXIMOS MESES.', ''),
            ('G',  'REVISÃO DA MEDIÇÃO DE MARÇO/26, REVISANDO A LINHA DE TENDÊNCIA DOS PRÓXIMOS MESES.', ''),
            ('H',  'REVISÃO DA MEDIÇÃO DE ABRIL/26, REVISANDO A LINHA DE TENDÊNCIA DOS PRÓXIMOS MESES.', ''),
        ]

    # Larguras das colunas (proporções do original Petrobras)
    CW_REV  = W * 0.080              # medido no PDF oficial
    CW_ABR  = W * 0.200             # medido no PDF oficial
    CW_DESC = W - CW_REV - CW_ABR   # ≈ 72% da largura

    # Cabeçalho
    HDR_H = 14.0
    hdr_y = y0 + H - HDR_H
    _cell(c, x0,                    hdr_y, CW_REV,  HDR_H, 'REV.',        fs=7, bold=True, bg=WHITE, fg=BLACK)
    _cell(c, x0 + CW_REV,          hdr_y, CW_DESC, HDR_H, 'DESCRIÇÃO',   fs=7, bold=True, bg=WHITE, fg=BLACK, align='C')
    _cell(c, x0 + CW_REV + CW_DESC, hdr_y, CW_ABR, HDR_H, 'ABREVIATURA', fs=7, bold=True, bg=WHITE, fg=BLACK, align='C')

    # Linhas de dados
    n_data    = len(rev_data)
    body_H    = H - HDR_H
    # Linhas preenchidas: usam altura fixa; sobras ficam vazias
    ROW_H_D   = 14.0
    total_data_h = n_data * ROW_H_D
    # Linhas vazias preenchem o restante
    n_empty   = max(0, int((body_H - total_data_h) / ROW_H_D))
    all_rows  = rev_data + [('', '', '')] * n_empty
    rh        = body_H / len(all_rows) if all_rows else ROW_H_D

    for i, (rev, desc, abr) in enumerate(all_rows):
        ry = y0 + body_H - (i + 1) * rh
        _cell(c, x0,                     ry, CW_REV,  rh, rev,  fs=6)
        _cell(c, x0 + CW_REV,            ry, CW_DESC, rh, desc, fs=6)
        _cell(c, x0 + CW_REV + CW_DESC,  ry, CW_ABR,  rh, abr,  fs=6)


def _capa_title_block(c: canvas.Canvas, x0, y0, W, H, pnum, total, **ctx):
    """Bloco título padrão Petrobras N-381 (coluna direita da capa)."""
    # Dividimos H em seções de cima para baixo:
    # R1: RAZÃO SOCIAL / RESP. TÉCNICO
    # R2: Nº CONTRATO / REG CREA / COD DOC
    # R3: ESPECIFICAÇÃO TÉCNICA Nº / código
    # R4-R8: logo + cliente/programa/área/srge+título / folha/planejamento/interno
    H1 = H * 0.145   # R1
    H2 = H * 0.12    # R2
    H3 = H * 0.11    # R3
    H_logo = H - H1 - H2 - H3   # resto para as linhas com logo

    # ── R3 (topo) ─────────────────────────────────────────────────────────────
    r3_y  = y0 + H - H1 - H2 - H3
    CW_lbl3 = W * 0.52
    CW_val3 = W - CW_lbl3
    _cell(c, x0,          r3_y, CW_lbl3, H3, 'ESPECIFICAÇÃO TÉCNICA',  fs=5.5, bold=True)
    _cell(c, x0 + CW_lbl3, r3_y, CW_val3, H3, ctx['cod_doc'],           fs=5.5)

    # ── R2 ────────────────────────────────────────────────────────────────────
    r2_y  = r3_y + H3
    CW_c1 = W * 0.38
    CW_c2 = W * 0.32
    CW_c3 = W - CW_c1 - CW_c2
    _cell(c, x0,            r2_y, CW_c1, H2, f'Nº CONTRATO: {ctx["num_contrato"]}', fs=5)
    _cell(c, x0 + CW_c1,    r2_y, CW_c2, H2, f'REG CREA N.: {ctx["reg_crea"]}',    fs=5)
    _cell(c, x0 + CW_c1 + CW_c2, r2_y, CW_c3, H2, 'COD. DOCUMENTO INTERNO: N/A',  fs=4.5)

    # ── R1 (topo absoluto) ────────────────────────────────────────────────────
    r1_y  = r2_y + H2
    CW_rs = W * 0.50
    _cell(c, x0,        r1_y, CW_rs, H1, f'RAZÃO SOCIAL: {ctx["razao_social"]}', fs=5.5, bold=True)
    _cell(c, x0 + CW_rs, r1_y, W - CW_rs, H1, f'RESPONSÁVEL TÉCNICO: {ctx["resp_tecnico"]}', fs=5.5)

    # ── R4-R8: logo + linhas de info ─────────────────────────────────────────
    # Colunas: logo (esq) | info (centro) | folha/classificação (dir)
    logo_W  = W * 0.22
    class_W = W * 0.16
    info_W  = W - logo_W - class_W

    logo_x  = x0
    info_x  = x0 + logo_W
    cls_x   = x0 + logo_W + info_W

    # Sub-linhas dentro da área info (5 linhas)
    n_info = 5
    ih = H_logo / n_info

    labels  = ['CLIENTE:', 'PROGRAMA:', 'ÁREA:', 'SRGE/SI:', 'TÍTULO:']
    values  = [
        ctx['cliente'],
        ctx['programa'],
        ctx['area'],
        ctx['srge'],
        ctx['titulo'],
    ]

    for i, (lbl, val) in enumerate(zip(labels, values)):
        iy = y0 + H_logo - (i + 1) * ih
        lbl_w = info_W * 0.30
        val_w = info_W - lbl_w
        _cell(c, info_x,         iy, lbl_w, ih, lbl, fs=4.5, bold=True)
        _cell(c, info_x + lbl_w, iy, val_w, ih, val, fs=5.0)

    # Coluna de classificação (FOLHA + PLANEJAMENTO + INTERNO)
    cls_rows = [
        (f'FOLHA',      '', False),
        (f'{pnum} de {total}', '', True),
        ('PLANEJAMENTO', '', False),
        ('INTERNO',      '', False),
        ('-',            '', False),
    ]
    clsh = H_logo / len(cls_rows)
    for i, (txt, _, bold) in enumerate(cls_rows):
        cy = y0 + H_logo - (i + 1) * clsh
        _cell(c, cls_x, cy, class_W, clsh, txt, fs=5, bold=bold, align='C')

    # Logo BR (área do logo = logo_W × H_logo)
    _draw_br_logo(c, logo_x, y0, logo_W, H_logo)


def _draw_br_logo(c: canvas.Canvas, x, y, w, h):
    """Renderiza o logo oficial Petrobras (SVG) na área indicada."""
    # Borda da célula
    c.setFillColor(WHITE)
    c.rect(x, y, w, h, fill=1, stroke=1)

    try:
        from svglib.svglib import svg2rlg
        logo_path = os.path.normpath(_LOGO_SVG)
        rlg = svg2rlg(logo_path)
        if rlg and rlg.width > 0 and rlg.height > 0:
            # Calcula escala para caber em w×h com uma pequena margem
            margin = 4
            scale_x = (w - margin * 2) / rlg.width
            scale_y = (h - margin * 2) / rlg.height
            scale   = min(scale_x, scale_y)
            draw_w  = rlg.width  * scale
            draw_h  = rlg.height * scale
            # Centraliza
            ox = x + margin + (w - margin * 2 - draw_w) / 2
            oy = y + margin + (h - margin * 2 - draw_h) / 2
            c.saveState()
            c.translate(ox, oy)
            c.scale(scale, scale)
            renderPDF.draw(rlg, c, 0, 0)
            c.restoreState()
            return
    except Exception:
        pass

    # Fallback: losango simples se svglib falhar
    c.setFillColor(colors.HexColor('#FFD700'))
    cx, cy = x + w / 2, y + h * 0.52
    dx, dy = w * 0.36, h * 0.36
    path = c.beginPath()
    path.moveTo(cx, cy + dy); path.lineTo(cx + dx, cy)
    path.lineTo(cx, cy - dy); path.lineTo(cx - dx, cy)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    c.setFillColor(colors.HexColor('#003087'))
    c.setFont(F_BOLD, min(w * 0.28, 10))
    c.drawCentredString(cx, cy - 2, 'BR')


def _capa_rev_bar(c: canvas.Canvas, x0, y0, W, H, **ctx):
    """Barra de revisões na base da capa (largura total)."""
    # Últimas 5 revisões mostradas — dados históricos fixos + revisão atual
    revs = [
        ('0',  '10/10/2025', ctx['execucao'], ctx['verificacao'], ctx['aprovacao']),
        ('E',  '01/02/2026', ctx['execucao'], ctx['verificacao'], ctx['aprovacao']),
        ('F',  '09/03/2026', ctx['execucao'], ctx['verificacao'], ctx['aprovacao']),
        ('G',  '08/04/2026', ctx['execucao'], ctx['verificacao'], ctx['aprovacao']),
        (ctx['revisao'], ctx['data_doc'], ctx['execucao'], ctx['verificacao'], ctx['aprovacao']),
    ]

    labels_col = ['', 'DATA', 'EXECUÇÃO', 'VERIFICAÇÃO', 'APROVAÇÃO']
    n_rows = len(labels_col)
    # + 1 linha formulário na base
    FORM_H = H * 0.16
    data_H = H - FORM_H
    rh = data_H / n_rows

    # Largura da coluna de rótulos
    LBL_W = W * 0.085
    rev_W  = (W - LBL_W) / len(revs)

    # Linha de rótulos + dados
    for ri, lbl in enumerate(labels_col):
        ry = y0 + data_H - (ri + 1) * rh
        # Célula de rótulo
        _cell(c, x0, ry, LBL_W, rh, lbl if ri > 0 else 'REV.',
              fs=5.5, bold=True)
        for ci, rev in enumerate(revs):
            rx = x0 + LBL_W + ci * rev_W
            if ri == 0:
                val = f'REV. {rev[0]}'
                _cell(c, rx, ry, rev_W, rh, val, fs=5.5, bold=True, align='C')
            else:
                val = rev[ri]
                _cell(c, rx, ry, rev_W, rh, val, fs=5, align='C')

    # Linha inferior: formulário + aviso
    form_y = y0
    form_lbl_w = W * 0.30
    form_val_w = W - form_lbl_w
    _cell(c, x0,              form_y, form_lbl_w, FORM_H,
          'FORMULÁRIO PERTENCENTE A PETROBRAS N-381 REV. M.', fs=4.5)
    _cell(c, x0 + form_lbl_w, form_y, form_val_w, FORM_H,
          'AS INFORMAÇÕES DESTE DOCUMENTO SÃO PROPRIEDADE DA PETROBRAS, '
          'SENDO PROIBIDA A UTILIZAÇÃO FORA DA SUA FINALIDADE.',
          fs=4.5)


def _draw_col_headers(c: canvas.Canvas, meses: list[str], col_mes_w: float):
    """Faixa de cabeçalho de colunas imediatamente acima da 1ª linha de dados."""
    x0 = MARGIN_L
    yb = BODY_DATA_TOP      # base da faixa = topo da primeira linha de dados
    h  = COL_HDR_H

    c.setFillColor(NAVY)
    c.rect(x0, yb, CONTENT_W, h, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(F_BOLD, FS_COL)

    col_defs = [
        (COL_ITEM,  'ITEM',       True),
        (COL_NIVEL, 'NÍV',        True),
        (COL_DESC,  'ESCOPO',     False),
        (COL_VALOR, 'VALOR (R$)', True),
        (COL_PCT,   '% ACUM',     True),
        (COL_RACUM, 'R$ ACUM',    True),
    ]

    cx = x0
    ymid = yb + h * 0.40
    for cw, lbl, centered in col_defs:
        if centered:
            c.drawCentredString(cx + cw / 2, ymid, lbl)
        else:
            c.drawString(cx + 2, ymid, lbl)
        # separador vertical
        c.setLineWidth(0.2)
        c.setStrokeColor(WHITE)
        c.line(cx + cw, yb, cx + cw, yb + h)
        cx += cw

    for mes in meses:
        c.setFont(F_BOLD, FS_COL)
        c.drawCentredString(cx + col_mes_w / 2, ymid, _label_mes(mes))
        c.setLineWidth(0.2)
        c.line(cx + col_mes_w, yb, cx + col_mes_w, yb + h)
        cx += col_mes_w

    # borda inferior da faixa
    c.setLineWidth(0.4)
    c.setStrokeColor(NAVY)
    c.line(x0, yb, x0 + CONTENT_W, yb)


def _draw_row_total(c: canvas.Canvas, valor_total: float, dist_total: dict,
                    meses: list[str], col_mes_w: float, y: float):
    """Linha 'CONTRATO' — totais do contrato."""
    _row_bg_fg(c, y, NAVY, WHITE, True)
    c.setFont(F_BOLD, FS_DATA + 0.3)
    base = y - ROW_H * 0.62

    cx = MARGIN_L
    _row_cell(c, cx, COL_ITEM,  'CONTRATO',             base, centered=True)
    cx += COL_ITEM
    _row_cell(c, cx, COL_NIVEL, '',                     base, centered=True)
    cx += COL_NIVEL
    _row_cell(c, cx, COL_DESC,  '',                     base, centered=False)
    cx += COL_DESC
    _row_cell(c, cx, COL_VALOR, _fmt_brl(valor_total),  base, centered=True)
    cx += COL_VALOR
    _row_cell(c, cx, COL_PCT,   '100,00%',              base, centered=True)
    cx += COL_PCT
    _row_cell(c, cx, COL_RACUM, _fmt_brl(valor_total),  base, centered=True)
    cx += COL_RACUM

    c.setFont(F_REG, FS_DATA)
    for mes in meses:
        v = dist_total.get(mes, 0)
        if v:
            _row_cell(c, cx, col_mes_w, _fmt_brl(v), base, centered=True)
        cx += col_mes_w

    _row_sep(c, y)


def _draw_row_item(c: canvas.Canvas, it, dm: dict,
                   meses: list[str], col_mes_w: float, y: float,
                   is_leaf: bool = False):
    """Uma linha de item EAP.

    Nós-pai recebem fundo navy progressivo por nível.
    Folhas (sem filhos) recebem fundo cinza claro independente do nível,
    para distingui-las visualmente dos agrupadores.
    """
    niv = it.nivel or 1
    idx = min(niv - 1, len(WBS_BG) - 1)

    if is_leaf:
        # Folha: fundo claro, texto escuro
        bg, fg, fnt = LGRAY, BLACK, F_REG
    elif niv <= 4:
        bg, fg, fnt = WBS_BG[idx], WHITE, F_BOLD
    elif niv == 5:
        bg, fg, fnt = WBS_BG[4], WHITE, F_REG
    elif niv == 6:
        bg, fg, fnt = WBS_BG[5], WHITE, F_REG
    else:
        bg, fg, fnt = LGRAY, BLACK, F_REG

    _row_bg_fg(c, y, bg, fg, False)
    c.setFont(fnt, FS_DATA)
    base = y - ROW_H * 0.62

    valor  = it.valor or 0.0
    indent = (niv - 1) * 2   # pt de recuo na coluna ESCOPO

    cx = MARGIN_L
    _row_cell(c, cx, COL_ITEM,  it.codigo or '',    base, centered=True)
    cx += COL_ITEM
    _row_cell(c, cx, COL_NIVEL, str(niv),           base, centered=True)
    cx += COL_NIVEL
    _row_cell(c, cx, COL_DESC,  it.descricao or '', base, centered=False,
              indent=indent)
    cx += COL_DESC
    _row_cell(c, cx, COL_VALOR, _fmt_brl(valor),    base, centered=True)
    cx += COL_VALOR
    _row_cell(c, cx, COL_PCT,   '100,00%',          base, centered=True)
    cx += COL_PCT
    _row_cell(c, cx, COL_RACUM, _fmt_brl(valor),    base, centered=True)
    cx += COL_RACUM

    c.setFont(F_REG, FS_DATA)
    for mes in meses:
        v = dm.get(mes, 0)
        if v:
            _row_cell(c, cx, col_mes_w, _fmt_brl(v), base, centered=True)
        cx += col_mes_w

    _row_sep(c, y)


# ── Primitivas de linha ───────────────────────────────────────────────────────

def _row_bg_fg(c: canvas.Canvas, y: float, bg, fg, bold: bool):
    """Preenche fundo de uma linha e define cor do texto."""
    c.setFillColor(bg)
    c.rect(MARGIN_L, y - ROW_H, CONTENT_W, ROW_H, fill=1, stroke=0)
    c.setFillColor(fg)


def _row_cell(c: canvas.Canvas, x: float, w: float, txt: str,
              base_y: float, *, centered: bool, indent: float = 0):
    """Desenha texto em uma célula, truncando se necessário."""
    if not txt:
        return
    if centered:
        t = _truncate(txt, w - 2, FS_DATA)
        c.drawCentredString(x + w / 2, base_y, t)
    else:
        t = _truncate(txt, w - 2 - indent, FS_DATA)
        c.drawString(x + 2 + indent, base_y, t)


def _row_sep(c: canvas.Canvas, y: float):
    """Linha separadora cinza abaixo de uma linha de dados."""
    c.setLineWidth(0.15)
    c.setStrokeColor(MGRAY)
    c.line(MARGIN_L, y - ROW_H, MARGIN_L + CONTENT_W, y - ROW_H)


# ── Utilidade de texto ────────────────────────────────────────────────────────

def _txt(c: canvas.Canvas, text: str, x: float, y: float,
         max_w: float, fs: float):
    """drawString com truncamento automático."""
    c.drawString(x, y, _truncate(text, max_w, fs))
