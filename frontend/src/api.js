import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

// --- Semanas ---
export const getSemanas = () => api.get('/semanas/').then(r => r.data)
export const createSemana = (data) => api.post('/semanas/', data).then(r => r.data)
export const updateSemana = (codigo, data) => api.put(`/semanas/${encodeURIComponent(codigo)}`, data).then(r => r.data)
export const deleteSemana = (codigo) => api.delete(`/semanas/${encodeURIComponent(codigo)}`)
export const getSemana = (codigo) => api.get(`/semanas/${encodeURIComponent(codigo)}`).then(r => r.data)
export const getQcron = (semana) => api.get(`/semanas/${encodeURIComponent(semana)}/qcron`).then(r => r.data)
export const getQprog = (semana) => api.get(`/semanas/${encodeURIComponent(semana)}/qprog`).then(r => r.data)
export const getIndicadores = (semana) => api.get(`/semanas/${encodeURIComponent(semana)}/indicadores`).then(r => r.data)
export const fecharSemana = (codigo) => api.post(`/semanas/${encodeURIComponent(codigo)}/fechar`).then(r => r.data)
export const reabrirSemana = (codigo) => api.post(`/semanas/${encodeURIComponent(codigo)}/reabrir`).then(r => r.data)
export const updateProgramacao = (semana, id, data) =>
  api.patch(`/semanas/${encodeURIComponent(semana)}/programacoes/${id}`, data).then(r => r.data)
export const updateProgramacoesBulk = (semana, ids, data) =>
  api.patch(`/semanas/${encodeURIComponent(semana)}/programacoes`, { ids, data }).then(r => r.data)

// --- Tarefas ---
export const getTarefas = (params) => api.get('/tarefas/', { params }).then(r => r.data)

// --- Adiantamento ---
export const adiantarAtividade = (semana, tarefaId) =>
  api.post(`/semanas/${encodeURIComponent(semana)}/adiantar`, { tarefa_id: tarefaId }).then(r => r.data)
export const removerAdiantada = (semana, progId) =>
  api.delete(`/semanas/${encodeURIComponent(semana)}/programacoes/${progId}/adiantada`)

// --- Imports ---
export const getImports = () => api.get('/imports/').then(r => r.data)
export const clearImports = () => api.delete('/imports/').then(r => r.data)
export const importXlsx = (formData) =>
  api.post('/imports/xlsx', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
export const importXer = (formData) =>
  api.post('/imports/xer', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
export const importSemanas = (formData) =>
  api.post('/imports/semanas', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)

// --- Relatorio / Textos ---
export const getTextos = (semana) => api.get(`/relatorio/${encodeURIComponent(semana)}`).then(r => r.data)
export const saveTextos = (semana, data) => api.post(`/relatorio/${encodeURIComponent(semana)}`, data).then(r => r.data)

// --- Clima --- chamado direto do browser para contornar firewall corporativo
const DIAS_PT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']
export const getClima = () =>
  fetch(
    'https://api.open-meteo.com/v1/forecast' +
    '?latitude=-23.6678&longitude=-46.4614' +
    '&daily=weathercode,temperature_2m_max,temperature_2m_min' +
    '&timezone=America%2FSao_Paulo&forecast_days=7'
  )
  .then(r => r.json())
  .then(data => data.daily.time.map((d, i) => {
    const dt = new Date(d + 'T12:00:00')
    return {
      data: d,
      data_fmt: d.slice(8,10) + '/' + d.slice(5,7),
      dia_semana: DIAS_PT[dt.getDay()],
      weathercode: data.daily.weathercode[i],
      temp_max: data.daily.temperature_2m_max[i],
      temp_min: data.daily.temperature_2m_min[i],
    }
  }))
  .catch(() => [{ erro: true }])

// --- Painel de Avanço Físico ---
export const getPainel = (semana) => api.get(`/painel/${encodeURIComponent(semana)}`).then(r => r.data)
export const recalcularPainel = (semana) => api.post(`/painel/${encodeURIComponent(semana)}/recalcular`).then(r => r.data)
export const importarXerPainel = (semana, formData) =>
  api.post(`/painel/${encodeURIComponent(semana)}/importar`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)

// --- Sub-tarefas ---
export const getSubTarefas = (progId) => api.get(`/programacoes/${progId}/sub-tarefas`).then(r => r.data)
export const createSubTarefa = (progId, data) => api.post(`/programacoes/${progId}/sub-tarefas`, data).then(r => r.data)
export const updateSubTarefa = (progId, subId, data) => api.patch(`/programacoes/${progId}/sub-tarefas/${subId}`, data).then(r => r.data)
export const deleteSubTarefa = (progId, subId) => api.delete(`/programacoes/${progId}/sub-tarefas/${subId}`)

// --- EAP Financeira ---
// Upload da EAP é grande (1500+ itens, ~3-5s no backend) — timeout 5min
export const importarEap = (formData) =>
  api.post('/eap/importar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data)
export const getEapItens = (params) => api.get('/eap/itens', { params }).then(r => r.data)
export const getCurvaPrevista = () => api.get('/eap/curva-prevista').then(r => r.data)
export const getCurvaRealizada = () => api.get('/eap/curva-realizada').then(r => r.data)
export const getKpisEvm = (semana) => api.get(`/eap/kpis/${encodeURIComponent(semana)}`).then(r => r.data)
export const getEapLinks = (params) => api.get('/eap/links', { params }).then(r => r.data)
export const createEapLink = (data) => api.post('/eap/links', data).then(r => r.data)
export const deleteEapLink = (id) => api.delete(`/eap/links/${id}`)
export const autoMapearEap = (top_n = 3) => api.post('/eap/auto-mapear', null, { params: { top_n } }).then(r => r.data)
export const getBoletimMedicao = (ano, mes) => api.get(`/eap/medicao/${ano}/${mes}`).then(r => r.data)

// Ciclo de medição mensal
export const updateEapItem = (codigo, data) => api.patch(`/eap/itens/${encodeURIComponent(codigo)}`, data).then(r => r.data)
export const criarAtividadeManualEap = (data) => api.post('/eap/atividades-manuais', data).then(r => r.data)
export const removerAtividadeManualEap = (codigo) => api.delete(`/eap/atividades-manuais/${encodeURIComponent(codigo)}`)
export const getPrevisaoMensal = (ano, mes) => api.get(`/eap/previsao/${ano}/${mes}`).then(r => r.data)
export const lancarPrevisaoMensal = (ano, mes, data) => api.post(`/eap/previsao/${ano}/${mes}`, data).then(r => r.data)
export const puxarPrevisaoP6 = (ano, mes) => api.post(`/eap/previsao/${ano}/${mes}/puxar-p6`).then(r => r.data)
export const getAvancoSemana = (semanaCodigo) => api.get(`/eap/avanco/${encodeURIComponent(semanaCodigo)}`).then(r => r.data)
export const lancarAvancoSemana = (data) => api.post('/eap/avanco', data).then(r => r.data)
export const getMedicaoMes = (ano, mes) => api.get(`/eap/medicao-mes/${ano}/${mes}`).then(r => r.data)

// Ciclo de medição mensal
export const listarCiclos = () => api.get('/eap/ciclos').then(r => r.data)
export const abrirCiclo = (ano, mes) => api.post(`/eap/ciclos?ano=${ano}&mes=${mes}`).then(r => r.data)
export const getCicloMes = (ano, mes) => api.get(`/eap/ciclos/mes/${ano}/${mes}`).then(r => r.data)
export const salvarPrevia = (cicloId, itens) => api.put(`/eap/ciclos/${cicloId}/salvar`, { itens }).then(r => r.data)
export const fecharBM = (cicloId, fechadoPor) => api.post(`/eap/ciclos/${cicloId}/fechar`, null, { params: { fechado_por: fechadoPor } }).then(r => r.data)
export const getPreviaPdfUrl = (cicloId) => `${api.defaults.baseURL}/eap/ciclos/${cicloId}/previa-pdf`

// Fase 2 — Módulo financeiro: resumo por fase, curva BM, histórico BM
export const getResumoFases = (ano, mes) => api.get(`/eap/ciclos/resumo-fases/${ano}/${mes}`).then(r => r.data)
export const getCurvaRealizadaBM = () => api.get('/eap/curva-realizada-bm').then(r => r.data)
export const getHistoricoBM = () => api.get('/eap/ciclos/historico-bm').then(r => r.data)

// ── Documentos de Engenharia (Fase 3) ─────────────────────────────────
export const getDocumentos = (params) => api.get('/documentos', { params }).then(r => r.data)
export const criarDocumento = (data) => api.post('/documentos', data).then(r => r.data)
export const atualizarDocumento = (id, data) => api.put(`/documentos/${id}`, data).then(r => r.data)
export const alterarStatusDocumento = (id, novoStatus, extras = {}) =>
  api.patch(`/documentos/${id}/status`, null, { params: { novo_status: novoStatus, ...extras } }).then(r => r.data)
export const deletarDocumento = (id) => api.delete(`/documentos/${id}`)
export const getProgresso211 = () => api.get('/documentos/progresso-211').then(r => r.data)
export const importarDocumentosExcel = (formData) =>
  api.post('/documentos/importar-excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)

// --- Exportações ---
export const exportBmExcel = (ano, mes, usuario = 'usuario') =>
  api.get(`/export/bm/${ano}/${mes}/excel`, {
    params: { usuario },
    responseType: 'blob',
  })

// ── Relatório Fotográfico ─────────────────────────────────────────────
export const getFotosMedicao = (ano, mes, params) =>
  api.get(`/medicao/${ano}/${mes}/fotos`, { params }).then(r => r.data)
export const uploadFotoMedicao = (ano, mes, formData) =>
  api.post(`/medicao/${ano}/${mes}/fotos`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
export const atualizarLegendaFoto = (ano, mes, fotoId, legenda) =>
  api.patch(`/medicao/${ano}/${mes}/fotos/${fotoId}`, { legenda }).then(r => r.data)
export const deletarFotoMedicao = (ano, mes, fotoId) =>
  api.delete(`/medicao/${ano}/${mes}/fotos/${fotoId}`)
export const fotoUrl = (foto) => `/api/medicao/${foto.ano}/${foto.mes}/fotos/${foto.id}/arquivo`

// ── Adiantar atividade (Previsão Mensal) ──────────────────────────────
export const adiantarPrevisaoMensal = (ano, mes, data) =>
  api.post(`/eap/previsao/${ano}/${mes}/adiantar`, data).then(r => r.data)
export const removerAdiantadaPrevisao = (ano, mes, eapCodigo) =>
  api.delete(`/eap/previsao/${ano}/${mes}/adiantada/${encodeURIComponent(eapCodigo)}`)

// ── Pendências do mês anterior (legado) ────────────────────────────
export const getPendenciasMes = (ano, mes) =>
  api.get(`/eap/previsao/${ano}/${mes}/pendencias`).then(r => r.data)

// ═══════════════════════════════════════════════════════════════════
// MÓDULO BM — Arquitetura Refatorada (/api/bm)
// ═══════════════════════════════════════════════════════════════════

// ── Abertura e ciclo de vida do BM ────────────────────────────────
export const bmAbrir = (ano, mes, criadoPor, observacao) =>
  api.post('/bm/abrir', { ano, mes, criado_por: criadoPor, observacao }).then(r => r.data)

export const bmListar = (status) =>
  api.get('/bm/lista', { params: status ? { status } : {} }).then(r => r.data)

export const bmGet = (cicloId) =>
  api.get(`/bm/${cicloId}`).then(r => r.data)

export const bmGetPorMes = (ano, mes) =>
  api.get(`/bm/mes/${ano}/${mes}`).then(r => r.data)

// ── Lançamentos ───────────────────────────────────────────────────
// lancamentos: [{eap_codigo, pct_acumulado (0-1), observacao}]
export const bmSalvarLancamentos = (cicloId, lancamentos, salvoPor) =>
  api.put(`/bm/${cicloId}/lancamentos`, {
    lancamentos,
    salvo_por: salvoPor,
  }).then(r => r.data)

// ── Transições de status ──────────────────────────────────────────
// novoStatus: 'em_analise' | 'pre_aprovada' | 'em_previa' (retorno)
export const bmTransicionarStatus = (cicloId, novoStatus, usuario, observacao) =>
  api.post(`/bm/${cicloId}/status`, {
    novo_status: novoStatus,
    usuario,
    observacao,
  }).then(r => r.data)

// ── Fechamento do BM ──────────────────────────────────────────────
export const bmFechar = (cicloId, fechadoPor, observacao) =>
  api.post(`/bm/${cicloId}/fechar`, {
    fechado_por: fechadoPor,
    observacao,
  }).then(r => r.data)

// ── Pendências ────────────────────────────────────────────────────
export const bmGetPendencias = (cicloId) =>
  api.get(`/bm/${cicloId}/pendencias`).then(r => r.data)

export const bmGetTodasPendencias = () =>
  api.get('/bm/pendencias/todas').then(r => r.data)

// pctRedistribuir: fração do gap a redistribuir (0.0-1.0, onde 1.0 = redistribuir tudo)
export const bmRedistribuirPendencia = (pendenciaId, destinoAno, destinoMes, pctRedistribuir, redistribuidoPor, observacao) =>
  api.post(`/bm/pendencias/${pendenciaId}/redistribuir`, {
    destino_ano: destinoAno,
    destino_mes: destinoMes,
    pct_redistribuir: pctRedistribuir,
    redistribuido_por: redistribuidoPor,
    observacao,
  }).then(r => r.data)

// ── Dashboard (SOMENTE BMs fechados) ─────────────────────────────
export const bmDashboardCurvaS = () =>
  api.get('/bm/dashboard/curva-s').then(r => r.data)

export const bmDashboardKpis = () =>
  api.get('/bm/dashboard/kpis').then(r => r.data)

export const bmDashboardHistorico = () =>
  api.get('/bm/dashboard/historico').then(r => r.data)

// ── Audit trail ───────────────────────────────────────────────────
export const bmGetVersoes = (cicloId) =>
  api.get(`/bm/${cicloId}/versoes`).then(r => r.data)

export const bmGetSnapshotPrevisao = (cicloId) =>
  api.get(`/bm/${cicloId}/snapshot-previsao`).then(r => r.data)

// ── Consolidação ─────────────────────────────────────────────────
export const bmConsolidar = (cicloId, consolidadoPor, observacao) =>
  api.post(`/bm/${cicloId}/consolidar`, {
    consolidado_por: consolidadoPor,
    observacao,
  }).then(r => r.data)

// ── Previsão mensal (status lifecycle) ───────────────────────────
export const bmStatusPrevisao = (ano, mes) =>
  api.get(`/bm/previsao/status/${ano}/${mes}`).then(r => r.data)

export const bmFecharPrevisao = (ano, mes, fechadoPor) =>
  api.post('/bm/previsao/fechar', { ano, mes, fechado_por: fechadoPor }).then(r => r.data)

export const bmReabrirPrevisao = (ano, mes, reabertoP) =>
  api.post('/bm/previsao/reabrir', { ano, mes, reaberto_por: reabertoP }).then(r => r.data)

// ── Log de auditoria ─────────────────────────────────────────────
export const bmGetLog = (cicloId) =>
  api.get(`/bm/${cicloId}/log`).then(r => r.data)

// ── PDF ───────────────────────────────────────────────────────────
export const bmPdfUrl = (cicloId) => `/api/bm/${cicloId}/pdf`
export const bmAnexoResumoPdfUrl = (cicloId) => `/api/bm/${cicloId}/anexo-resumo-pdf`

// ── Migração de dados legados ─────────────────────────────────────
export const bmMigrarLegado = () =>
  api.post('/bm/migrar-legado').then(r => r.data)

// ── Fase 2A — Integração LD / SIGEM (Módulo 1) ────────────────────
export const uploadLd = (formData) =>
  api.post('/ld/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data)
export const getLdDocumentos = (params) => api.get('/ld/documentos', { params }).then(r => r.data)
export const getLdHistorico = (documentoId) => api.get(`/ld/documentos/${documentoId}/historico`).then(r => r.data)
export const getLdFiltros = () => api.get('/ld/filtros').then(r => r.data)

// ── Fase 2A — Motor de Medição de Engenharia (Módulo 2) ───────────
export const getMedicaoEngDashboard = () => api.get('/medicao-eng/dashboard').then(r => r.data)
export const getMedicaoEngPorDisciplina = () => api.get('/medicao-eng/por-disciplina').then(r => r.data)
export const getMedicaoEngEvolucao = (semanas = 12) => api.get('/medicao-eng/evolucao', { params: { semanas } }).then(r => r.data)
export const getMedicaoEngConfig = () => api.get('/medicao-eng/config').then(r => r.data)

export const uploadSigem = (formData) =>
  api.post('/sigem/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data)
export const getSigemConciliacao = () => api.get('/sigem/conciliacao').then(r => r.data)
export const getSigemDivergentes = () => api.get('/sigem/documentos-divergentes').then(r => r.data)
export const getSigemDocumentos = (params) => api.get('/sigem/documentos', { params }).then(r => r.data)
export const getEventosRevisao = (params) => api.get('/revisoes/eventos', { params }).then(r => r.data)
export const atualizarAnaliseRevisao = (eventoId, data) =>
  api.patch(`/revisoes/eventos/${eventoId}`, data).then(r => r.data)

// ── Fase 2A — Matriz de Critérios (Módulo 3) ──────────────────────
export const getCriterios = (params) => api.get('/criterios', { params }).then(r => r.data)
export const getCriterioTipos = () => api.get('/criterios/tipos').then(r => r.data)
export const salvarCriterio = (data) => api.post('/criterios', data).then(r => r.data)
export const atualizarCriterio = (codigoEap, data) => api.put(`/criterios/${encodeURIComponent(codigoEap)}`, data).then(r => r.data)
export const deletarCriterio = (codigoEap) => api.delete(`/criterios/${encodeURIComponent(codigoEap)}`)
export const seedCriterios = (tipoDefault) => api.post('/criterios/seed', null, { params: { tipo_default: tipoDefault } }).then(r => r.data)
export const avaliarCriterio = (codigoEap) => api.get(`/criterios/${encodeURIComponent(codigoEap)}/avaliar`).then(r => r.data)

// ── Módulo Produção (cronograma XER) ──────────────────────────────
export const getProducaoStatus = () => api.get('/producao/status').then(r => r.data)
export const getProducaoDashboard = () => api.get('/producao/dashboard').then(r => r.data)
export const importProducaoXer = (formData) =>
  api.post('/producao/import-xer', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data)

export const importarEconomico = (formData) =>
  api.post('/economico/importar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data)
export const listarEconomicoImportacoes = () => api.get('/economico/importacoes').then(r => r.data)
export const getEconomicoAuditoria = (importacaoId) =>
  api.get('/economico/auditoria', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoDashboard = (importacaoId) =>
  api.get('/economico/dashboard', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoReceitas = (importacaoId) =>
  api.get('/economico/receitas', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoForecast = (importacaoId) =>
  api.get('/economico/forecast', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoForecastOperacionalVersoes = () =>
  api.get('/economico/forecast-operacional/versoes').then(r => r.data)
export const criarEconomicoForecastOperacionalVersao = (data) =>
  api.post('/economico/forecast-operacional/versoes', data).then(r => r.data)
export const getEconomicoForecastOperacionalVersao = (versaoId) =>
  api.get(`/economico/forecast-operacional/versoes/${versaoId}`).then(r => r.data)
export const clonarEconomicoForecastOperacionalVersao = (versaoId, data) =>
  api.post(`/economico/forecast-operacional/versoes/${versaoId}/clonar`, data).then(r => r.data)
export const ajustarEconomicoForecastOperacionalCategoria = (versaoId, data) =>
  api.post(`/economico/forecast-operacional/versoes/${versaoId}/ajustes`, data).then(r => r.data)
export const compararEconomicoForecastOperacionalVersoes = (baseId, novoId) =>
  api.get('/economico/forecast-operacional/comparar', { params: { base_id: baseId, novo_id: novoId } }).then(r => r.data)
export const getEconomicoResultado = (importacaoId) =>
  api.get('/economico/resultado', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoHistorico = () => api.get('/economico/historico').then(r => r.data)
export const getEconomicoCustos = (importacaoId) =>
  api.get('/economico/custos', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoDesvios = (importacaoId) =>
  api.get('/economico/desvios', { params: importacaoId ? { importacao_id: importacaoId } : {} }).then(r => r.data)
export const getEconomicoLancamentos = (params = {}) =>
  api.get('/economico/lancamentos', { params }).then(r => r.data)
export const getEconomicoCentroAnalise = (params = {}) =>
  api.get('/economico/centro-analise', { params }).then(r => r.data)

export const getPerformanceAuditoria = (recalcular = false) =>
  api.get('/performance/auditoria', { params: recalcular ? { recalcular: true } : {} }).then(r => r.data)

export default api
