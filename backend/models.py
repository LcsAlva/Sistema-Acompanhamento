from sqlalchemy import Column, Integer, String, Text, Boolean, Float, Date, DateTime, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Tarefa(Base):
    __tablename__ = "tarefas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, nullable=False, unique=True)  # Ex: URFCC-C-202250
    nome = Column(String, nullable=False)
    disciplina = Column(String)   # Civil, Caldeiraria, etc.
    supervisor = Column(String)
    encarregado = Column(String)
    area_unidade = Column(String)  # TGV, Hidratacao, etc.
    wbs_codigo = Column(String)    # Ex: URFCC-2026-04-05.1.2.1.4
    wbs_path = Column(Text)        # JSON: lista de wbs_name do raiz até o nó pai da tarefa
    duracao = Column(Integer)      # Em dias
    inicio_lb = Column(Date)       # Linha de base
    termino_lb = Column(Date)      # Linha de base
    inicio_atual = Column(Date)    # Início real (start_date / Early Start do P6)
    termino_atual = Column(Date)   # Término real (end_date / Early Finish do P6)
    pct_avanco = Column(Float, default=0.0)       # % físico atual (phys_complete_pct do P6)
    unid_orcadas_smo = Column(Float)              # Peso SMO (target_equip_qty)

    programacoes = relationship("ProgramacaoSemanal", back_populates="tarefa")


class Semana(Base):
    __tablename__ = "semanas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True)  # Ex: S_035
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    # Snapshot imutável gravado ao fechar a semana
    fechada = Column(Boolean, default=False)
    fechada_em = Column(DateTime)
    snap_qcron = Column(Integer)
    snap_qprog = Column(Integer)
    snap_qreal = Column(Integer)
    snap_pct_exec = Column(Float)

    programacoes = relationship(
        "ProgramacaoSemanal",
        primaryjoin="Semana.codigo == foreign(ProgramacaoSemanal.semana)",
        back_populates="semana_rel",
    )
    relatorio = relationship(
        "RelatorioSemana",
        primaryjoin="Semana.codigo == foreign(RelatorioSemana.semana)",
        back_populates="semana_rel",
        uselist=False,
    )


class ProgramacaoSemanal(Base):
    __tablename__ = "programacao_semanal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    semana = Column(String, nullable=False)           # FK lógica para semanas.codigo
    tarefa_id = Column(Integer, ForeignKey("tarefas.id"), nullable=False)
    # Datas base para cálculo QCRON
    inicio_prog = Column(Date)
    termino_prog = Column(Date)
    # QPROG - seleção do planejador
    no_qprog = Column(Boolean, default=False)
    inicio_qprog = Column(Date)
    termino_qprog = Column(Date)
    status_atividade = Column(String)                 # P6: status_code (Concluído/Em Progresso/Não Iniciado)
    pct_avanco = Column(Float, default=0.0)           # 0 a 100 (previsto — sched_complete_pct)
    pct_executado = Column(Float, default=0.0)        # 0 a 100 (executado — equip_complete_pct)
    # Datas REAIS — preenchidas manualmente pelo planejador. Aparecem
    # no PDF (coluna "Programado") com prioridade sobre as datas do
    # cronograma. Independentes do cronograma.
    inicio_real = Column(Date)
    termino_real = Column(Date)
    # QREAL - lançamento retrospectivo
    qreal_concluida = Column(Boolean, default=False)
    pct_qreal = Column(Float, default=0.0)            # 0 a 100
    # Campos textuais
    observacoes = Column(Text)
    condicao_1 = Column(String)
    condicao_2 = Column(String)
    # Adiantamento manual
    adiantada = Column(Boolean, default=False)
    semana_original = Column(String)               # Semana onde a atividade estava originalmente
    # Auditoria
    usuario = Column(String)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tarefa = relationship("Tarefa", back_populates="programacoes")
    semana_rel = relationship(
        "Semana",
        primaryjoin="foreign(ProgramacaoSemanal.semana) == Semana.codigo",
        back_populates="programacoes",
    )
    sub_tarefas = relationship("SubTarefa", back_populates="programacao", cascade="all, delete-orphan", order_by="SubTarefa.id")


class SubTarefa(Base):
    __tablename__ = "sub_tarefas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    programacao_id = Column(Integer, ForeignKey("programacao_semanal.id"), nullable=False)
    descricao = Column(String, nullable=False)
    status = Column(String, default="nao_executada")  # concluida / parcial / nao_executada
    inicio_qprog = Column(Date)
    termino_qprog = Column(Date)
    criado_em = Column(DateTime, server_default=func.now())

    programacao = relationship("ProgramacaoSemanal", back_populates="sub_tarefas")


class RelatorioSemana(Base):
    __tablename__ = "relatorio_semana"

    id = Column(Integer, primary_key=True, autoincrement=True)
    semana = Column(String, nullable=False, unique=True)
    descricao_resumida = Column(String)               # max 400 chars
    justificativas_atraso = Column(Text)              # JSON list
    marcos_observacoes = Column(Text)                 # JSON list
    condicoes_climaticas = Column(Text)               # JSON (dados Open-Meteo)
    nota_clima = Column(String)

    semana_rel = relationship(
        "Semana",
        primaryjoin="foreign(RelatorioSemana.semana) == Semana.codigo",
        back_populates="relatorio",
    )


class Import(Base):
    __tablename__ = "imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String, nullable=False)             # xlsx ou xer
    semana_ref = Column(String, nullable=False)
    arquivo_original = Column(String)
    importado_em = Column(DateTime, server_default=func.now())
    usuario = Column(String)
    status = Column(String, default="ok")             # ok, erro, reprocessado


# ── Gestão Econômica - Fase 1A: importação e auditoria ───────────────────────

class EconomicoImportacao(Base):
    __tablename__ = "economico_importacao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    arquivo_original = Column(String, nullable=False)
    importado_em = Column(DateTime, server_default=func.now())
    usuario = Column(String)
    status = Column(String, default="ok")
    observacao = Column(Text)

    valores = relationship("EconomicoValor", back_populates="importacao", cascade="all, delete-orphan")
    auditorias = relationship("EconomicoAuditoria", back_populates="importacao", cascade="all, delete-orphan")


class EconomicoValor(Base):
    __tablename__ = "economico_valor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False, index=True)       # sistema | resumo_bi
    indicador = Column(String, nullable=False, index=True)
    cenario = Column(String, nullable=False, index=True)    # linha_base | real | tendencia
    periodo = Column(Date, index=True)                      # null = acumulado
    categoria = Column(String, index=True)
    valor = Column(Float, default=0.0)
    origem = Column(String)

    importacao = relationship("EconomicoImportacao", back_populates="valores")


class EconomicoAuditoria(Base):
    __tablename__ = "economico_auditoria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    indicador = Column(String, nullable=False)
    sistema = Column(Float, default=0.0)
    resumo_bi = Column(Float, default=0.0)
    diferenca = Column(Float, default=0.0)
    aprovado = Column(Boolean, default=False)
    tolerancia = Column(Float, default=0.01)
    origem_sistema = Column(String)
    origem_resumo_bi = Column(String)

    importacao = relationship("EconomicoImportacao", back_populates="auditorias")


class EconomicoResumoCalculado(Base):
    __tablename__ = "economico_resumo_calculado"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    indicador = Column(String, nullable=False, index=True)
    cenario = Column(String, nullable=False, index=True)
    periodo = Column(Date, index=True)
    categoria = Column(String, index=True)
    valor = Column(Float, default=0.0)
    origem = Column(String)


class EconomicoLancamentoRazao(Base):
    __tablename__ = "economico_lancamento_razao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    data = Column(Date, index=True)
    documento = Column(String, index=True)
    fornecedor = Column(String, index=True)
    conta = Column(String, index=True)
    conta_descricao = Column(String)
    categoria_dre = Column(String, index=True)
    historico = Column(Text)
    valor = Column(Float, default=0.0)
    tipo = Column(String)
    lote = Column(String)
    lancamento = Column(String)


class EconomicoRelatorioOC(Base):
    __tablename__ = "economico_relatorio_oc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    numero_oc = Column(String, index=True)
    item_oc = Column(String)
    requisicao = Column(String)
    produto = Column(String)
    descricao = Column(Text)
    fornecedor = Column(String, index=True)
    data = Column(Date, index=True)
    conta = Column(String, index=True)
    conta_descricao = Column(String)
    valor_total = Column(Float, default=0.0)
    valor_liquido = Column(Float, default=0.0)
    valor_nf = Column(Float, default=0.0)


class EconomicoAnaliseDRE(Base):
    __tablename__ = "economico_analise_dre"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    categoria = Column(String, nullable=False, index=True)
    projetado = Column(Float, default=0.0)
    razao = Column(Float, default=0.0)
    asocnf = Column(Float, default=0.0)
    fat_nao_lancado_razao = Column(Float, default=0.0)
    forecast = Column(Float, default=0.0)
    previsao_anterior = Column(Float, default=0.0)
    considerar = Column(Float, default=0.0)


class EconomicoContaDespesa(Base):
    __tablename__ = "economico_conta_despesa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    conta = Column(String, nullable=False, index=True)
    descricao = Column(String)
    comentario = Column(Text)
    agrupamento_dre = Column(String, index=True)


class EconomicoForecastVersao(Base):
    __tablename__ = "economico_forecast_versao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    codigo = Column(String, nullable=False, unique=True, index=True)
    nome = Column(String, nullable=False)
    motivo = Column(Text)
    status = Column(String, nullable=False, default="rascunho", index=True)
    origem = Column(String, nullable=False, default="importacao", index=True)
    versao_base_id = Column(Integer, ForeignKey("economico_forecast_versao.id"), index=True)
    criado_por = Column(String)
    criado_em = Column(DateTime, server_default=func.now())

    importacao = relationship("EconomicoImportacao")
    versao_base = relationship("EconomicoForecastVersao", remote_side=[id])
    itens = relationship("EconomicoForecastItem", back_populates="versao", cascade="all, delete-orphan")
    ajustes = relationship("EconomicoForecastAjuste", back_populates="versao", cascade="all, delete-orphan")
    historicos = relationship("EconomicoForecastHistorico", back_populates="versao", cascade="all, delete-orphan")


class EconomicoForecastItem(Base):
    __tablename__ = "economico_forecast_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    versao_id = Column(Integer, ForeignKey("economico_forecast_versao.id"), nullable=False, index=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    indicador = Column(String, nullable=False, index=True)
    periodo = Column(Date, index=True)
    categoria = Column(String, index=True)
    valor = Column(Float, default=0.0)
    origem = Column(String)

    versao = relationship("EconomicoForecastVersao", back_populates="itens")


class EconomicoForecastAjuste(Base):
    __tablename__ = "economico_forecast_ajuste"

    id = Column(Integer, primary_key=True, autoincrement=True)
    versao_id = Column(Integer, ForeignKey("economico_forecast_versao.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("economico_forecast_item.id"), index=True)
    categoria = Column(String, nullable=False, index=True)
    valor_anterior = Column(Float, default=0.0)
    valor_novo = Column(Float, default=0.0)
    diferenca = Column(Float, default=0.0)
    justificativa = Column(Text, nullable=False)
    usuario = Column(String)
    criado_em = Column(DateTime, server_default=func.now())

    versao = relationship("EconomicoForecastVersao", back_populates="ajustes")
    item = relationship("EconomicoForecastItem")


class EconomicoForecastHistorico(Base):
    __tablename__ = "economico_forecast_historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    versao_id = Column(Integer, ForeignKey("economico_forecast_versao.id"), nullable=False, index=True)
    acao = Column(String, nullable=False, index=True)
    descricao = Column(Text)
    usuario = Column(String)
    payload = Column(Text)
    criado_em = Column(DateTime, server_default=func.now())

    versao = relationship("EconomicoForecastVersao", back_populates="historicos")


class PerformanceCustoClassificacao(Base):
    __tablename__ = "performance_custo_classificacao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    categoria_dre = Column(String, nullable=False, index=True)
    classificacao = Column(String, nullable=False, index=True)  # proporcional | nao_proporcional | hibrido
    comportamento = Column(String)
    risco_interpretacao = Column(Text)
    regra = Column(Text)
    criado_em = Column(DateTime, server_default=func.now())


class PerformanceAuditoriaMes(Base):
    __tablename__ = "performance_auditoria_mes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    importacao_id = Column(Integer, ForeignKey("economico_importacao.id"), nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("prod_projeto.id"), nullable=True, index=True)
    mes = Column(Date, nullable=False, index=True)
    avanco_fisico_pct = Column(Float, default=0.0)
    receita_acumulada = Column(Float, default=0.0)
    custos_acumulados = Column(Float, default=0.0)
    resultado_acumulado = Column(Float, default=0.0)
    fonte_fisica = Column(String)
    fonte_economica = Column(String)
    riscos = Column(Text)
    criado_em = Column(DateTime, server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=False, unique=True)
    senha_hash = Column(String, nullable=False)


class PainelSnapshot(Base):
    __tablename__ = "painel_snapshot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    semana = Column(String, nullable=False)           # FK lógica → semanas.codigo
    data_referencia = Column(Date)                    # = semana.data_fim
    avanco_real = Column(Float)                       # % real acumulado do projeto
    avanco_prev_lb = Column(Float)                    # % previsto LB acumulado para data_referencia
    importado_em = Column(DateTime, server_default=func.now())


class PainelFaseSemana(Base):
    __tablename__ = "painel_fase_semana"
    id = Column(Integer, primary_key=True, autoincrement=True)
    semana = Column(String, nullable=False)
    fase = Column(String, nullable=False)             # ex: "CONSTRUÇÃO CIVIL"
    pct_prev_lb = Column(Float)
    pct_real = Column(Float)
    peso_total = Column(Float)


# ── EAP Financeira ─────────────────────────────────────────────────────
# Importada do XLSX da Petrobras. Cada item tem:
#   - codigo: hierárquico tipo "1.2.1.3"
#   - nivel: profundidade (1..8)
#   - parent_codigo: prefixo (ex.: "1.2.1" para "1.2.1.3")
#   - valor: R$ orçados para esta folha
#   - dist_mensal: JSON {"2025-08-01": 0.05, "2025-09-01": 0.10, ...}
#                  fração do valor alocada em cada mês (curva-S prevista)

class EapItem(Base):
    __tablename__ = "eap_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True, index=True)
    descricao = Column(String, nullable=False)
    nivel = Column(Integer, nullable=False)
    parent_codigo = Column(String, index=True)         # null no nível 1
    valor = Column(Float, default=0.0)                 # R$ desta folha (0 para nós-pai)
    dist_mensal = Column(Text)                         # JSON {month_iso: fração}
    criterio = Column(Text)                            # Critério de medição (foto, RDO, teste hidrostático…)
    unidade = Column(String, default='%')              # Unidade de medição (%, m³, un, etc.)
    importado_em = Column(DateTime, server_default=func.now())


# Mapeia uma tarefa do P6 para um ou mais itens-folha da EAP.
# `peso` permite distribuir o avanço entre múltiplos itens (default 1.0
# para mapeamento 1:1). Quando uma tarefa avança X%, o EV da EAP item
# correspondente recebe `valor × X% × peso`.

class TarefaEapLink(Base):
    __tablename__ = "tarefa_eap_link"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarefa_id = Column(Integer, ForeignKey("tarefas.id"), nullable=False, index=True)
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)
    peso = Column(Float, default=1.0)
    criado_em = Column(DateTime, server_default=func.now())


# ── Ciclo de medição mensal ────────────────────────────────────────────
# 1. Previsão (início do mês): planejador define quais itens vai medir
#    e em que % cada um. Pode partir do P6 e ajustar.
# 2. Avanço semanal: a cada semana, lança o DELTA do que avançou no item
#    (ex.: "+5%"). O acumulado total é a soma dos deltas até a data.
# 3. Fechamento (dia 25): snapshot imutável do BM do mês.

class EapPrevisaoMensal(Base):
    __tablename__ = "eap_previsao_mensal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ano = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=False, index=True)
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)
    pct_previsto = Column(Float, default=0.0)         # 0..100
    observacao = Column(Text)
    lancado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())
    lancado_por = Column(String)
    adiantada = Column(Boolean, default=False)
    mes_original_ano = Column(Integer)   # ano do mês onde estava originalmente planejado
    mes_original_mes = Column(Integer)   # mês onde estava originalmente planejado
    # Status da previsão mensal: em_edicao | fechada | convertida
    # em_edicao: pode ser editada pelo planejador
    # fechada: congelada — BM pode ser aberto para snapshot
    # convertida: snapshot já foi tirado (BM aberto); bloqueia edição
    status_previsao = Column(String, default="em_edicao", nullable=False)


class EapAvancoSemanal(Base):
    __tablename__ = "eap_avanco_semanal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    semana_codigo = Column(String, nullable=False, index=True)   # ex.: "S_038"
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)
    pct_delta = Column(Float, default=0.0)             # delta da semana (+ ou - se ajuste)
    observacao = Column(Text)
    lancado_em = Column(DateTime, server_default=func.now())
    lancado_por = Column(String)


# ── Ciclo de Medição Mensal (BM) ───────────────────────────────────────

class CicloMedicao(Base):
    __tablename__ = "ciclo_medicao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)          # 1–12
    status = Column(String, default="aberto")      # "aberto" | "fechado"
    fechado_em = Column(DateTime)
    fechado_por = Column(String)
    observacao = Column(Text)
    criado_em = Column(DateTime, server_default=func.now())
    lancamentos = relationship("LancamentoMedicao", back_populates="ciclo", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("ano", "mes", name="uq_ciclo_ano_mes"),)


class LancamentoMedicao(Base):
    __tablename__ = "lancamento_medicao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("ciclo_medicao.id"), nullable=False)
    eap_codigo = Column(String, nullable=False)
    pct_acumulado = Column(Float, default=0.0)   # % total acumulado até este mês (0.0–1.0)
    observacao = Column(Text)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())
    ciclo = relationship("CicloMedicao", back_populates="lancamentos")
    __table_args__ = (UniqueConstraint("ciclo_id", "eap_codigo", name="uq_lanc_ciclo_eap"),)


# ── Lista de Documentos de Engenharia ─────────────────────────────────
# Fase 3 — cada documento contribui para o avanço do item EAP 2.1.1.
# Emissão (EM_ANALISE ou posterior) = 60% do peso do documento.
# Aprovação (SEM_COMENTARIOS ou APROVADO) = 100% do peso do documento.

class DocumentoEngenharia(Base):
    __tablename__ = "documento_engenharia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True, index=True)   # Ex: PE-1080-0001
    titulo = Column(String, nullable=False)
    disciplina = Column(String)      # Civil, Mecânico, Elétrico, Processo…
    tipo_doc = Column(String)        # Memorial de Cálculo, Desenho, Especificação…
    revisao_atual = Column(String)   # 0, 1, A, B…
    # Status: EM_ELABORACAO | EM_ANALISE | COM_COMENTARIOS | SEM_COMENTARIOS | APROVADO
    status = Column(String, default="EM_ELABORACAO")
    emitido_em = Column(Date)        # data da primeira emissão (transição → EM_ANALISE)
    aprovado_em = Column(Date)       # data de aprovação formal
    peso = Column(Float, default=1.0)   # peso para cálculo do % 2.1.1 (complexidade)
    observacao = Column(Text)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Relatório Fotográfico ─────────────────────────────────────────────
# Fotos de evidência por item EAP, vinculadas a um ciclo de medição (ano/mês).

class FotoMedicao(Base):
    __tablename__ = "foto_medicao"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    eap_codigo = Column(String, nullable=False, index=True)
    eap_descricao = Column(String)          # denormalized for display
    numero = Column(Integer)                # sequential photo number in document
    legenda = Column(String)                # caption text
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    tamanho = Column(Integer)               # bytes
    criado_em = Column(DateTime, server_default=func.now())
    lancado_por = Column(String)


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO DE AVANÇO FINANCEIRO — ARQUITETURA REFATORADA
# ═══════════════════════════════════════════════════════════════════════════════
#
# Separação limpa de responsabilidades:
#   EAP original           → eap_item (imutável entre importações)
#   Planejamento           → eap_previsao_mensal (editável até abertura do BM)
#   Snapshot da previsão   → bm_snapshot_previsao (congelado ao abrir BM)
#   Medição/BM             → bm_ciclo + bm_lancamento (imutável após fechamento)
#   Versionamento          → bm_versao (audit trail)
#   Consolidação           → bm_consolidado (materializado após fechamento)
#   Pendências             → bm_pendencia (persistida) + bm_pendencia_redistrib
#
# Escala única: TODOS os % nestas tabelas usam 0.0–1.0 (fração decimal).
# Contraste com eap_previsao_mensal.pct_previsto que usa 0–100 (legado).
# ═══════════════════════════════════════════════════════════════════════════════

# Status permitidos para BmCiclo
# em_previa → em_analise → pre_aprovada → fechada → consolidada
_STATUS_CICLO = ("em_previa", "em_analise", "pre_aprovada", "fechada", "consolidada")


class BmCiclo(Base):
    """Ciclo de medição mensal (BM) com máquina de estados completa.

    Substitui CicloMedicao como fonte de verdade para o fluxo de BM.
    CicloMedicao continua existindo para compatibilidade com código legado.
    """
    __tablename__ = "bm_ciclo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ano = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=False, index=True)                    # 1–12

    # Máquina de estados: em_previa → em_analise → pre_aprovada → fechada → consolidada
    status = Column(String, nullable=False, default="em_previa", index=True)

    # Número sequencial do BM (ex: BM-001, BM-002 …)
    numero_bm = Column(String, index=True)

    # Referência cruzada com o ciclo legado (para compatibilidade)
    ciclo_legado_id = Column(Integer, ForeignKey("ciclo_medicao.id"), nullable=True)

    # Metadados de cada transição de status
    criado_em       = Column(DateTime, server_default=func.now())
    criado_por      = Column(String)
    enviado_analise_em  = Column(DateTime)
    enviado_analise_por = Column(String)
    pre_aprovado_em     = Column(DateTime)
    pre_aprovado_por    = Column(String)
    fechado_em          = Column(DateTime)
    fechado_por         = Column(String)
    consolidado_em      = Column(DateTime)
    consolidado_por     = Column(String)

    observacao = Column(Text)

    lancamentos  = relationship("BmLancamento",         back_populates="ciclo", cascade="all, delete-orphan")
    snapshots    = relationship("BmSnapshotPrevisao",   back_populates="ciclo", cascade="all, delete-orphan")
    versoes      = relationship("BmVersao",             back_populates="ciclo", cascade="all, delete-orphan")
    consolidados = relationship("BmConsolidado",        back_populates="ciclo", cascade="all, delete-orphan")
    pendencias   = relationship("BmPendencia",          back_populates="ciclo", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("ano", "mes", name="uq_bm_ciclo_ano_mes"),)


class BmSnapshotPrevisao(Base):
    """Snapshot imutável da previsão no momento da abertura do BM.

    Registra exatamente o que estava planejado quando o BM foi criado.
    Permite auditoria: o que foi previsto vs. o que foi medido.
    Não pode ser editado após criação.
    """
    __tablename__ = "bm_snapshot_previsao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id = Column(Integer, ForeignKey("bm_ciclo.id"), nullable=False, index=True)
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)

    # Escala 0.0–1.0 (normalizado de pct_previsto/100)
    pct_previsto     = Column(Float, nullable=False, default=0.0)
    adiantada        = Column(Boolean, default=False)
    mes_origem_ano   = Column(Integer)   # mês original se adiantada
    mes_origem_mes   = Column(Integer)

    observacao = Column(Text)
    capturado_em = Column(DateTime, server_default=func.now())

    ciclo = relationship("BmCiclo", back_populates="snapshots")

    __table_args__ = (UniqueConstraint("ciclo_id", "eap_codigo", name="uq_bm_snap_ciclo_eap"),)


class BmLancamento(Base):
    """Lançamento de % medido por item EAP no BM.

    pct_acumulado: % acumulado total do projeto INCLUINDO este BM (0.0–1.0).
    Editável apenas quando ciclo.status in ('em_previa', 'em_analise', 'pre_aprovada').
    Imutável após ciclo.status = 'fechada'.
    """
    __tablename__ = "bm_lancamento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id   = Column(Integer, ForeignKey("bm_ciclo.id"), nullable=False, index=True)
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)

    # Escala 0.0–1.0
    pct_acumulado = Column(Float, nullable=False, default=0.0)
    observacao    = Column(Text)

    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())
    atualizado_por = Column(String)

    ciclo = relationship("BmCiclo", back_populates="lancamentos")

    __table_args__ = (UniqueConstraint("ciclo_id", "eap_codigo", name="uq_bm_lanc_ciclo_eap"),)


class BmVersao(Base):
    """Audit trail: snapshot completo dos lançamentos a cada save.

    Permite ver exatamente o que estava no BM em cada momento antes do fechamento.
    Imutável após criação.
    """
    __tablename__ = "bm_versao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id   = Column(Integer, ForeignKey("bm_ciclo.id"), nullable=False, index=True)
    numero_versao = Column(Integer, nullable=False)   # 1, 2, 3, …
    status_no_momento = Column(String)                # status do ciclo ao salvar
    lancamentos_json  = Column(Text, nullable=False)  # JSON [{eap_codigo, pct_acumulado, obs}, …]
    total_valor_periodo = Column(Float, default=0.0)  # R$ do período nesta versão
    pct_acum_projeto  = Column(Float, default=0.0)    # % acumulado do projeto

    criado_em  = Column(DateTime, server_default=func.now())
    criado_por = Column(String)

    ciclo = relationship("BmCiclo", back_populates="versoes")

    __table_args__ = (UniqueConstraint("ciclo_id", "numero_versao", name="uq_bm_versao_ciclo_num"),)


class BmConsolidado(Base):
    """Acumulados materializados por item EAP após fechamento do BM.

    Esta tabela é a fonte de verdade para o dashboard e relatórios.
    Atualizada apenas no evento de fechamento do BM.
    NÃO deve ser lida antes do fechamento.

    pct_acumulado: % acumulado total do projeto para este item até este BM (0.0–1.0).
    pct_periodo:   delta do período (acum_atual - acum_bm_anterior) (0.0–1.0).
    valor_periodo: R$ realizado no período.
    valor_acumulado: R$ acumulado total.
    """
    __tablename__ = "bm_consolidado"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id   = Column(Integer, ForeignKey("bm_ciclo.id"), nullable=False, index=True)
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)

    # Escala 0.0–1.0
    pct_acumulado   = Column(Float, nullable=False, default=0.0)
    pct_periodo     = Column(Float, nullable=False, default=0.0)
    pct_previsto    = Column(Float, nullable=False, default=0.0)   # do snapshot

    valor_item      = Column(Float, default=0.0)   # denormalizado para performance
    valor_periodo   = Column(Float, default=0.0)
    valor_acumulado = Column(Float, default=0.0)

    # Indica se este item tem filhos (para propagação já materializada)
    is_folha = Column(Boolean, default=True)
    nivel    = Column(Integer, default=1)

    criado_em = Column(DateTime, server_default=func.now())

    ciclo = relationship("BmCiclo", back_populates="consolidados")

    __table_args__ = (UniqueConstraint("ciclo_id", "eap_codigo", name="uq_bm_consol_ciclo_eap"),)


class BmPendencia(Base):
    """Pendência gerada automaticamente ao fechar o BM.

    Representa a diferença entre o que foi previsto e o que foi medido no BM.
    gap = pct_previsto - pct_periodo (em 0.0–1.0).

    Status: ativa → redistribuida (total ou parcial) → cancelada.
    """
    __tablename__ = "bm_pendencia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id   = Column(Integer, ForeignKey("bm_ciclo.id"), nullable=False, index=True)
    eap_codigo = Column(String, ForeignKey("eap_item.codigo"), nullable=False, index=True)

    # Escala 0.0–1.0
    pct_previsto = Column(Float, nullable=False)   # do snapshot da previsão
    pct_realizado = Column(Float, nullable=False)  # do lançamento medido
    pct_gap      = Column(Float, nullable=False)   # = pct_previsto - pct_realizado

    valor_item      = Column(Float, default=0.0)   # denormalizado
    valor_gap       = Column(Float, default=0.0)   # pct_gap * valor_item

    # Status da pendência
    # ativa → redistribuida_parcial → redistribuida_total | cancelada
    status = Column(String, nullable=False, default="ativa", index=True)

    pct_ja_redistribuido = Column(Float, default=0.0)   # quanto já foi redistribuído

    # Mês para onde foi redistribuído (se redistribuída integralmente)
    mes_destino_ano = Column(Integer)
    mes_destino_mes = Column(Integer)

    observacao = Column(Text)
    gerado_em  = Column(DateTime, server_default=func.now())

    ciclo          = relationship("BmCiclo", back_populates="pendencias")
    redistribuicoes = relationship("BmPendenciaRedistrib", back_populates="pendencia", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("ciclo_id", "eap_codigo", name="uq_bm_pend_ciclo_eap"),)


class BmPendenciaRedistrib(Base):
    """Histórico de redistribuição de pendências.

    Cada redistribuição registra para qual mês foi alocada e qual % foi movido.
    Permite rastrear o ciclo de vida completo de uma pendência.
    """
    __tablename__ = "bm_pendencia_redistrib"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pendencia_id = Column(Integer, ForeignKey("bm_pendencia.id"), nullable=False, index=True)

    # Para qual mês foi redistribuída
    destino_ano = Column(Integer, nullable=False)
    destino_mes = Column(Integer, nullable=False)

    # Escala 0.0–1.0
    pct_redistribuido = Column(Float, nullable=False)
    valor_redistribuido = Column(Float, default=0.0)

    observacao   = Column(Text)
    redistribuido_em = Column(DateTime, server_default=func.now())
    redistribuido_por = Column(String)

    pendencia = relationship("BmPendencia", back_populates="redistribuicoes")


class BmLog(Base):
    """Trilha de auditoria imutável do módulo BM.

    Registra cada evento relevante: abertura, transições de status,
    lançamentos, fechamentos, redistribuições. Nunca deve ser editada
    ou deletada — apenas inserida.

    Eventos padronizados:
      BM_ABERTO, STATUS_CHANGED, LANCAMENTO_SALVO,
      BM_FECHADO, BM_CONSOLIDADO, PENDENCIA_REDISTRIBUIDA,
      PREVISAO_FECHADA, PREVISAO_REABERTA
    """
    __tablename__ = "bm_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ciclo_id   = Column(Integer, ForeignKey("bm_ciclo.id"), nullable=True, index=True)
    evento     = Column(String, nullable=False, index=True)
    usuario    = Column(String)
    detalhe    = Column(Text)      # JSON livre com contexto do evento
    valor_antes  = Column(Text)    # JSON snapshot antes da mudança
    valor_depois = Column(Text)    # JSON snapshot depois da mudança
    criado_em  = Column(DateTime, server_default=func.now(), index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO DE COMPETÊNCIA FINANCEIRA — ENGINE DE GOVERNANÇA
# ═══════════════════════════════════════════════════════════════════════════════
#
# Camada formal de controle de competência financeira por mês.
# Independente do BM — pode existir sem BM aberto.
# Controla lock temporal e rastreabilidade de fechamento contábil.
#
# Máquina de estados:
#   aberta → em_apuracao → fechada → consolidada → encerrada_contabilmente
#
# Regras:
#   - Apenas aberta/em_apuracao permitem movimentos operacionais
#   - encerrada_contabilmente seta locked=True automaticamente
#   - locked=True bloqueia QUALQUER alteração independente do status
# ═══════════════════════════════════════════════════════════════════════════════

_STATUS_COMPETENCIA = (
    "aberta", "em_apuracao", "fechada", "consolidada", "encerrada_contabilmente"
)


class CompetenciaFinanceira(Base):
    """Competência financeira mensal — controle formal de governança.

    Uma competência por mês (unique(ano, mes)).
    Criada automaticamente como 'aberta' na primeira operação do mês,
    ou manualmente via endpoint POST /api/competencias/{ano}/{mes}/abrir.
    """
    __tablename__ = "competencia_financeira"

    id  = Column(Integer, primary_key=True, autoincrement=True)
    ano = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=False, index=True)

    status = Column(String, nullable=False, default="aberta", index=True)
    locked = Column(Boolean, nullable=False, default=False)

    # Rastreabilidade de cada transição
    aberto_em       = Column(DateTime)
    aberto_por      = Column(String)
    em_apuracao_em  = Column(DateTime)
    em_apuracao_por = Column(String)
    fechado_em      = Column(DateTime)
    fechado_por     = Column(String)
    consolidado_em  = Column(DateTime)
    consolidado_por = Column(String)
    encerrado_em    = Column(DateTime)
    encerrado_por   = Column(String)

    observacao  = Column(Text)
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())

    logs = relationship("CompetenciaLog", back_populates="competencia",
                        cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("ano", "mes", name="uq_competencia_ano_mes"),
    )


class CompetenciaLog(Base):
    """Trilha de auditoria das transições de competência financeira.

    Imutável após inserção. Registra cada mudança de status com
    rastreabilidade completa de quem, quando e por quê.
    """
    __tablename__ = "competencia_log"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    competencia_id = Column(Integer, ForeignKey("competencia_financeira.id"),
                            nullable=False, index=True)
    evento         = Column(String, nullable=False, index=True)
    status_antes   = Column(String)
    status_depois  = Column(String)
    usuario        = Column(String)
    observacao     = Column(Text)
    criado_em      = Column(DateTime, server_default=func.now(), index=True)

    competencia = relationship("CompetenciaFinanceira", back_populates="logs")


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2A — SISTEMA DE MEDIÇÃO PETROBRAS (Integração LD/SIGEM + Critérios)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Plataforma de medição automática baseada nos critérios contratuais Petrobras.
# Regras de negócio (parametrizáveis, NÃO fixas para a RECAP):
#   - Status apto para medição = "SEM WORKFLOW" (não existe "Aprovado").
#   - SEM WORKFLOW ⇒ 100% aceito para fins de medição.
#   - LD recebida da S5 = fonte oficial semanal; SIGEM = origem dos status.
#
# Estas tabelas vivem SEPARADAS do DocumentoEngenharia (item EAP 2.1.1), que
# permanece intacto. O conjunto de status aptos e os pesos vêm de config; os
# critérios por item EAP vêm da tabela criterios_medicao (estratégia por tipo).
# ═══════════════════════════════════════════════════════════════════════════════


class CriterioMedicao(Base):
    """Matriz de critérios de medição Petrobras — parametrização por item EAP.

    Cada item da EAP possui seu próprio critério (unique codigo_eap). O
    `tipo_criterio` é um IDENTIFICADOR DE ESTRATÉGIA resolvido por um registry
    de handlers (ver services/criterios_service.py), não uma regra fixa.
    `parametros` (JSON) guarda configs específicas do tipo (disciplina-alvo,
    fonte, fator, etc.), permitindo reutilização em outros contratos.
    """
    __tablename__ = "criterios_medicao"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_eap = Column(String, nullable=False, unique=True, index=True)
    descricao = Column(String)
    tipo_criterio = Column(String, nullable=False, default="MANUAL", index=True)
    peso = Column(Float, default=1.0)
    evidencia_obrigatoria = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    parametros = Column(Text)          # JSON livre com configs do tipo
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LdDocumento(Base):
    """Documento da Lista de Documentos (LD) recebida da S5 / status SIGEM.

    Fonte oficial semanal de engenharia. Cada documento é único por
    `codigo_documento`; novas revisões atualizam o mesmo registro e cada
    mudança de status gera uma linha em ld_historico_status.
    """
    __tablename__ = "ld_documentos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_documento = Column(String, nullable=False, unique=True, index=True)
    titulo = Column(String)
    disciplina = Column(String, index=True)
    revisao = Column(String)
    status = Column(String, index=True)        # ex.: "SEM WORKFLOW", "EM ELABORAÇÃO"…
    a4_equivalente = Column(Float, default=0.0)
    data_prevista = Column(Date)
    data_emissao = Column(Date)
    data_importacao = Column(DateTime, server_default=func.now())
    origem_arquivo = Column(String)            # nome do arquivo LD que originou/atualizou

    historico = relationship(
        "LdHistoricoStatus", back_populates="documento",
        cascade="all, delete-orphan", order_by="LdHistoricoStatus.data_alteracao",
    )


class LdHistoricoStatus(Base):
    """Histórico de transições de status de um documento da LD (auditoria).

    Substitui a atualização manual do 'LD Histórico Medição': cada importação
    que altere o status de um documento grava aqui a transição anterior→novo.
    """
    __tablename__ = "ld_historico_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    documento_id = Column(Integer, ForeignKey("ld_documentos.id"), nullable=False, index=True)
    status_anterior = Column(String)
    status_novo = Column(String)
    data_alteracao = Column(DateTime, server_default=func.now(), index=True)
    arquivo_origem = Column(String)

    documento = relationship("LdDocumento", back_populates="historico")


class SigemDocumento(Base):
    """Snapshot atual do SIGEM por documento.

    A LD continua sendo a fonte da estrutura documental. Esta tabela guarda a
    visão mais recente do SIGEM para status, revisão corrente, datas e
    hierarquia do workflow.
    """
    __tablename__ = "sigem_documentos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_documento = Column(String, nullable=False, unique=True, index=True)
    revisao = Column(String)
    status = Column(String, index=True)
    modificado_em = Column(DateTime)
    incluido_em = Column(DateTime)
    nivel_1 = Column(String)
    nivel_2 = Column(String)
    nivel_3 = Column(String)
    nivel_4 = Column(String)
    nivel_5 = Column(String)
    nivel_6 = Column(String)
    nivel_7 = Column(String)
    nivel_8 = Column(String)
    origem_arquivo = Column(String)
    data_importacao = Column(DateTime, server_default=func.now())

    historico = relationship(
        "SigemHistoricoStatus", back_populates="documento",
        cascade="all, delete-orphan", order_by="SigemHistoricoStatus.data_alteracao",
    )


class SigemHistoricoStatus(Base):
    """Histórico de mudanças de status detectadas em importações SIGEM."""
    __tablename__ = "sigem_historico_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    documento_id = Column(Integer, ForeignKey("sigem_documentos.id"), nullable=False, index=True)
    status_anterior = Column(String)
    status_novo = Column(String)
    data_alteracao = Column(DateTime, server_default=func.now(), index=True)
    arquivo_origem = Column(String)

    documento = relationship("SigemDocumento", back_populates="historico")


class DocumentoRevisao(Base):
    """Historico formal de revisoes LD/SIGEM por codigo de documento."""
    __tablename__ = "documento_revisoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_documento = Column(String, nullable=False, index=True)
    revisao = Column(String, nullable=False)
    revisao_vigente = Column(Boolean, default=True, nullable=False, index=True)
    status_documento = Column(String, default="Vigente", index=True)
    status_classificacao = Column(String, default="Pendente de classificacao", index=True)
    data_recebimento = Column(DateTime, server_default=func.now(), index=True)
    origem = Column(String, default="Manual", index=True)
    arquivo = Column(String)
    observacao_revisao = Column(Text)
    substitui_revisao = Column(String)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ControleDocumento(Base):
    """Controle vinculado a documento para sinalizacao de impacto de revisao."""
    __tablename__ = "controles_documento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_controle = Column(String, nullable=False, unique=True, index=True)
    documento_origem = Column(String, nullable=False, index=True)
    revisao_documento = Column(String)
    controle_aplicavel = Column(String)
    setor = Column(String, index=True)
    area = Column(String, index=True)
    status_controle = Column(String, default="Aberto", index=True)
    tem_pedido = Column(Boolean, default=False)
    numero_pedido = Column(String)
    status_pedido = Column(String)
    revisao_documento_usada = Column(String)
    data_pedido = Column(Date)
    tem_material = Column(Boolean, default=False)
    tem_montagem = Column(Boolean, default=False)
    entrou_medicao_report = Column(Boolean, default=False)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ControleQuantitativo(Base):
    """Item quantitativo extraido do documento tecnico vinculado ao controle."""
    __tablename__ = "controle_quantitativos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    controle_id = Column(Integer, ForeignKey("controles_documento.id"), nullable=False, index=True)
    codigo_controle = Column(String, nullable=False, index=True)
    documento_origem = Column(String, nullable=False, index=True)
    item = Column(String)
    descricao = Column(Text)
    unidade = Column(String, nullable=False, index=True)
    quantidade = Column(Float, nullable=False)
    fonte_arquivo = Column(Text)
    evidencia = Column(Text)
    status_validacao = Column(String, default="Extraido automaticamente - revisar", index=True)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EventoRevisaoDocumento(Base):
    """Evento gerado quando uma revisao nova substitui revisao anterior."""
    __tablename__ = "eventos_revisao_documento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_evento_revisao = Column(String, nullable=False, unique=True, index=True)
    codigo_documento = Column(String, nullable=False, index=True)
    revisao_anterior = Column(String)
    revisao_nova = Column(String, nullable=False)
    data_deteccao = Column(DateTime, server_default=func.now(), index=True)
    controles_afetados = Column(Text)
    status_analise = Column(String, default="Pendente analise", index=True)
    analisado_por = Column(String)
    data_analise = Column(DateTime)
    impacto_quantitativo = Column(Boolean, default=False)
    impacto_material = Column(Boolean, default=False)
    impacto_montagem = Column(Boolean, default=False)
    impacto_medicao_report = Column(Boolean, default=False)
    impacto_informado = Column(String)
    acao_necessaria = Column(String)
    observacao_impacto = Column(Text)
    item_controlavel = Column(String)
    quantidade_anterior = Column(Float)
    quantidade_nova = Column(Float)
    diferenca_quantidade = Column(Float)
    unidade = Column(String)
    tipo_variacao = Column(String)
    acao_pedido = Column(String)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO PRODUÇÃO — cronograma Primavera (XER)
# ═══════════════════════════════════════════════════════════════════════════════
# Importado do XER. Painel executivo do cronograma: KPIs, curva-S, lookahead,
# disciplinas, atividades. Ponderação por DURAÇÃO (peso). Parametrizado para
# reutilização em outros contratos (não há regras fixas da RECAP).

class ProdProjeto(Base):
    """Snapshot de um cronograma XER importado (1 projeto = 1 import ativo)."""
    __tablename__ = "prod_projeto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proj_short_name = Column(String)
    data_date = Column(Date, index=True)        # last_recalc_date do XER
    plan_start = Column(Date)
    plan_end = Column(Date)
    origem_arquivo = Column(String)
    total_atividades = Column(Integer, default=0)
    importado_em = Column(DateTime, server_default=func.now())
    ativo = Column(Boolean, default=True, index=True)

    atividades = relationship("ProdAtividade", back_populates="projeto",
                              cascade="all, delete-orphan")
    wbs = relationship("ProdWbs", back_populates="projeto",
                       cascade="all, delete-orphan")


class ProdWbs(Base):
    """Nó da WBS do cronograma (hierarquia da obra)."""
    __tablename__ = "prod_wbs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    projeto_id = Column(Integer, ForeignKey("prod_projeto.id"), nullable=False, index=True)
    wbs_uid = Column(String, index=True)        # wbs_id do XER
    parent_uid = Column(String, index=True)
    short_name = Column(String)
    nome = Column(String)
    is_node = Column(Boolean, default=False)

    projeto = relationship("ProdProjeto", back_populates="wbs")


class ProdAtividade(Base):
    """Atividade (TASK) do cronograma com dados para o painel executivo."""
    __tablename__ = "prod_atividade"

    id = Column(Integer, primary_key=True, autoincrement=True)
    projeto_id = Column(Integer, ForeignKey("prod_projeto.id"), nullable=False, index=True)

    task_code = Column(String, index=True)
    nome = Column(String)
    wbs_uid = Column(String, index=True)
    wbs_nome = Column(String)
    disciplina = Column(String, index=True)
    fase = Column(String, index=True)
    area = Column(String)

    status = Column(String, index=True)         # concluida | em_andamento | nao_iniciada
    phys_pct = Column(Float, default=0.0)        # 0–100 (referência; NÃO usado no avanço)
    peso = Column(Float, default=0.0)            # unidades orçadas do PONDERADOR (peso físico)
    unid_realizada = Column(Float, default=0.0)  # unidades realizadas (act_reg_qty + act_ot_qty)
    unid_remaining = Column(Float, default=0.0)  # unidades restantes (remain_qty) → tendência

    target_start = Column(Date)
    target_end = Column(Date, index=True)
    act_start = Column(Date)
    act_end = Column(Date)

    total_float_hr = Column(Float)               # None quando ausente
    critica = Column(Boolean, default=False, index=True)
    is_marco = Column(Boolean, default=False, index=True)
    responsavel = Column(String)

    projeto = relationship("ProdProjeto", back_populates="atividades")
