import json as _json
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import date, datetime


# ── Tarefa ──────────────────────────────────────────────────────────────────

class TarefaBase(BaseModel):
    activity_id: str
    nome: str
    disciplina: Optional[str] = None
    supervisor: Optional[str] = None
    encarregado: Optional[str] = None
    area_unidade: Optional[str] = None
    duracao: Optional[int] = None
    inicio_lb: Optional[date] = None
    termino_lb: Optional[date] = None


class TarefaCreate(TarefaBase):
    pass


class TarefaUpdate(BaseModel):
    nome: Optional[str] = None
    disciplina: Optional[str] = None
    supervisor: Optional[str] = None
    encarregado: Optional[str] = None
    area_unidade: Optional[str] = None
    duracao: Optional[int] = None
    inicio_lb: Optional[date] = None
    termino_lb: Optional[date] = None


class TarefaOut(TarefaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    wbs_path: Optional[list[str]] = None

    @field_validator("wbs_path", mode="before")
    @classmethod
    def _parse_wbs_path(cls, v):
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except _json.JSONDecodeError:
                return None
        return v


# ── Semana ──────────────────────────────────────────────────────────────────

class SemanaBase(BaseModel):
    codigo: str
    data_inicio: date
    data_fim: date


class SemanaCreate(SemanaBase):
    pass


class SemanaOut(SemanaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fechada: bool = False
    fechada_em: Optional[datetime] = None
    snap_qcron: Optional[int] = None
    snap_qprog: Optional[int] = None
    snap_qreal: Optional[int] = None
    snap_pct_exec: Optional[float] = None
    # Contadores live (semanas não fechadas)
    live_qcron: Optional[int] = None
    live_qprog: Optional[int] = None
    live_qreal: Optional[int] = None
    live_pct_exec: Optional[float] = None


# ── SubTarefa ────────────────────────────────────────────────────────────────
# Definida antes de ProgramacaoComTarefa para ser usada como campo

class SubTarefaBase(BaseModel):
    descricao: str
    status: str = "nao_executada"
    inicio_qprog: Optional[date] = None
    termino_qprog: Optional[date] = None


class SubTarefaCreate(SubTarefaBase):
    pass


class SubTarefaUpdate(BaseModel):
    descricao: Optional[str] = None
    status: Optional[str] = None
    inicio_qprog: Optional[date] = None
    termino_qprog: Optional[date] = None


class SubTarefaOut(SubTarefaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    programacao_id: int
    criado_em: Optional[datetime] = None


# ── ProgramacaoSemanal ───────────────────────────────────────────────────────

class ProgramacaoBase(BaseModel):
    semana: str
    tarefa_id: int
    inicio_prog: Optional[date] = None
    termino_prog: Optional[date] = None
    no_qprog: bool = False
    inicio_qprog: Optional[date] = None
    termino_qprog: Optional[date] = None
    status_atividade: Optional[str] = None
    pct_avanco: float = 0.0
    pct_executado: float = 0.0
    inicio_real: Optional[date] = None
    termino_real: Optional[date] = None
    qreal_concluida: bool = False
    pct_qreal: float = 0.0
    observacoes: Optional[str] = None
    condicao_1: Optional[str] = None
    condicao_2: Optional[str] = None
    adiantada: bool = False
    semana_original: Optional[str] = None
    usuario: Optional[str] = None


class ProgramacaoCreate(ProgramacaoBase):
    pass


class ProgramacaoUpdate(BaseModel):
    no_qprog: Optional[bool] = None
    inicio_qprog: Optional[date] = None
    termino_qprog: Optional[date] = None
    pct_avanco: Optional[float] = None
    inicio_real: Optional[date] = None
    termino_real: Optional[date] = None
    qreal_concluida: Optional[bool] = None
    pct_qreal: Optional[float] = None
    observacoes: Optional[str] = None
    condicao_1: Optional[str] = None
    condicao_2: Optional[str] = None
    adiantada: Optional[bool] = None
    semana_original: Optional[str] = None
    usuario: Optional[str] = None


class ProgramacaoOut(ProgramacaoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    atualizado_em: Optional[datetime] = None


class ProgramacaoComTarefa(ProgramacaoOut):
    tarefa: TarefaOut
    sub_tarefas: list[SubTarefaOut] = []


# ── Import ───────────────────────────────────────────────────────────────────

class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    semana_ref: str
    arquivo_original: Optional[str] = None
    importado_em: Optional[datetime] = None
    usuario: Optional[str] = None
    status: str


# ── Resultados de importacao ─────────────────────────────────────────────────

class ImportResultado(BaseModel):
    importacao_id: int
    semana: str
    tarefas_encontradas: int
    tarefas_novas: int
    tarefas_atualizadas: int
    qcron_count: int
    auto_qreal_count: int = 0
    detalhes: list[TarefaOut]


# ── EAP Financeira ──────────────────────────────────────────────────────

class EapItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    descricao: str
    nivel: int
    parent_codigo: Optional[str] = None
    valor: float = 0.0
    # dist_mensal vem como string JSON do banco; o endpoint converte
    dist_mensal: Optional[dict[str, float]] = None


class EapImportResultado(BaseModel):
    itens_total: int
    itens_folha: int
    valor_total: float
    meses: list[str]
    # Integridade hierárquica (síntese de nós intermediários ausentes na origem)
    intermediarios_sintetizados: int = 0
    codigos_sintetizados: list[str] = []


class TarefaEapLinkBase(BaseModel):
    tarefa_id: int
    eap_codigo: str
    peso: float = 1.0


class TarefaEapLinkOut(TarefaEapLinkBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CurvaPonto(BaseModel):
    """Um ponto da curva-S (mensal ou semanal)."""
    label: str           # "ago/25", "set/25" ou "S_037"
    data: str            # ISO yyyy-mm-dd
    pv_mes: float = 0.0  # R$ previsto neste período
    ev_mes: float = 0.0  # R$ realizado (Earned Value) neste período
    pv_acum: float = 0.0
    ev_acum: float = 0.0


class EvmKpis(BaseModel):
    """Indicadores EVM agregados até a semana de referência."""
    semana: str
    bac: float           # Budget at Completion (orçamento total)
    pv: float            # Planned Value acumulado
    ev: float            # Earned Value acumulado
    spi: float           # Schedule Performance Index = EV / PV
    cv_pct: float        # Variance % = (EV - PV) / PV * 100
    vac: float           # Variance at Completion = BAC - EAC (estimada)
    pct_pv: float        # PV / BAC * 100
    pct_ev: float        # EV / BAC * 100


class AutoMapearSugestao(BaseModel):
    tarefa_id: int
    activity_id: str
    nome: str
    sugestoes: list[dict]  # [{eap_codigo, descricao, score}]


# ── Ciclo de medição (Previsão + Avanço) ──────────────────────────────

class EapPrevisaoIn(BaseModel):
    eap_codigo: str
    pct_previsto: float
    observacao: Optional[str] = None


class EapPrevisaoBulk(BaseModel):
    """Bulk update da previsão mensal."""
    itens: list[EapPrevisaoIn]
    lancado_por: Optional[str] = None


class EapAdiantarIn(BaseModel):
    eap_codigo: str
    pct_previsto: float = 0.0
    mes_original_ano: int
    mes_original_mes: int
    observacao: Optional[str] = None
    lancado_por: Optional[str] = None


class EapPrevisaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ano: int
    mes: int
    eap_codigo: str
    pct_previsto: float = 0.0
    observacao: Optional[str] = None
    lancado_em: Optional[datetime] = None
    lancado_por: Optional[str] = None
    adiantada: bool = False
    mes_original_ano: Optional[int] = None
    mes_original_mes: Optional[int] = None


class EapAvancoIn(BaseModel):
    eap_codigo: str
    pct_delta: float
    observacao: Optional[str] = None


class EapAvancoBulk(BaseModel):
    semana_codigo: str
    itens: list[EapAvancoIn]
    lancado_por: Optional[str] = None


class EapAvancoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semana_codigo: str
    eap_codigo: str
    pct_delta: float = 0.0
    observacao: Optional[str] = None
    lancado_em: Optional[datetime] = None
    lancado_por: Optional[str] = None


class EapItemMedicaoOut(BaseModel):
    """View consolidada para a tela de medição: 1 linha por item EAP no mês."""
    eap_codigo: str
    descricao: str
    valor: float
    unidade: Optional[str] = '%'
    criterio: Optional[str] = None
    pct_previsto: float = 0.0
    pct_acum_anterior: float = 0.0     # acumulado até o mês anterior
    pct_acum_atual: float = 0.0        # acumulado incluindo deltas do mês corrente
    pct_periodo: float = 0.0           # delta do mês (acum_atual - acum_anterior)
    valor_periodo: float = 0.0
    valor_acum_total: float = 0.0


class EapItemUpdate(BaseModel):
    """Atualização in-line de campos editáveis do item EAP (critério, unidade)."""
    criterio: Optional[str] = None
    unidade: Optional[str] = None



class EapAtividadeManualIn(BaseModel):
    parent_codigo: str
    descricao: str
    valor: float
    criterio: Optional[str] = None
    unidade: Optional[str] = "%"

    @field_validator("descricao")
    @classmethod
    def validar_descricao(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Informe a descricao da atividade.")
        return v

    @field_validator("valor")
    @classmethod
    def validar_valor(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("O peso/valor estimado deve ser maior que zero.")
        return v

# ── Ciclo de Medição Mensal (BM) ──────────────────────────────────────

class CicloMedicaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ano: int
    mes: int
    status: str
    fechado_em: Optional[datetime] = None
    fechado_por: Optional[str] = None
    observacao: Optional[str] = None
    criado_em: Optional[datetime] = None


class LancamentoIn(BaseModel):
    eap_codigo: str
    pct_acumulado: float       # 0.0 a 1.0 (ex: 0.75 = 75%)
    observacao: Optional[str] = None

    @field_validator('pct_acumulado')
    @classmethod
    def validar_pct(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(
                f'pct_acumulado inválido: {v} é negativo. '
                'Valores permitidos: 0% até 100%.'
            )
        if v > 1.0:
            raise ValueError(
                f'pct_acumulado inválido: {v} excede 100% (1.0). '
                'Valores permitidos: 0% até 100%.'
            )
        return v


class LancamentoBulk(BaseModel):
    itens: list[LancamentoIn]
    fechado_por: Optional[str] = None


class MedicaoItemOut(BaseModel):
    codigo: str
    descricao: str
    nivel: int
    parent_codigo: Optional[str] = None
    valor: float
    is_folha: bool
    pct_previsto: float        # do eap_previsao_mensal (0–1)
    pct_acum_anterior: float   # acumulado do último BM fechado
    pct_acumulado: float       # acumulado incluindo este ciclo
    pct_periodo: float         # pct_acumulado - pct_acum_anterior
    valor_periodo: float       # pct_periodo * valor
    valor_acumulado: float     # pct_acumulado * valor
    valor_dist_mes: float = 0.0  # R$ planejado para o mês conforme curva de desembolso
    observacao: Optional[str] = None
    adiantada: bool = False       # foi adiantada de outro mês via Previsão Mensal


class MedicaoMesOut(BaseModel):
    ciclo: CicloMedicaoOut
    itens: list[MedicaoItemOut]
    bac: float
    total_pct_acum: float
    total_pct_periodo: float
    total_valor_periodo: float


# ── Documentos de Engenharia (Fase 3) ─────────────────────────────────

class DocumentoIn(BaseModel):
    codigo: str
    titulo: str
    disciplina: Optional[str] = None
    tipo_doc: Optional[str] = None
    revisao_atual: Optional[str] = None
    status: Optional[str] = "EM_ELABORACAO"
    emitido_em: Optional[date] = None
    aprovado_em: Optional[date] = None
    peso: Optional[float] = 1.0
    observacao: Optional[str] = None


class DocumentoUpdate(BaseModel):
    titulo: Optional[str] = None
    disciplina: Optional[str] = None
    tipo_doc: Optional[str] = None
    revisao_atual: Optional[str] = None
    status: Optional[str] = None
    emitido_em: Optional[date] = None
    aprovado_em: Optional[date] = None
    peso: Optional[float] = None
    observacao: Optional[str] = None


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    titulo: str
    disciplina: Optional[str] = None
    tipo_doc: Optional[str] = None
    revisao_atual: Optional[str] = None
    status: str
    emitido_em: Optional[date] = None
    aprovado_em: Optional[date] = None
    peso: float = 1.0
    observacao: Optional[str] = None
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None


class Progresso211Out(BaseModel):
    pct: float            # 0.0 a 1.0
    pct_fmt: str          # "72.4%"
    total_docs: int
    em_elaboracao: int
    em_analise: int
    com_comentarios: int
    sem_comentarios: int
    aprovados: int
    peso_total: float
    peso_realizado: float  # soma dos pesos × fator de contribuição


class DocumentoImportResultado(BaseModel):
    inseridos: int
    atualizados: int
    erros: list[str]


# ── Relatório Fotográfico ─────────────────────────────────────────────

class FotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ano: int
    mes: int
    eap_codigo: str
    eap_descricao: Optional[str] = None
    numero: Optional[int] = None
    legenda: Optional[str] = None
    filename: str
    tamanho: Optional[int] = None
    criado_em: Optional[datetime] = None
    lancado_por: Optional[str] = None


class FotoLegendaIn(BaseModel):
    legenda: Optional[str] = None


# ── Fase 2A — Critérios / Integração LD / Motor de Medição ───────────────────

class CriterioIn(BaseModel):
    codigo_eap: str
    descricao: Optional[str] = None
    tipo_criterio: Optional[str] = "MANUAL"
    peso: Optional[float] = 1.0
    evidencia_obrigatoria: Optional[bool] = False
    ativo: Optional[bool] = True
    parametros: Optional[dict] = None


class CriterioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo_eap: str
    descricao: Optional[str] = None
    tipo_criterio: str
    peso: Optional[float] = None
    evidencia_obrigatoria: Optional[bool] = None
    ativo: Optional[bool] = None
    parametros: Optional[str] = None
    criado_em: Optional[datetime] = None


class CriterioAvaliacaoOut(BaseModel):
    codigo_eap: str
    tipo_criterio: str
    pct: Optional[float] = None
    implementado: bool
    fonte_pendente: bool = False
    manual: bool = False
    evidencias: list[str] = []
    detalhe: str = ""


class LdDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo_documento: str
    titulo: Optional[str] = None
    disciplina: Optional[str] = None
    revisao: Optional[str] = None
    status: Optional[str] = None
    a4_equivalente: Optional[float] = None
    data_prevista: Optional[date] = None
    data_emissao: Optional[date] = None
    data_importacao: Optional[datetime] = None
    origem_arquivo: Optional[str] = None


class LdHistoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    documento_id: int
    status_anterior: Optional[str] = None
    status_novo: Optional[str] = None
    data_alteracao: Optional[datetime] = None
    arquivo_origem: Optional[str] = None


class LdImportResultado(BaseModel):
    origem_arquivo: Optional[str] = None
    total_linhas: int
    novos: int
    atualizados: int
    status_alterados: int
    sem_mudanca: int
    revisoes_detectadas: int = 0
    transicoes: list[dict] = []
    colunas_detectadas: dict = {}
    aba: Optional[str] = None
    linha_cabecalho: Optional[int] = None
    linhas_ignoradas: Optional[int] = None


class SigemDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo_documento: str
    revisao: Optional[str] = None
    status: Optional[str] = None
    modificado_em: Optional[datetime] = None
    incluido_em: Optional[datetime] = None
    nivel_1: Optional[str] = None
    nivel_2: Optional[str] = None
    nivel_3: Optional[str] = None
    nivel_4: Optional[str] = None
    nivel_5: Optional[str] = None
    nivel_6: Optional[str] = None
    nivel_7: Optional[str] = None
    nivel_8: Optional[str] = None
    origem_arquivo: Optional[str] = None
    data_importacao: Optional[datetime] = None


class SigemImportResultado(BaseModel):
    origem_arquivo: Optional[str] = None
    total_linhas: int
    novos: int
    atualizados: int
    status_alterados: int
    sem_mudanca: int
    revisoes_detectadas: int = 0
    transicoes: list[dict] = []
    colunas_detectadas: dict = {}
    aba: Optional[str] = None
    linha_cabecalho: Optional[int] = None
    linhas_ignoradas: Optional[int] = None


class RevisaoPedidoOut(BaseModel):
    numero_pedido: Optional[str] = None
    status_pedido: Optional[str] = None
    revisao_documento_usada: Optional[str] = None
    data_pedido: Optional[date] = None


class RevisaoVariacaoOut(BaseModel):
    item_controlavel: Optional[str] = None
    quantidade_anterior: Optional[float] = None
    quantidade_nova: Optional[float] = None
    diferenca_quantidade: Optional[float] = None
    unidade: Optional[str] = None
    tipo_variacao: Optional[str] = None


class EventoRevisaoOut(BaseModel):
    id: int
    id_evento_revisao: str
    codigo_documento: str
    revisao_anterior: Optional[str] = None
    revisao_nova: str
    data_deteccao: Optional[datetime] = None
    controle_aplicavel: Optional[str] = None
    setor: Optional[str] = None
    area: Optional[str] = None
    codigo_controle_afetado: Optional[str] = None
    status_controle: Optional[str] = None
    status_analise: Optional[str] = None
    impacto_informado: Optional[str] = None
    acao_necessaria: Optional[str] = None
    observacao_impacto: Optional[str] = None
    alertas: list[str] = []
    pedido: Optional[RevisaoPedidoOut] = None
    variacao: Optional[RevisaoVariacaoOut] = None


class AnaliseRevisaoUpdate(BaseModel):
    status_analise: Optional[str] = None
    analisado_por: Optional[str] = None
    impacto_informado: Optional[str] = None
    acao_necessaria: Optional[str] = None
    observacao_impacto: Optional[str] = None
    item_controlavel: Optional[str] = None
    quantidade_anterior: Optional[float] = None
    quantidade_nova: Optional[float] = None
    unidade: Optional[str] = None
    tipo_variacao: Optional[str] = None
    acao_pedido: Optional[str] = None


class ControleDocumentoIn(BaseModel):
    documento_origem: str
    revisao_documento: Optional[str] = None
    controle_aplicavel: Optional[str] = None
    setor: Optional[str] = None
    area: Optional[str] = None
    codigo_controle: Optional[str] = None
    status_controle: Optional[str] = "Aberto"
    tem_pedido: Optional[bool] = False
    numero_pedido: Optional[str] = None
    status_pedido: Optional[str] = None
    revisao_documento_usada: Optional[str] = None
    data_pedido: Optional[date] = None
    tem_material: Optional[bool] = False
    tem_montagem: Optional[bool] = False
    entrou_medicao_report: Optional[bool] = False


class ControleDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo_controle: str
    documento_origem: str
    revisao_documento: Optional[str] = None
    controle_aplicavel: Optional[str] = None
    setor: Optional[str] = None
    area: Optional[str] = None
    status_controle: Optional[str] = None
    tem_pedido: Optional[bool] = False
    numero_pedido: Optional[str] = None
    status_pedido: Optional[str] = None
    revisao_documento_usada: Optional[str] = None
    data_pedido: Optional[date] = None
    tem_material: Optional[bool] = False
    tem_montagem: Optional[bool] = False
    entrou_medicao_report: Optional[bool] = False
