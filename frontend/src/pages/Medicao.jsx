import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  bmGetPorMes, bmAbrir, bmSalvarLancamentos, bmFechar, bmTransicionarStatus, bmPdfUrl, bmAnexoResumoPdfUrl,
  bmConsolidar, bmStatusPrevisao, bmFecharPrevisao, bmReabrirPrevisao,
  getFotosMedicao, uploadFotoMedicao, atualizarLegendaFoto, deletarFotoMedicao, fotoUrl,
} from '../api'
import PctInput from '../components/PctInput'

// Status do novo sistema BM
const STATUS_LABEL = {
  em_previa:     { label: 'PRÉVIA',        cor: '#2563eb' },
  em_analise:    { label: 'EM ANÁLISE',    cor: '#d97706' },
  pre_aprovada:  { label: 'PRÉ-APROVADA',  cor: '#7c3aed' },
  fechada:       { label: 'BM FECHADO',    cor: '#16a34a' },
  consolidada:   { label: 'CONSOLIDADO',   cor: '#064e3b' },
}

const PREV_LABEL = {
  sem_previsao: { label: 'SEM PREVISÃO',      cor: '#9ca3af' },
  em_edicao:    { label: 'PREV. EM EDIÇÃO',   cor: '#0891b2' },
  fechada:      { label: 'PREV. FECHADA',     cor: '#7c3aed' },
  convertida:   { label: 'PREV. CONVERTIDA',  cor: '#16a34a' },
}
const STATUS_EDITAVEL = new Set(['em_previa', 'em_analise', 'pre_aprovada'])

const MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

// Detecta itens "Administração Local" e o Serviço vinculado.
// Padrão da EAP: entrega N tem N.1 (Serviços) e N.2 (Adm. Local).
// Retorna { adminCodigo: servicoCodigo }.
function detectarAdminLink(itens) {
  const codigos = new Set(itens.map(i => i.codigo))
  const link = {}
  for (const it of itens) {
    if (it.nivel !== 2) continue
    if (!/administra[çc][ãa]o\s+local/i.test(it.descricao || '')) continue
    const servico = `${it.codigo.split('.')[0]}.1`
    if (codigos.has(servico)) link[it.codigo] = servico
  }
  return link
}

// Propaga % acumulado dos pais a partir das folhas (média ponderada por R$).
// `adminLink` faz a Administração Local sem edição herdar o % do Serviço.
function propagarPais(itens, edits, adminLink = {}) {
  const vals = {}
  for (const it of itens) {
    if (it.is_folha) vals[it.codigo] = edits[it.codigo] !== undefined  edits[it.codigo] : it.pct_acumulado
  }
  const sorted = [...itens].sort((a, b) => b.codigo.length - a.codigo.length || a.codigo.localeCompare(b.codigo))
  for (const it of sorted) {
    if (it.is_folha) continue
    const filhos = itens.filter(f => f.parent_codigo === it.codigo)
    if (!filhos.length || !it.valor) continue
    const soma = filhos.reduce((s, f) => s + (f.valor * (vals[f.codigo]  0)), 0)
    vals[it.codigo] = soma / it.valor
  }
  // Administração Local sem edição manual → herda o % do Serviço vinculado
  for (const [adminCod, servicoCod] of Object.entries(adminLink)) {
    if (edits[adminCod] === undefined) {
      vals[adminCod] = vals[servicoCod]  0
    }
  }
  // Re-propaga os pais nível-1 (a Adm. Local é filha direta da entrega)
  for (const it of sorted) {
    if (it.nivel !== 1 || it.is_folha || !it.valor) continue
    const filhos = itens.filter(f => f.parent_codigo === it.codigo)
    if (!filhos.length) continue
    const soma = filhos.reduce((s, f) => s + (f.valor * (vals[f.codigo]  0)), 0)
    vals[it.codigo] = soma / it.valor
  }
  return vals
}

function fmt(v, digits = 2) {
  if (v === null || v === undefined) return '—'
  return (v * 100).toFixed(digits) + '%'
}

function fmtR(v) {
  if (v === null || v === undefined) return '—'
  return 'R$ ' + v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function Medicao() {
  const params = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const somenteVisualizacao = new URLSearchParams(location.search).get('view') === '1'
  const hoje = new Date()
  const [ano, setAno] = useState(params.ano  parseInt(params.ano) : hoje.getFullYear())
  const [mes, setMes] = useState(params.mes  parseInt(params.mes) : hoje.getMonth() + 1)

  const [dados, setDados] = useState(null)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)
  const [bmNaoExiste, setBmNaoExiste] = useState(false)
  const [abrindo, setAbrindo] = useState(false)
  const [edits, setEdits] = useState({})
  const [salvando, setSalvando] = useState(false)
  const [confirmFechar, setConfirmFechar] = useState(false)
  const [fechadoPor, setFechadoPor] = useState('')
  const [confirmConsolidar, setConfirmConsolidar] = useState(false)
  const [consolidadoPor, setConsolidadoPor] = useState('')
  const [prevInfo, setPrevInfo] = useState(null)
  const [colapsados, setColapsados] = useState({})
  const [showAll, setShowAll] = useState(false)   // false = só itens do mês
  const [galeria, setGaleria] = useState(null)    // { codigo, descricao } ou null

  const carregar = useCallback(async (a, m) => {
    setLoading(true)
    setErro(null)
    setBmNaoExiste(false)
    setEdits({})
    try {
      const [d, prev] = await Promise.all([
        bmGetPorMes(a, m),
        bmStatusPrevisao(a, m),
      ])
      setDados(d)
      setPrevInfo(prev)
    } catch (e) {
      if (e?.response?.status === 404) {
        // GET retorna 404 quando BM não foi aberto ainda — estado normal,
        // não é erro. Usa POST /bm/abrir para criar.
        setBmNaoExiste(true)
        setDados(null)
        // Ainda carrega status da previsão para mostrar se pode abrir
        try {
          const prev = await bmStatusPrevisao(a, m)
          setPrevInfo(prev)
        } catch (_) { /* previsão não carregada */ }
      } else {
        setErro('Erro ao carregar medição: ' + (e?.response?.data?.detail || e.message))
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    carregar(ano, mes)
    navigate(`/medicao/${ano}/${mes}${somenteVisualizacao  '?view=1' : ''}`, { replace: true })
  }, [ano, mes, carregar, navigate, somenteVisualizacao])

  function navMes(delta) {
    let nm = mes + delta
    let na = ano
    if (nm < 1) { nm = 12; na-- }
    if (nm > 12) { nm = 1; na++ }
    setAno(na)
    setMes(nm)
  }

  const adminLink = dados  detectarAdminLink(dados.itens) : {}
  const vals = dados  propagarPais(dados.itens, edits, adminLink) : {}
  const status = dados?.ciclo?.status || 'em_previa'
  const fechado = !STATUS_EDITAVEL.has(status)

  function handleEdit(codigo, inputVal) {
    if (somenteVisualizacao) return
    const num = parseFloat(inputVal)
    if (isNaN(num)) {
      setEdits(prev => ({ ...prev, [codigo]: 0 }))
      return
    }
    // Clamp financeiro: [0, 100] na escala do input → [0.0, 1.0] internamente.
    // PctInput já faz o clamp visual; aqui garantimos consistência no estado React.
    const clamped = Math.min(100, Math.max(0, num))
    setEdits(prev => ({ ...prev, [codigo]: clamped / 100 }))
  }

  function _buildLancamentos() {
    if (!dados) return []
    return dados.itens
      .filter(it => it.is_folha)
      .map(it => ({
        eap_codigo: it.codigo,
        pct_acumulado: vals[it.codigo] !== undefined  vals[it.codigo] : it.pct_acumulado,
        observacao: null,
      }))
  }

  async function handleSalvar() {
    if (somenteVisualizacao) return
    if (!dados) return
    setSalvando(true)
    try {
      const d = await bmSalvarLancamentos(dados.ciclo.id, _buildLancamentos(), 'usuario')
      setDados(d)
      setEdits({})
    } catch (e) {
      alert('Erro ao salvar: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  async function handleFechar() {
    if (somenteVisualizacao) return
    if (!dados) return
    setSalvando(true)
    try {
      await bmSalvarLancamentos(dados.ciclo.id, _buildLancamentos(), fechadoPor || null)
      const d = await bmFechar(dados.ciclo.id, fechadoPor || null)
      setDados(d)
      setEdits({})
      setConfirmFechar(false)
    } catch (e) {
      alert('Erro ao fechar BM: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  async function handleAvancarStatus(novoStatus) {
    if (somenteVisualizacao) return
    if (!dados) return
    setSalvando(true)
    try {
      await bmTransicionarStatus(dados.ciclo.id, novoStatus, 'usuario')
      await carregar(ano, mes)
    } catch (e) {
      alert('Erro: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  async function handleAbrirBm() {
    if (somenteVisualizacao) return
    setAbrindo(true)
    try {
      await bmAbrir(ano, mes, 'usuario', null)
      await carregar(ano, mes)
    } catch (e) {
      alert('Erro ao abrir BM: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setAbrindo(false)
    }
  }

  async function handleFecharPrevisao() {
    if (somenteVisualizacao) return
    setSalvando(true)
    try {
      await bmFecharPrevisao(ano, mes, 'usuario')
      await carregar(ano, mes)
    } catch (e) {
      alert('Erro ao fechar previsão: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  async function handleReabrirPrevisao() {
    if (somenteVisualizacao) return
    setSalvando(true)
    try {
      await bmReabrirPrevisao(ano, mes, 'usuario')
      await carregar(ano, mes)
    } catch (e) {
      alert('Erro ao reabrir previsão: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  async function handleConsolidar() {
    if (somenteVisualizacao) return
    if (!dados) return
    setSalvando(true)
    try {
      await bmConsolidar(dados.ciclo.id, consolidadoPor || 'usuario', null)
      await carregar(ano, mes)
      setConfirmConsolidar(false)
    } catch (e) {
      alert('Erro ao consolidar BM: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  // Build display items with computed vals
  function buildItens() {
    if (!dados) return []
    return dados.itens.map(it => {
      const pct_acum = vals[it.codigo]  it.pct_acumulado
      const pct_periodo = Math.max(0, pct_acum - it.pct_acum_anterior)
      const valor_previsto = it.valor_previsto  ((it.pct_previsto || 0) * (it.valor || 0))
      return {
        ...it,
        pct_acumulado: pct_acum,
        pct_periodo,
        valor_previsto,
        valor_periodo: pct_periodo * it.valor,
        valor_acumulado: pct_acum * it.valor,
      }
    })
  }

  const itensDisplay = buildItens()

  // Filtro do mês: só itens que têm distribuição planejada no mês OU já têm medição OU são adiantadas
  const itensFiltrados = showAll
     itensDisplay
    : itensDisplay.filter(it =>
        it.valor_dist_mes > 0 ||
        it.pct_acumulado > 0 ||
        it.pct_previsto > 0 ||        // adiantada: tem previsão mas sem dist_mensal
        (edits[it.codigo] !== undefined)
      )

  // Group nivel-1 items for totals
  const nivel1 = itensFiltrados.filter(it => it.nivel === 1)
  const codigosResumo = useMemo(
    () => new Set(itensFiltrados.filter(it => !it.is_folha).map(it => it.codigo)),
    [itensFiltrados]
  )

  function isVisible(it) {
    if (it.nivel === 1) return true
    const parts = it.codigo.split('.')
    for (let i = 1; i < parts.length; i++) {
      const anc = parts.slice(0, i).join('.')
      if (colapsados[anc]) return false
    }
    return true
  }

  function toggleColapso(codigo) {
    setColapsados(prev => ({ ...prev, [codigo]: !prev[codigo] }))
  }

  const bac = dados?.bac || 0
  const totalValorPrevisto = dados?.total_valor_previsto  nivel1.reduce((s, it) => s + (it.valor_previsto || 0), 0)
  const totalPctPrevisto = dados?.total_pct_previsto  (bac > 0  totalValorPrevisto / bac : 0)
  const totalValorMedido = dados?.total_valor_medido  dados?.total_valor_periodo  nivel1.reduce((s, it) => s + it.valor_periodo, 0)
  const totalPctMedido = dados?.total_pct_medido  dados?.total_pct_periodo  (bac > 0  totalValorMedido / bac : 0)
  const totalValorAcum = dados?.total_valor_acum  nivel1.reduce((s, it) => s + it.valor_acumulado, 0)
  const totalPctAcum = dados?.total_pct_acum  (bac > 0  totalValorAcum / bac : 0)
  const desvioValorPeriodo = dados?.desvio_valor_periodo  (totalValorMedido - totalValorPrevisto)
  const desvioPctPeriodo = dados?.desvio_pct_periodo  (totalPctMedido - totalPctPrevisto)
  const desvioTexto = Math.abs(desvioValorPeriodo) < 0.01
     'em linha com o previsto'
    : desvioValorPeriodo < 0
       'abaixo do previsto'
      : 'acima do previsto'
  const desvioCor = desvioValorPeriodo < 0  '#B91C1C' : '#15803D'

  const cardStyle = {
    background: '#fff',
    borderRadius: 12,
    border: '0.5px solid #E0E0DC',
    padding: '16px 20px',
    marginBottom: 16,
  }

  return (
    <div style={{ background: '#F2F2F0', minHeight: '100vh', padding: '24px 28px' }}>
      {/* Cabeçalho */}
      <div style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <button onClick={() => navMes(-1)} style={navBtnStyle}>◀</button>
        <div style={{ textAlign: 'center', minWidth: 180 }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#063057' }}>
            {MESES_PT[mes]} / {ano}
          </div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>Boletim de Medição</div>
        </div>
        <button onClick={() => navMes(1)} style={navBtnStyle}>▶</button>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {dados?.ciclo?.numero_bm && (
            <span style={{ fontSize: 12, color: '#888' }}>{dados.ciclo.numero_bm}</span>
          )}
          {prevInfo && (() => {
            const p = PREV_LABEL[prevInfo.status] || { label: prevInfo.status, cor: '#9ca3af' }
            return (
              <span title={`Previsão: ${prevInfo.status} (${prevInfo.total} itens)`}
                style={{ background: p.cor + '22', color: p.cor, border: `1px solid ${p.cor}55`,
                  borderRadius: 20, padding: '3px 12px', fontSize: 11, fontWeight: 600 }}>
                {p.label}
              </span>
            )
          })()}
          {(() => {
            const s = STATUS_LABEL[status] || { label: status, cor: '#888' }
            return (
              <span style={{ background: s.cor, color: '#fff', borderRadius: 20, padding: '4px 14px', fontSize: 13, fontWeight: 600 }}>
                {s.label}
              </span>
            )
          })()}
          {somenteVisualizacao && (
            <span style={{ background: '#eef2ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: 20, padding: '4px 14px', fontSize: 12, fontWeight: 600 }}>
              SOMENTE VISUALIZAÇÃO
            </span>
          )}
        </div>
      </div>

      {erro && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 8, padding: '12px 16px', color: '#b91c1c', marginBottom: 16 }}>
          {erro}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>Carregando...</div>
      )}

      {/* Estado: BM ainda não foi aberto para este mês */}
      {bmNaoExiste && !loading && (
        <div style={{ ...cardStyle, textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#063057', marginBottom: 8 }}>
            Nenhum BM aberto para {MESES_PT[mes]}/{ano}
          </div>
          <div style={{ fontSize: 13, color: '#888', marginBottom: 20 }}>
            {prevInfo?.pode_abrir_bm === false
               `A previsão ainda está em edição (${prevInfo.total} item(ns)). Feche a previsão antes de abrir o BM.`
              : prevInfo?.status === 'sem_previsao'
                 'Nenhuma previsão lançada para este mês. Lance e feche a previsão antes de abrir o BM.'
                : 'Clique em "Abrir BM" para iniciar o ciclo de medição deste mês.'}
          </div>
          {!somenteVisualizacao && prevInfo?.pode_abrir_bm !== false && prevInfo?.status !== 'sem_previsao' && (
            <button
              onClick={handleAbrirBm}
              disabled={abrindo}
              style={btnStyle('#063057')}
            >
              {abrindo  'Abrindo...' : '+ Abrir BM'}
            </button>
          )}
        </div>
      )}

      {dados && !loading && (
        <>
          {/* Barra de resumo */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
            <ResumoCard label="BAC Total" valor={fmtR(bac)} cor="#063057" detalhe="total do contrato" />
            <ResumoCard label="Previsto no Período" valor={fmtR(totalValorPrevisto)} cor="#7C3AED" detalhe={fmt(totalPctPrevisto)} />
            <ResumoCard label="Medido no Período" valor={fmtR(totalValorMedido)} cor="#185FA5" detalhe={fmt(totalPctMedido)} />
            <ResumoCard label="Desvio do Período" valor={fmtR(desvioValorPeriodo)} cor={desvioCor} detalhe={`${fmt(desvioPctPeriodo)} - ${desvioTexto}`} />
            <ResumoCard label="Acumulado Atual" valor={fmtR(totalValorAcum)} cor="#16a34a" detalhe={fmt(totalPctAcum)} />
          </div>

          {/* Tabela */}
          <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
            {/* Barra de filtro */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 14px', borderBottom: '1px solid #e5e7eb', background: '#f8fafc' }}>
              <span style={{ fontSize: 11, color: '#6b7280' }}>
                {showAll
                   `${itensDisplay.length} itens (todos)`
                  : `${itensFiltrados.length} itens do mês  ·  ${itensDisplay.length - itensFiltrados.length} ocultados`
                }
              </span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  onClick={() => {
                    const resumos = itensFiltrados.filter(it => !it.is_folha)
                    const algumAberto = resumos.some(it => !colapsados[it.codigo])
                    const novo = {}
                    resumos.forEach(it => { novo[it.codigo] = algumAberto })
                    setColapsados(novo)
                  }}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, cursor: 'pointer', background: 'white', color: '#374151', border: '1px solid #d1d5db' }}
                >
                  ⊞ Expandir / Recolher
                </button>
                <button
                  onClick={() => setShowAll(v => !v)}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 5, cursor: 'pointer',
                    background: showAll  '#1d4ed8' : 'white',
                    color: showAll  'white' : '#374151',
                    border: '1px solid #d1d5db', fontWeight: showAll  600 : 400,
                  }}
                >
                  {showAll  '✓ Mostrar todos' : 'Mostrar todos'}
                </button>
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#063057', color: '#fff' }}>
                    <th style={thStyle}>Código</th>
                    <th style={{ ...thStyle, textAlign: 'left', minWidth: 200 }}>Descrição</th>
                    <th style={thStyle}>% Previsto</th>
                    <th style={thStyle}>R$ Previsto</th>
                    <th style={thStyle}>Acum. Anterior</th>
                    <th style={thStyle}>% Medido</th>
                    <th style={thStyle}>R$ Medido</th>
                    <th style={thStyle}>Acum. Atual</th>
                    <th style={thStyle} title="Valor que ainda resta medir do item">Saldo</th>
                    <th style={{ ...thStyle, width: 36 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {itensFiltrados.map((it, idx) => {
                    if (!isVisible(it)) return null
                    const isN1 = it.nivel === 1
                    const isPai = !it.is_folha
                    const isColapso = colapsados[it.codigo]
                    const indentPx = (it.nivel - 1) * 14

                    // Esquema de cores progressivo igual ao PDF (TabelaQprog)
                    const WBS_BG  = ['#063057','#0A4778','#1260A0','#1A79C8','#2E86C1','#5DADE2']
                    const WBS_FW  = [700, 600, 600, 500, 500, 400]
                    const paiBg   = WBS_BG[Math.min(it.nivel - 1, WBS_BG.length - 1)]
                    const paiFw   = WBS_FW[Math.min(it.nivel - 1, WBS_FW.length - 1)]

                    const rowBg  = isPai  paiBg : (idx % 2 === 0  '#fff' : '#f8f8f7')
                    const rowClr = isPai  '#fff' : '#1a1a1a'
                    const rowFw  = isPai  paiFw : 400

                    const periodo = it.pct_periodo
                    const previsto = it.pct_previsto
                    let periodoColor = isPai  '#c8dff5' : '#555'
                    if (!isPai && periodo > 0) {
                      periodoColor = periodo >= previsto  '#16a34a' : '#d97706'
                    }

                    // Vínculo Administração Local → Serviços
                    const vinc = it.is_folha  (adminLink[it.codigo] || null) : null
                    const isAdmin = !!vinc
                    const adminAuto = isAdmin && edits[it.codigo] === undefined
                    // Saldo a medir e sinais de alerta
                    const saldoR = (it.valor || 0) * (1 - it.pct_acumulado)
                    const excedeu = it.pct_acumulado > 1.0001
                    const regrediu = it.is_folha && it.pct_acumulado < it.pct_acum_anterior - 0.0001

                    return (
                      <tr key={it.codigo} style={{ background: rowBg, color: rowClr, fontWeight: rowFw }}>
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            {isPai && codigosResumo.has(it.codigo) && (
                              <button
                                onClick={() => toggleColapso(it.codigo)}
                                style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 11, padding: '0 2px' }}
                              >
                                {isColapso  '▸' : '▾'}
                              </button>
                            )}
                            <span style={{ fontFamily: isPai  'inherit' : 'monospace', fontSize: isPai  12 : 11 }}>
                              {it.codigo}
                            </span>
                          </span>
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'left', paddingLeft: indentPx + 8, fontStyle: it.nivel >= 4 && isPai  'italic' : 'normal' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
                            {it.adiantada && it.is_folha && (
                              <span title="Atividade adiantada de outro mês" style={{
                                background: '#F3E8FF', color: '#6D28D9',
                                border: '1px solid #DDD6FE', borderRadius: 3,
                                fontSize: 9, padding: '1px 5px', whiteSpace: 'nowrap', flexShrink: 0,
                              }}>⚡ adiantada</span>
                            )}
                            {it.descricao}
                            {isAdmin && (
                              <span title={`Acompanha automaticamente o Serviço ${vinc}`} style={{
                                background: '#DBEAFE', color: '#1E40AF',
                                border: '1px solid #BFDBFE', borderRadius: 3,
                                fontSize: 9, padding: '1px 5px', whiteSpace: 'nowrap', flexShrink: 0, fontWeight: 600,
                              }}>↔ vinc. {vinc}</span>
                            )}
                          </span>
                        </td>
                        <td style={{ ...tdStyle, color: periodoColor }}>{fmt(previsto)}</td>
                        <td style={{ ...tdStyle, color: isPai  '#c8dff5' : periodoColor }}>
                          {fmtR(it.valor_previsto)}
                        </td>
                        <td style={{ ...tdStyle, color: isPai  '#c8dff5' : undefined }}>{fmt(it.pct_acum_anterior)}</td>
                        <td style={{ ...tdStyle, color: isPai  '#fff' : periodoColor, fontWeight: periodo > 0  600 : 400 }}>
                          {fmt(periodo)}
                        </td>
                        <td style={{ ...tdStyle, color: isPai  '#c8dff5' : periodoColor }}>
                          {fmtR(it.valor_periodo)}
                        </td>
                        <td style={{ ...tdStyle, color: isPai  '#fff' : periodoColor, fontWeight: periodo > 0  600 : 400 }}>
                          {it.is_folha && !fechado && !somenteVisualizacao
                             (
                              <PctInput
                                value={it.pct_acumulado * 100}
                                onCommit={v => handleEdit(it.codigo, v)}
                                title={isAdmin
                                   `Herdado do Serviço ${vinc}. Digite para sobrepor — aceita conta (ex.: 100/3).`
                                  : '% acumulado total — aceita conta (ex.: 100/3)'}
                                style={{
                                  width: 78, padding: '2px 4px', borderRadius: 4,
                                  border: excedeu  '1px solid #DC2626'
                                    : regrediu  '1px solid #d97706'
                                    : '1px solid #d1d5db',
                                  textAlign: 'right', fontSize: 12,
                                  background: excedeu  '#FEF2F2'
                                    : regrediu  '#FFF7ED'
                                    : adminAuto  '#E3EDF9'
                                    : 'white',
                                  color: adminAuto  '#185FA5' : '#1a1a1a',
                                  fontStyle: adminAuto  'italic' : 'normal',
                                }}
                              />
                            )
                            : fmt(it.pct_acumulado)
                          }
                        </td>
                        <td style={{ ...tdStyle, color: isPai  '#c8dff5' : excedeu  '#DC2626' : '#888', fontSize: 11 }}
                            title={excedeu  'Item ultrapassou 100% — saldo negativo' : 'Saldo que ainda resta medir'}>
                          {fmtR(saldoR)}{excedeu  ' ⚠' : ''}
                        </td>
                        <td style={{ ...tdStyle, padding: '2px 4px' }}>
                          {it.is_folha && (
                            <button
                              onClick={() => setGaleria({ codigo: it.codigo, descricao: it.descricao })}
                              title="Fotos de evidência"
                              style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                fontSize: 14, padding: 2,
                              }}
                            >📷</button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Rodapé de ações */}
          <div style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {/* PDF sempre disponível */}
            <button
              onClick={() => window.open(bmPdfUrl(dados.ciclo.id), '_blank')}
              style={btnStyle('#6b21a8')}
              title="Gerar PDF do BM"
            >
              Gerar PDF
            </button>
            <button
              onClick={() => window.open(bmAnexoResumoPdfUrl(dados.ciclo.id), '_blank')}
              style={btnStyle('#063057')}
              title="Gerar ANEXO I - RESUMO BM"
            >
              Gerar Anexo I
            </button>
            {somenteVisualizacao && (
              <span style={{ background: '#eef2ff', color: '#1d4ed8', borderRadius: 8, padding: '6px 14px', fontSize: 13, fontWeight: 600 }}>
                Link somente para consulta
              </span>
            )}

            {/* Fechar / Reabrir Previsão — só disponível quando o BM ainda não está fechado */}
            {!somenteVisualizacao && status === 'em_previa' && prevInfo?.status === 'em_edicao' && (
              <button onClick={handleFecharPrevisao} disabled={salvando}
                title="Congela a previsão para permitir abertura do BM"
                style={btnStyle('#0891b2')}>
                Fechar Previsão
              </button>
            )}
            {!somenteVisualizacao && status === 'em_previa' && prevInfo?.status === 'fechada' && (
              <button onClick={handleReabrirPrevisao} disabled={salvando}
                title="Reabre a previsão para edição (invalida snapshot se BM está em prévia)"
                style={{ ...btnStyle('#6b7280'), fontSize: 12 }}>
                Reabrir Previsão
              </button>
            )}

            {!somenteVisualizacao && status === 'em_previa' && (
              <>
                <button onClick={handleSalvar} disabled={salvando} style={btnStyle('#2563eb')}>
                  {salvando  'Salvando...' : 'Salvar Prévia'}
                </button>
                <button onClick={() => handleAvancarStatus('em_analise')} disabled={salvando} style={btnStyle('#d97706')}>
                  Enviar p/ Análise
                </button>
              </>
            )}

            {!somenteVisualizacao && status === 'em_analise' && (
              <>
                <button onClick={handleSalvar} disabled={salvando} style={btnStyle('#2563eb')}>
                  {salvando  'Salvando...' : 'Salvar'}
                </button>
                <button onClick={() => handleAvancarStatus('pre_aprovada')} disabled={salvando} style={btnStyle('#7c3aed')}>
                  Pré-Aprovar
                </button>
                <button onClick={() => handleAvancarStatus('em_previa')} disabled={salvando}
                  style={{ ...btnStyle('#6b7280'), fontSize: 12 }} title="Retornar para prévia">
                  ← Devolver
                </button>
              </>
            )}

            {!somenteVisualizacao && status === 'pre_aprovada' && (
              <>
                <button onClick={() => setConfirmFechar(true)} disabled={salvando} style={btnStyle('#16a34a')}>
                  Fechar BM
                </button>
                <button onClick={() => handleAvancarStatus('em_analise')} disabled={salvando}
                  style={{ ...btnStyle('#6b7280'), fontSize: 12 }} title="Retornar para análise">
                  ← Devolver
                </button>
              </>
            )}

            {!somenteVisualizacao && status === 'fechada' && (
              <>
                <span style={{ background: '#dcfce7', color: '#166534', borderRadius: 8, padding: '6px 14px', fontSize: 13, fontWeight: 600 }}>
                  BM imutável
                </span>
                <button onClick={() => setConfirmConsolidar(true)} disabled={salvando} style={btnStyle('#064e3b')}>
                  Consolidar BM
                </button>
              </>
            )}

            {status === 'consolidada' && (
              <span style={{ background: '#dcfce7', color: '#166534', borderRadius: 8, padding: '6px 14px', fontSize: 13, fontWeight: 600 }}>
                BM Consolidado — imutável
              </span>
            )}

            <span style={{ marginLeft: 'auto', fontSize: 12, color: '#888' }}>
              {dados.ciclo.fechado_por
                 `Fechado por ${dados.ciclo.fechado_por}`
                : `Ciclo #${dados.ciclo.id}`}
            </span>
          </div>

          {/* Pendências geradas (somente BM fechado) */}
          {(status === 'fechada' || status === 'consolidada') && dados.pendencias?.length > 0 && (
            <div style={{ ...cardStyle, border: '1px solid #fcd34d' }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: '#92400e', marginBottom: 10 }}>
                ⚠ {dados.pendencias.length} pendência{dados.pendencias.length > 1  's' : ''} gerada{dados.pendencias.length > 1  's' : ''} neste BM
              </div>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#fef3c7' }}>
                    <th style={{ ...thStyle, textAlign: 'left' }}>Item EAP</th>
                    <th style={thStyle}>Previsto</th>
                    <th style={thStyle}>Realizado</th>
                    <th style={thStyle}>Gap</th>
                    <th style={thStyle}>Valor Gap</th>
                    <th style={thStyle}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dados.pendencias.map(p => (
                    <tr key={p.id} style={{ borderBottom: '1px solid #fde68a' }}>
                      <td style={{ ...tdStyle, textAlign: 'left' }}>
                        <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{p.eap_codigo}</span>
                        {' '}{p.eap_descricao}
                      </td>
                      <td style={tdStyle}>{p.pct_previsto?.toFixed(2)}%</td>
                      <td style={tdStyle}>{p.pct_realizado?.toFixed(2)}%</td>
                      <td style={{ ...tdStyle, color: '#b45309', fontWeight: 600 }}>{p.pct_gap?.toFixed(2)}%</td>
                      <td style={{ ...tdStyle, color: '#b45309' }}>
                        R$ {p.valor_gap?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                      </td>
                      <td style={tdStyle}>
                        <span style={{
                          background: p.status === 'ativa'  '#fef3c7' : '#dcfce7',
                          color: p.status === 'ativa'  '#92400e' : '#166534',
                          borderRadius: 12, padding: '2px 8px', fontSize: 11, fontWeight: 600,
                        }}>{p.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Modal de galeria de fotos */}
      {galeria && (
        <GaleriaFotoModal
          ano={ano}
          mes={mes}
          eapCodigo={galeria.codigo}
          eapDescricao={galeria.descricao}
          somenteVisualizacao={somenteVisualizacao}
          onClose={() => setGaleria(null)}
        />
      )}

      {/* Modal de confirmação de fechamento */}
      {confirmFechar && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 32, maxWidth: 420, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
            <h3 style={{ margin: '0 0 8px', color: '#063057', fontSize: 18 }}>Fechar BM?</h3>
            <p style={{ color: '#555', fontSize: 14, margin: '0 0 16px' }}>
              Esta ação tornará o Boletim de Medição de <strong>{MESES_PT[mes]}/{ano}</strong> imutável.
              Os valores atuais serão salvos e o ciclo será encerrado.
            </p>
            <input
              type="text"
              placeholder="Seu nome (opcional)"
              value={fechadoPor}
              onChange={e => setFechadoPor(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmFechar(false)} style={btnStyle('#6b7280')}>Cancelar</button>
              <button onClick={handleFechar} disabled={salvando} style={btnStyle('#16a34a')}>
                {salvando  'Fechando...' : 'Confirmar Fechamento'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de consolidação */}
      {confirmConsolidar && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 32, maxWidth: 420, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
            <h3 style={{ margin: '0 0 8px', color: '#064e3b', fontSize: 18 }}>Consolidar BM?</h3>
            <p style={{ color: '#555', fontSize: 14, margin: '0 0 16px' }}>
              A consolidação registra o BM de <strong>{MESES_PT[mes]}/{ano}</strong> como base
              histórica permanente. Esta ação <strong>não pode ser desfeita</strong>.
            </p>
            <input
              type="text"
              placeholder="Seu nome (opcional)"
              value={consolidadoPor}
              onChange={e => setConsolidadoPor(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmConsolidar(false)} style={btnStyle('#6b7280')}>Cancelar</button>
              <button onClick={handleConsolidar} disabled={salvando} style={btnStyle('#064e3b')}>
                {salvando  'Consolidando...' : 'Confirmar Consolidação'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ResumoCard({ label, valor, cor, detalhe }) {
  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '0.5px solid #E0E0DC', padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: cor }}>{valor}</div>
      {detalhe && (
        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 3, lineHeight: 1.3 }}>{detalhe}</div>
      )}
    </div>
  )
}

const navBtnStyle = {
  background: '#063057', color: '#fff', border: 'none', borderRadius: 8,
  width: 36, height: 36, fontSize: 16, cursor: 'pointer', display: 'flex',
  alignItems: 'center', justifyContent: 'center',
}

function btnStyle(bg) {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 8,
    padding: '9px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
  }
}

const thStyle = {
  padding: '10px 10px',
  textAlign: 'right',
  fontWeight: 600,
  fontSize: 11,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  whiteSpace: 'nowrap',
  borderBottom: '1px solid rgba(255,255,255,0.1)',
}

const tdStyle = {
  padding: '7px 10px',
  textAlign: 'right',
  borderBottom: '1px solid #f0f0ee',
}


// ── Galeria de Fotos por item EAP ─────────────────────────────────────
function GaleriaFotoModal({ ano, mes, eapCodigo, eapDescricao, somenteVisualizacao = false, onClose }) {
  const [fotos, setFotos] = useState([])
  const [loading, setLoading] = useState(false)
  const [legenda, setLegenda] = useState('')
  const [file, setFile] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)

  const carregar = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getFotosMedicao(ano, mes, { eap_codigo: eapCodigo })
      setFotos(data || [])
    } catch (e) {
      setErro('Erro ao carregar: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }, [ano, mes, eapCodigo])

  useEffect(() => { carregar() }, [carregar])

  async function handleUpload() {
    if (somenteVisualizacao) return
    if (!file) { setErro('Selecione um arquivo.'); return }
    setEnviando(true); setErro(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('eap_codigo', eapCodigo)
      fd.append('eap_descricao', eapDescricao || '')
      if (legenda) fd.append('legenda', legenda)
      await uploadFotoMedicao(ano, mes, fd)
      setLegenda(''); setFile(null)
      // Reset input
      const inp = document.getElementById('galeria-file-input')
      if (inp) inp.value = ''
      await carregar()
    } catch (e) {
      setErro('Erro ao enviar: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setEnviando(false)
    }
  }

  async function handleEditLegenda(f) {
    if (somenteVisualizacao) return
    const nova = prompt('Editar legenda da Foto ' + (f.numero || ''), f.legenda || '')
    if (nova === null) return
    try {
      await atualizarLegendaFoto(ano, mes, f.id, nova)
      carregar()
    } catch (e) {
      alert('Erro: ' + (e?.response?.data?.detail || e.message))
    }
  }

  async function handleDelete(f) {
    if (somenteVisualizacao) return
    if (!confirm(`Excluir Foto ${f.numero || ''}?`)) return
    try {
      await deletarFotoMedicao(ano, mes, f.id)
      carregar()
    } catch (e) {
      alert('Erro: ' + (e?.response?.data?.detail || e.message))
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: 24, width: '92%',
        maxWidth: 720, maxHeight: '90vh', overflowY: 'auto',
        boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0, color: '#063057', fontSize: 17 }}>Fotos — {eapCodigo}</h3>
            <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>{eapDescricao}</div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: '#666',
          }}>×</button>
        </div>

        {erro && (
          <div style={{ background: '#fee2e2', color: '#b91c1c', padding: '8px 12px', borderRadius: 6, fontSize: 12, marginBottom: 12 }}>{erro}</div>
        )}

        {/* Upload */}
        {!somenteVisualizacao && (
        <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: '#374151' }}>Adicionar foto</div>
          <input
            id="galeria-file-input"
            type="file"
            accept="image/*"
            onChange={e => setFile(e.target.files?.[0] || null)}
            style={{ width: '100%', marginBottom: 8, fontSize: 12 }}
          />
          <input
            type="text"
            value={legenda}
            onChange={e => setLegenda(e.target.value)}
            placeholder="Legenda (opcional)"
            style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 12, marginBottom: 8, boxSizing: 'border-box' }}
          />
          <button
            onClick={handleUpload}
            disabled={enviando || !file}
            style={{
              background: enviando || !file  '#9ca3af' : '#2563eb', color: '#fff', border: 'none',
              borderRadius: 6, padding: '7px 16px', fontSize: 12, fontWeight: 600,
              cursor: enviando || !file  'not-allowed' : 'pointer',
            }}
          >{enviando  'Enviando...' : 'Adicionar'}</button>
        </div>
        )}

        {/* Grid */}
        {loading  (
          <div style={{ textAlign: 'center', padding: 20, color: '#888' }}>Carregando...</div>
        ) : fotos.length === 0  (
          <div style={{ textAlign: 'center', padding: 20, color: '#888', fontSize: 13 }}>Nenhuma foto para este item.</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {fotos.map(f => (
              <div key={f.id} style={{ position: 'relative' }}>
                <img
                  src={fotoUrl(f)}
                  alt={f.legenda || `Foto ${f.numero}`}
                  style={{
                    width: '100%', height: 160, objectFit: 'cover',
                    borderRadius: 6, border: '1px solid #d1d5db',
                  }}
                />
                <div style={{ marginTop: 4, fontSize: 11, color: '#1a1a1a' }}>
                  <strong>Foto {f.numero}:</strong> {f.legenda || <em style={{ color: '#888' }}>sem legenda</em>}
                </div>
                {!somenteVisualizacao && (
                <div style={{ position: 'absolute', top: 4, right: 4, display: 'flex', gap: 3 }}>
                  <button onClick={() => handleEditLegenda(f)} title="Editar legenda"
                    style={{ background: 'rgba(0,0,0,0.7)', color: '#fff', border: 'none', borderRadius: 4, width: 26, height: 26, cursor: 'pointer', fontSize: 12 }}
                  >✏️</button>
                  <button onClick={() => handleDelete(f)} title="Excluir"
                    style={{ background: 'rgba(0,0,0,0.7)', color: '#fff', border: 'none', borderRadius: 4, width: 26, height: 26, cursor: 'pointer', fontSize: 12 }}
                  >🗑️</button>
                </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
