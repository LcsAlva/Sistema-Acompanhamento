// Previsão Mensal — visão hierárquica colapsável (EAP completa)
//
// Fluxo típico:
//   1. Selecionar mês
//   2. "Puxar do P6" — pré-popula % previsto das folhas pelo cronograma
//   3. Editar % previsto por item-folha (input numérico)
//   4. Pais calculam automaticamente pela média ponderada dos filhos
//   5. "Salvar Previsão"

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  getEapItens, getPrevisaoMensal, lancarPrevisaoMensal,
  criarAtividadeManualEap, removerAtividadeManualEap,
  puxarPrevisaoP6, getMedicaoMes,
  adiantarPrevisaoMensal, removerAdiantadaPrevisao,
  getPendenciasMes,
  bmGetPorMes, bmAbrir, bmStatusPrevisao, bmFecharPrevisao, bmReabrirPrevisao,
} from '../api'
import { logError } from '../utils/errors'
import PctInput from '../components/PctInput'

const WBS_BG = ['#063057','#0A4778','#1260A0','#1A79C8','#2E86C1','#5DADE2']
const WBS_FW = [700, 700, 600, 600, 500, 400]

// Valores em R$ sempre com 2 casas decimais
const fmtBRL = (v) => 'R$ ' + (v  0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const PREV_LABEL = {
  sem_previsao: { label: 'SEM PREVISÃO', cor: '#6b7280' },
  em_edicao:    { label: 'PREV. EM EDIÇÃO', cor: '#0891b2' },
  fechada:      { label: 'PREV. FECHADA', cor: '#7c3aed' },
  convertida:   { label: 'PREV. CONVERTIDA', cor: '#16a34a' },
}

// Detecta itens "Administração Local" e o código do Serviço vinculado.
// Padrão da EAP Petrobras: a entrega N tem N.1 (Serviços) e N.2 (Adm. Local).
// A Adm. Local não tem avanço físico próprio — acompanha os Serviços.
// Retorna { adminCodigo: servicoCodigo }.
function detectarAdminLink(allItems, parentSet) {
  const codigos = new Set(allItems.map(i => i.codigo))
  const link = {}
  for (const it of allItems) {
    if (it.nivel !== 2) continue
    if (!/administra[çc][ãa]o\s+local/i.test(it.descricao || '')) continue
    const entrega = it.codigo.split('.')[0]
    const servico = `${entrega}.1`
    if (codigos.has(servico)) link[it.codigo] = servico
  }
  return link
}

const proximoMes = () => {
  const hoje = new Date()
  const d = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 1)
  return { ano: d.getFullYear(), mes: d.getMonth() + 1 }
}

// Propaga % previsto dos pais a partir das folhas (bottom-up, média ponderada por R$).
// `adminLink` ({ adminCodigo: servicoCodigo }) faz a Administração Local sem
// edição manual herdar o % do Serviço vinculado.
function propagarPrevisaoPais(allItems, editsPct, parentSet, adminLink = {}) {
  const pcts = {}
  // 1. Folhas — valor editado (admin local sem edição entra como 0 por enquanto)
  for (const it of allItems) {
    if (!parentSet.has(it.codigo)) {
      pcts[it.codigo] = editsPct[it.codigo]  0
    }
  }
  // 2. Pais bottom-up — ordena por tamanho de código decrescente
  const sorted = [...allItems].sort((a, b) => b.codigo.length - a.codigo.length || a.codigo.localeCompare(b.codigo))
  for (const it of sorted) {
    if (!parentSet.has(it.codigo)) continue
    const filhos = allItems.filter(f => f.parent_codigo === it.codigo)
    if (!filhos.length || !it.valor) continue
    const soma = filhos.reduce((s, f) => s + ((f.valor || 0) * (pcts[f.codigo]  0)), 0)
    pcts[it.codigo] = soma / it.valor
  }
  // 3. Administração Local sem edição manual → herda o % do Serviço vinculado
  for (const [adminCod, servicoCod] of Object.entries(adminLink)) {
    if (editsPct[adminCod] === undefined) {
      pcts[adminCod] = pcts[servicoCod]  0
    }
  }
  // 4. Re-propaga os pais nível-1 (a Adm. Local é filha direta da entrega)
  for (const it of sorted) {
    if (it.nivel !== 1 || !parentSet.has(it.codigo) || !it.valor) continue
    const filhos = allItems.filter(f => f.parent_codigo === it.codigo)
    if (!filhos.length) continue
    const soma = filhos.reduce((s, f) => s + ((f.valor || 0) * (pcts[f.codigo]  0)), 0)
    pcts[it.codigo] = soma / it.valor
  }
  return pcts
}

export default function PrevisaoMensal() {
  const inicial = proximoMes()
  const [ano, setAno] = useState(inicial.ano)
  const [mes, setMes] = useState(inicial.mes)

  const [allItems, setAllItems]   = useState([])   // todos os itens EAP
  const [previsoes, setPrevisoes] = useState([])
  const [medicao, setMedicao]     = useState([])
  const [busca, setBusca]         = useState('')
  const [loading, setLoading]     = useState(true)
  const [salvando, setSalvando]   = useState(false)
  const [colapsados, setColapsados] = useState({}) // { codigoResumo: bool }
  const [showAll, setShowAll]     = useState(false) // false = só itens do mês
  const [showAdiantar, setShowAdiantar] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [aba, setAba]             = useState('previsao') // 'previsao' | 'pendencias'
  const [pendencias, setPendencias] = useState([])
  const [loadingPend, setLoadingPend] = useState(false)
  const [prevInfo, setPrevInfo] = useState(null)
  const [bmMes, setBmMes] = useState(null)

  // edits: { codigo: pct_previsto (0–100) }
  const [edits, setEdits] = useState({})

  // Conjuntos derivados (recalculados só quando allItems muda)
  const parentSet = useMemo(() => {
    const s = new Set()
    allItems.forEach(it => { if (it.parent_codigo) s.add(it.parent_codigo) })
    return s
  }, [allItems])

  const paisComHierarquiaFinanceiraInconsistente = useMemo(() => {
    const porPai = {}
    allItems.forEach(it => {
      if (!it.parent_codigo) return
      porPai[it.parent_codigo] = (porPai[it.parent_codigo] || 0) + (Number(it.valor) || 0)
    })
    const set = new Set()
    allItems.forEach(it => {
      const valor = Number(it.valor) || 0
      const somaFilhos = porPai[it.codigo] || 0
      if (valor > 0 && somaFilhos > valor + 0.01) set.add(it.codigo)
    })
    return set
  }, [allItems])

  const medicaoPorCodigo = useMemo(() => {
    const m = {}
    medicao.forEach(x => { m[x.eap_codigo] = x })
    return m
  }, [medicao])

  // Vínculo Administração Local → Serviços
  const adminLink = useMemo(() => detectarAdminLink(allItems, parentSet), [allItems, parentSet])

  // Valores propagados para pais (já considera o vínculo da Adm. Local)
  const pcts = useMemo(
    () => propagarPrevisaoPais(allItems, edits, parentSet, adminLink),
    [allItems, edits, parentSet, adminLink]
  )

  const carregar = useCallback(() => {
    setLoading(true)
    Promise.all([
      getEapItens({ limit: 2000 }),     // TODOS os itens (pais + folhas)
      getPrevisaoMensal(ano, mes),
      getMedicaoMes(ano, mes),
      bmStatusPrevisao(ano, mes).catch(() => null),
      bmGetPorMes(ano, mes).catch(e => e?.response?.status === 404  null : Promise.reject(e)),
    ])
      .then(([items, prev, med, statusPrev, bm]) => {
        // Ordena por código (natural)
        const sorted = [...items].sort((a, b) =>
          a.codigo.localeCompare(b.codigo, undefined, { numeric: true })
        )
        setAllItems(sorted)
        setPrevisoes(prev)
        setMedicao(med)
        setPrevInfo(statusPrev)
        setBmMes(bm)
        // Inicializa edits com valores existentes (só folhas)
        const e = {}
        for (const x of prev) e[x.eap_codigo] = x.pct_previsto  0
        setEdits(e)
      })
      .catch(logError('PrevisaoMensal:carregar'))
      .finally(() => setLoading(false))
  }, [ano, mes])

  useEffect(() => { carregar() }, [carregar])

  const carregarPendencias = useCallback(() => {
    setLoadingPend(true)
    getPendenciasMes(ano, mes)
      .then(setPendencias)
      .catch(logError('PrevisaoMensal:pendencias'))
      .finally(() => setLoadingPend(false))
  }, [ano, mes])

  useEffect(() => {
    if (aba === 'pendencias') carregarPendencias()
  }, [aba, carregarPendencias])

  function toggleColapso(codigo) {
    setColapsados(prev => ({ ...prev, [codigo]: !prev[codigo] }))
  }

  // Visibilidade: colapsa descendentes de qualquer item-resumo.
  function isVisible(it) {
    if (it.nivel === 1) return true
    const parts = it.codigo.split('.')
    for (let i = 1; i < parts.length; i++) {
      const anc = parts.slice(0, i).join('.')
      if (colapsados[anc]) return false
    }
    return true
  }

  // Chave do mês selecionado para filtrar dist_mensal
  const monthKey = `${ano}-${String(mes).padStart(2, '0')}-01`

  // Conjunto de códigos adiantados neste mês
  const adiantadasSet = useMemo(() => {
    const s = new Set()
    previsoes.filter(p => p.adiantada).forEach(p => s.add(p.eap_codigo))
    return s
  }, [previsoes])

  // Info completa das adiantadas { codigo: { mes_original_ano, mes_original_mes } }
  const adiantadasInfo = useMemo(() => {
    const m = {}
    previsoes.filter(p => p.adiantada).forEach(p => {
      m[p.eap_codigo] = { mes_original_ano: p.mes_original_ano, mes_original_mes: p.mes_original_mes }
    })
    return m
  }, [previsoes])

  // Itens filtrados para o mês (dist_mensal > 0 OU tem edição OU é adiantada)
  const itemsDoMes = useMemo(() => {
    if (showAll) return allItems
    // Adiantadas + seus ancestrais
    const adiantadasComAnc = new Set()
    allItems.forEach(it => {
      if (adiantadasSet.has(it.codigo)) {
        adiantadasComAnc.add(it.codigo)
        let parts = it.codigo.split('.')
        while (parts.length > 1) { parts.pop(); adiantadasComAnc.add(parts.join('.')) }
      }
    })
    return allItems.filter(it =>
      (it.dist_mensal && (it.dist_mensal[monthKey]  0) > 0) ||
      (edits[it.codigo]  0) > 0 ||
      adiantadasComAnc.has(it.codigo)
    )
  }, [allItems, showAll, monthKey, edits, adiantadasSet])

  // Itens filtrados por busca (modo lista plana — busca em todos os itens)
  const itensBusca = useMemo(() => {
    if (!busca.trim()) return null
    const q = busca.toLowerCase()
    return allItems.filter(it =>
      !parentSet.has(it.codigo) &&   // só folhas na busca
      ((it.descricao || '').toLowerCase().includes(q) || it.codigo.startsWith(busca))
    ).slice(0, 200)
  }, [busca, allItems, parentSet])

  const statusPrevisao = prevInfo?.status || (previsoes.length > 0  'em_edicao' : 'sem_previsao')
  const prevMeta = PREV_LABEL[statusPrevisao] || { label: statusPrevisao, cor: '#6b7280' }
  const bmStatus = bmMes?.ciclo?.status
  const previsaoEditavel = statusPrevisao === 'em_edicao' || statusPrevisao === 'sem_previsao'
  const totalPrevisoesSalvas = prevInfo?.total  previsoes.length
  const podeFecharPrevisao = statusPrevisao === 'em_edicao' && totalPrevisoesSalvas > 0 && !salvando
  const podeReabrirPrevisao = statusPrevisao === 'fechada' && !['fechada', 'consolidada'].includes(bmStatus)

  const setEdit = (codigo, pct) => {
    if (!previsaoEditavel) return
    const num = Number(pct)
    // Clamp financeiro: pct_previsto deve estar em [0, 100].
    // Auto-ajuste UX: 150 → 100, -5 → 0. O backend também valida.
    const clamped = isNaN(num)  0 : Math.min(100, Math.max(0, num))
    setEdits(prev => ({ ...prev, [codigo]: clamped }))
  }

  // Remove a edição manual de um item. Para Administração Local, isso faz
  // o item voltar a herdar automaticamente o % do Serviço vinculado.
  const clearEdit = (codigo) => {
    if (!previsaoEditavel) return
    setEdits(prev => {
      const n = { ...prev }
      delete n[codigo]
      return n
    })
  }

  // ── totais (nivel-1 items acumulados) ─────────────────────────────
  const nivel1Items = useMemo(() => itemsDoMes.filter(it => it.nivel === 1), [itemsDoMes])

  const totals = useMemo(() => {
    let pvTotal = 0, bac = 0
    for (const it of nivel1Items) {
      bac += it.valor || 0
      pvTotal += (it.valor || 0) * (pcts[it.codigo]  0) / 100
    }
    const nFolhasComEdit = Object.keys(edits).filter(k => edits[k] > 0).length
    return { pvTotal, bac, nFolhasComEdit }
  }, [nivel1Items, pcts, edits])

  const handleSalvar = async () => {
    if (!previsaoEditavel) {
      alert('Esta previsao esta fechada ou convertida. Reabra antes de editar.')
      return
    }
    setSalvando(true)
    try {
      const itens = allItems
        .filter(it => !parentSet.has(it.codigo))   // só folhas
        .map(it => {
          // Admin Local: usa o valor efetivo (edição manual ou herdado do Serviço)
          const isAdmin = !!adminLink[it.codigo]
          const eff = isAdmin
             (pcts[it.codigo]  0)
            : (edits[it.codigo]  0)
          return { eap_codigo: it.codigo, pct_previsto: eff, observacao: null }
        })
        .filter(x => x.pct_previsto > 0)
      const res = await lancarPrevisaoMensal(ano, mes, { itens })
      alert(`Previsao salva: ${res.inseridos} novas, ${res.atualizados} atualizadas, ${res.removidos} removidas.\n\nSalvar nao fecha a previsao. Feche a previsao para liberar a medicao mensal.`)
      await carregar()
    } catch (e) {
      alert('Erro ao salvar: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const handlePuxarP6 = async () => {
    if (!previsaoEditavel) {
      alert('Esta previsao esta fechada ou convertida. Reabra antes de puxar do P6.')
      return
    }
    if (!window.confirm(`Puxar do P6 a previsão para ${MESES[mes-1]}/${ano} Não sobrescreve itens já previstos.`)) return
    setSalvando(true)
    try {
      const res = await puxarPrevisaoP6(ano, mes)
      alert(`${res.inseridos} itens adicionados (já existiam ${res.ja_existiam}).`)
      await carregar()
    } catch (e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const handleFecharPrevisao = async () => {
    if (!previsoes.length) {
      alert('Nao ha previsao salva para fechar neste mes.')
      return
    }
    setSalvando(true)
    try {
      await bmFecharPrevisao(ano, mes, 'usuario')
      let bmAbertoAgora = false
      try {
        await bmGetPorMes(ano, mes)
      } catch (e) {
        if (e?.response?.status === 404) {
          await bmAbrir(ano, mes, 'usuario', 'Aberto automaticamente ao fechar a previsao mensal.')
          bmAbertoAgora = true
        } else {
          throw e
        }
      }
      await carregar()
      alert(bmAbertoAgora
        ? 'Previsao fechada e BM aberto automaticamente. A medicao mensal ja esta liberada.'
        : 'Previsao fechada. O BM deste mes ja estava aberto para lancamento.')
    } catch (e) {
      alert('Erro ao fechar previsao: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const handleReabrirPrevisao = async () => {
    setSalvando(true)
    try {
      await bmReabrirPrevisao(ano, mes, 'usuario')
      await carregar()
      alert('Previsao reaberta para edicao.')
    } catch (e) {
      alert('Erro ao reabrir previsao: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  // ── render ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen p-4" style={{ background: '#F2F2F0' }}>

      {/* Barra de topo */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <h1 style={{ fontSize: 18, fontWeight: 600, color: '#063057' }}>Previsão Mensal</h1>
        <select value={mes} onChange={e => setMes(Number(e.target.value))}
          className="input-base" style={{ width: 90, fontSize: 12 }}>
          {MESES.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <input type="number" value={ano} onChange={e => setAno(Number(e.target.value))}
          className="input-base" style={{ width: 80, fontSize: 12 }} />
        <span style={{ fontSize: 11, color: '#777' }}>
          <span title="Folhas com % previsto lançado">{totals.nFolhasComEdit} previstas</span>
          <span style={{ margin: '0 4px', color: '#ccc' }}>·</span>
          prev {fmtBRL(totals.pvTotal)}
        </span>
        <span title={`Status da previsao: ${statusPrevisao}`}
          style={{ background: prevMeta.cor + '22', color: prevMeta.cor, border: `1px solid ${prevMeta.cor}55`,
            borderRadius: 20, padding: '3px 12px', fontSize: 11, fontWeight: 700 }}>
          {prevMeta.label}
        </span>
        {/* Abas */}
        <div style={{ display: 'flex', gap: 4, marginRight: 4 }}>
          {[
            { id: 'previsao', label: '📅 Previsão' },
            { id: 'pendencias', label: `⏳ Pendências${pendencias.length > 0  ` (${pendencias.length})` : ''}` },
          ].map(({ id, label }) => (
            <button key={id} onClick={() => setAba(id)}
              style={{
                fontSize: 11, padding: '3px 12px', borderRadius: 4, cursor: 'pointer',
                background: aba === id  '#063057' : 'white',
                color: aba === id  'white' : '#555',
                border: `1px solid ${aba === id  '#063057' : '#D0D0CC'}`,
                fontWeight: aba === id  600 : 400,
              }}>
              {label}
            </button>
          ))}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {podeFecharPrevisao && (
            <button onClick={handleFecharPrevisao} disabled={salvando}
              className="btn-navy" style={{ background: '#0891b2' }}>
              Fechar Previsao
            </button>
          )}
          {podeReabrirPrevisao && (
            <button onClick={handleReabrirPrevisao} disabled={salvando}
              className="btn-navy" style={{ background: '#6b7280' }}>
              Reabrir Previsao
            </button>
          )}
          <button onClick={handlePuxarP6} disabled={salvando || !previsaoEditavel}
            className="btn-navy" style={{ background: previsaoEditavel  '#185FA5' : '#9ca3af' }}>
            Puxar do P6
          </button>
          <button onClick={() => setShowAdiantar(true)} disabled={salvando || !previsaoEditavel}
            className="btn-navy" style={{ background: previsaoEditavel  '#7C3AED' : '#9ca3af' }}>
            Adiantar
          </button>
          <button onClick={() => setShowManual(true)} disabled={salvando || !previsaoEditavel}
            className="btn-navy" style={{ background: previsaoEditavel  '#0f766e' : '#9ca3af' }}>
            Atividade manual
          </button>
          <Link to={`/medicao/${ano}/${mes}`} className="btn-navy" style={{ background: '#3B6D11' }}>
            Lancar Avanco
          </Link>
          <button onClick={handleSalvar} disabled={salvando || !previsaoEditavel} className="btn-navy"
            style={{ background: previsaoEditavel  undefined : '#9ca3af' }}>
            {salvando  'Salvando...' : 'Salvar Previsao'}
          </button>
        </div>
      </div>

      {statusPrevisao === 'em_edicao' && (
        <div className="card" style={{ marginBottom: 10, padding: '9px 12px', background: '#FFFBEB', border: '1px solid #FDE68A', color: '#92400E', fontSize: 12 }}>
          Salvar nao fecha a previsao. Feche a previsao para liberar a medicao mensal.
        </div>
      )}
      {statusPrevisao === 'fechada' && (
        <div className="card" style={{ marginBottom: 10, padding: '9px 12px', background: '#F5F3FF', border: '1px solid #DDD6FE', color: '#5B21B6', fontSize: 12 }}>
          Previsao fechada. Agora voce pode abrir/lancar a medicao mensal.
        </div>
      )}
      {statusPrevisao === 'convertida' && (
        <div className="card" style={{ marginBottom: 10, padding: '9px 12px', background: '#F0FDF4', border: '1px solid #BBF7D0', color: '#166534', fontSize: 12 }}>
          Previsao convertida em BM. Para alterar, sera necessario cancelar/recriar o BM ou criar ajuste complementar.
        </div>
      )}

      {/* Modal adiantar atividade */}
      {showAdiantar && (
        <AdiantarModal
          ano={ano}
          mes={mes}
          allItems={allItems}
          parentSet={parentSet}
          monthKey={monthKey}
          adiantadasSet={adiantadasSet}
          onClose={() => setShowAdiantar(false)}
          onAdiantado={() => { setShowAdiantar(false); carregar() }}
        />
      )}

      {showManual && (
        <AtividadeManualModal
          ano={ano}
          mes={mes}
          allItems={allItems}
          parentSet={parentSet}
          edits={edits}
          onSetEdit={setEdit}
          onClose={() => setShowManual(false)}
          onChanged={() => { setShowManual(false); carregar() }}
        />
      )}

      {/* Aba Pendências */}
      {aba === 'pendencias' && (
        <TabelaPendencias
          pendencias={pendencias}
          loading={loadingPend}
          mesPrevLabel={`${MESES[mes - 2 < 0  11 : mes - 2]}/${mes === 1  ano - 1 : ano}`}
          onIncluir={(p) => {
            setEdit(p.eap_codigo, (edits[p.eap_codigo]  0) + p.gap)
            setAba('previsao')
          }}
          onIncluirTodos={(lista) => {
            lista.forEach(p => setEdit(p.eap_codigo, (edits[p.eap_codigo]  0) + p.gap))
            setAba('previsao')
          }}
        />
      )}

      {/* Card principal */}
      {aba === 'previsao' && (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 110px)' }}>

        {/* Campo de busca */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
          <input
            className="input-base" placeholder="Buscar item EAP (descrição ou código)…"
            style={{ flex: 1, fontSize: 12 }}
            value={busca} onChange={e => setBusca(e.target.value)}
          />
          {busca && (
            <button onClick={() => setBusca('')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#777', fontSize: 16 }}>
              ×
            </button>
          )}
          {!busca && (<>
            <button
              onClick={() => setShowAll(v => !v)}
              style={{
                fontSize: 10, padding: '3px 10px', borderRadius: 4, cursor: 'pointer', whiteSpace: 'nowrap',
                background: showAll  '#1d4ed8' : 'white',
                color: showAll  'white' : '#555',
                border: '1px solid #D0D0CC', fontWeight: showAll  600 : 400,
              }}
            >
              {showAll
                 `✓ Todos os itens (${allItems.length})`
                : `📅 Mês: ${itemsDoMes.length} na árvore`}
            </button>
            <button
              onClick={() => {
                const todosCod = itemsDoMes.filter(it => parentSet.has(it.codigo)).map(it => it.codigo)
                const algumAberto = todosCod.some(c => !colapsados[c])
                const novo = {}
                todosCod.forEach(c => { novo[c] = algumAberto })
                setColapsados(novo)
              }}
              style={{ background: 'none', border: '1px solid #D0D0CC', borderRadius: 4, padding: '3px 8px', fontSize: 10, cursor: 'pointer', color: '#555', whiteSpace: 'nowrap' }}
            >
              ⊞ Expandir / Recolher
            </button>
          </>)}
        </div>

        <div style={{ overflow: 'auto', flex: 1 }}>
          {loading  (
            <p style={{ color: '#999', fontSize: 12, padding: 16 }}>Carregando…</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
                <tr style={{ background: '#063057', color: '#fff' }}>
                  <th style={th()}>Código</th>
                  <th style={{ ...th(), textAlign: 'left', minWidth: 220 }}>Descrição</th>
                  <th style={{ ...th(), textAlign: 'right' }}>Valor (R$)</th>
                  <th style={{ ...th(), textAlign: 'right' }}>Acum. Anterior</th>
                  <th style={{ ...th(), textAlign: 'right', width: 110 }}>% Previsto</th>
                  <th style={{ ...th(), textAlign: 'right' }}>R$ Previsto</th>
                  <th style={{ ...th(), textAlign: 'right' }} title="Quanto ainda resta do item após o acumulado anterior e a previsão deste mês">Saldo</th>
                  <th style={{ ...th(), width: '13%' }}>Observação</th>
                  <th style={th()}></th>
                </tr>
              </thead>
              <tbody>
                {/* ── Modo busca: lista plana de folhas ── */}
                {itensBusca !== null && (
                  itensBusca.length === 0
                     <tr><td colSpan={9} style={{ padding: 20, textAlign: 'center', color: '#999', fontSize: 12 }}>Nenhum item encontrado.</td></tr>
                    : itensBusca.map((it, idx) => {
                      const vinc = adminLink[it.codigo] || null
                      const isAdm = !!vinc
                      return (
                        <LinhaFolha
                          key={it.codigo}
                          it={it}
                          pct={isAdm  (pcts[it.codigo]  0) : (edits[it.codigo]  0)}
                          acumAnt={medicaoPorCodigo[it.codigo]?.pct_acum_anterior  0}
                          hasEdit={isAdm  edits[it.codigo] !== undefined : (edits[it.codigo]  0) > 0}
                          idx={idx}
                          vinculadoA={vinc}
                          disabled={!previsaoEditavel}
                          onEdit={setEdit}
                          onRemover={() => clearEdit(it.codigo)}
                        />
                      )
                    })
                )}

                {/* ── Modo árvore ── */}
                {itensBusca === null && itemsDoMes.map((it, idx) => {
                  if (!isVisible(it)) return null
                  const isN1 = it.nivel === 1
                  const isFolha = !parentSet.has(it.codigo)
                  const vinculadoA = isFolha  (adminLink[it.codigo] || null) : null
                  const isAdmin = !!vinculadoA
                  // Admin Local e pais usam o valor propagado; folha normal usa a edição
                  const pct = (!isFolha || isAdmin)  (pcts[it.codigo]  0) : (edits[it.codigo]  0)
                  const hierarquiaFinanceiraInconsistente = !isFolha && it.nivel > 1 && paisComHierarquiaFinanceiraInconsistente.has(it.codigo)
                  const pvR = (it.valor || 0) * pct / 100
                  const acumAnt = isFolha  (medicaoPorCodigo[it.codigo]?.pct_acum_anterior  0) : null
                  const hasEdit = isFolha && (isAdmin
                     edits[it.codigo] !== undefined
                    : (edits[it.codigo]  0) > 0)
                  const indentPx = (it.nivel - 1) * 16

                  if (isN1) {
                    return (
                      <tr key={it.codigo} style={{ background: '#063057', color: '#fff', fontWeight: 700 }}>
                        <td style={{ ...td(), whiteSpace: 'nowrap' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <button
                              onClick={() => toggleColapso(it.codigo)}
                              style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 11, padding: '0 2px', lineHeight: 1 }}
                            >
                              {colapsados[it.codigo]  '▸' : '▾'}
                            </button>
                            {it.codigo}
                          </span>
                        </td>
                        <td style={{ ...td(), textAlign: 'left' }}>{it.descricao}</td>
                        <td style={{ ...td(), textAlign: 'right', color: '#a5c8f0' }}>{fmtBRL(it.valor)}</td>
                        <td style={{ ...td(), textAlign: 'right', color: '#a5c8f0' }}>—</td>
                        <td style={{ ...td(), textAlign: 'right' }}>
                          {pct > 0  pct.toFixed(2) + '%' : '—'}
                        </td>
                        <td style={{ ...td(), textAlign: 'right', color: pct > 0  '#a5f0c8' : '#a5c8f0' }}>
                          {pct > 0  fmtBRL(pvR) : '—'}
                        </td>
                        <td style={{ ...td(), textAlign: 'right', color: '#a5c8f0' }}>
                          {hierarquiaFinanceiraInconsistente ? fmtBRL(it.valor || 0) : fmtBRL((it.valor || 0) - pvR)}
                        </td>
                        <td colSpan={2} />
                      </tr>
                    )
                  }

                  if (!isFolha) {
                    // Nó pai intermediário — cores progressivas WBS
                    const paiBg  = WBS_BG[Math.min(it.nivel - 1, WBS_BG.length - 1)]
                    const paiFw  = WBS_FW[Math.min(it.nivel - 1, WBS_FW.length - 1)]
                    return (
                      <tr key={it.codigo} style={{ background: paiBg, color: '#fff', fontWeight: paiFw }}>
                        <td style={{ ...td(), whiteSpace: 'nowrap' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <button
                              onClick={() => toggleColapso(it.codigo)}
                              style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 11, padding: '0 2px', lineHeight: 1 }}
                            >
                              {colapsados[it.codigo]  '▸' : '▾'}
                            </button>
                            {it.codigo}
                          </span>
                        </td>
                        <td style={{ ...td(), textAlign: 'left', paddingLeft: indentPx + 8 }}>
                          {it.descricao}
                        </td>
                        <td style={{ ...td(), textAlign: 'right', color: '#a5c8f0', fontSize: 10 }}>{fmtBRL(it.valor)}</td>
                        <td style={{ ...td(), textAlign: 'right', color: '#a5c8f0' }}>—</td>
                        <td style={{ ...td(), textAlign: 'right', color: pct > 0  '#a5f0c8' : '#a5c8f0', fontWeight: 600 }}>
                          {pct > 0  pct.toFixed(2) + '%' : '—'}
                        </td>
                        <td style={{ ...td(), textAlign: 'right', color: pct > 0  '#a5f0c8' : '#a5c8f0', fontSize: 10 }}>
                          {pct > 0  fmtBRL(pvR) : '—'}
                        </td>
                        <td style={{ ...td(), textAlign: 'right', color: '#a5c8f0', fontSize: 10 }}>
                          {hierarquiaFinanceiraInconsistente ? fmtBRL(it.valor || 0) : fmtBRL((it.valor || 0) - pvR)}
                        </td>
                        <td colSpan={2} />
                      </tr>
                    )
                  }

                  // Folha — editável
                  return (
                    <LinhaFolha
                      key={it.codigo}
                      it={it}
                      pct={pct}
                      acumAnt={acumAnt}
                      hasEdit={hasEdit}
                      idx={idx}
                      indentPx={indentPx}
                      vinculadoA={vinculadoA}
                      disabled={!previsaoEditavel}
                      onEdit={setEdit}
                      onRemover={() => clearEdit(it.codigo)}
                      adiantada={adiantadasSet.has(it.codigo)}
                      adiantadaInfo={adiantadasInfo[it.codigo]}
                      onRemoverAdiantada={async () => {
                        try {
                          await removerAdiantadaPrevisao(ano, mes, it.codigo)
                          carregar()
                        } catch (e) {
                          alert('Erro ao remover adiantamento: ' + (e.response?.data?.detail || e.message))
                        }
                      }}
                    />
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
      )}
    </div>
  )
}

// ── Linha de folha editável ────────────────────────────────────────
function LinhaFolha({ it, pct, acumAnt, hasEdit, idx, indentPx = 0, onEdit, onRemover,
                      vinculadoA = null,
                      adiantada = false, adiantadaInfo = null, onRemoverAdiantada,
                      disabled = false }) {
  const isAdmin = !!vinculadoA
  const pvR = (it.valor || 0) * pct / 100
  const acumAntPct = (acumAnt  0) * 100
  // Saldo = quanto resta do item após o acumulado anterior e a previsão deste mês
  const saldoPct = 100 - acumAntPct - pct
  const saldoR = (it.valor || 0) * saldoPct / 100
  const excedeu = saldoPct < -0.01
  // Admin Local seguindo o Serviço automaticamente (sem sobreposição manual)
  const adminAuto = isAdmin && !hasEdit

  const rowBg = adiantada  '#F5F0FF'
    : adminAuto  '#EEF4FB'
    : hasEdit  '#F4FAF0'
    : (idx % 2 === 0  '#fff' : '#fafaf8')

  return (
    <tr style={{ borderBottom: '0.5px solid #E0E0DC', background: rowBg }}>
      <td style={{ ...td(), fontFamily: 'monospace', color: '#185FA5', fontWeight: 600, fontSize: 10, whiteSpace: 'nowrap' }}>
        {it.codigo}
      </td>
      <td style={{ ...td(), paddingLeft: indentPx + 8 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          {it.descricao}
          {isAdmin && (
            <span title={`Acompanha automaticamente o Serviço ${vinculadoA}`}
              style={{ fontSize: 9, background: '#185FA5', color: '#fff', borderRadius: 3, padding: '1px 5px', fontWeight: 600, whiteSpace: 'nowrap' }}>
              ↔ vinc. {vinculadoA}
            </span>
          )}
          {adiantada && (
            <span title={adiantadaInfo  `Adiantada de ${MESES[(adiantadaInfo.mes_original_mes  1) - 1]}/${adiantadaInfo.mes_original_ano}` : 'Adiantada'}
              style={{ fontSize: 9, background: '#7C3AED', color: '#fff', borderRadius: 3, padding: '1px 4px', fontWeight: 600, whiteSpace: 'nowrap' }}>
              ⚡ adiantada
            </span>
          )}
        </span>
      </td>
      <td style={{ ...td(), textAlign: 'right', color: '#555', fontSize: 10 }}>
        {fmtBRL(it.valor)}
      </td>
      <td style={{ ...td(), textAlign: 'right', color: acumAntPct > 0  '#3B6D11' : '#bbb' }}>
        {acumAntPct > 0  acumAntPct.toFixed(2) + '%' : '—'}
      </td>
      <td style={{ ...td(), textAlign: 'right' }}>
        <PctInput
          value={pct}
          disabled={disabled}
          onCommit={v => onEdit(it.codigo, v)}
          title={isAdmin
             `Herdado do Serviço ${vinculadoA}. Digite para sobrepor manualmente — aceita conta (ex.: 100/3).`
            : 'Aceita conta — ex.: 100/3, 50+5'}
          style={{
            width: 78, padding: '2px 4px', fontSize: 11,
            textAlign: 'right', borderRadius: 3, outline: 'none',
            border: excedeu  '1px solid #DC2626' : '0.5px solid #D0D0CC',
            background: disabled  '#F3F4F6'
              : excedeu  '#FEF2F2'
              : adminAuto  '#E3EDF9'
              : hasEdit  '#f0fce8'
              : 'white',
            color: disabled  '#6b7280' : adminAuto  '#185FA5' : '#1a1a1a',
            fontStyle: adminAuto  'italic' : 'normal',
          }}
        />
      </td>
      <td style={{ ...td(), textAlign: 'right', color: pct > 0  '#185FA5' : '#bbb', fontWeight: pct > 0  600 : 400 }}>
        {pct > 0  fmtBRL(pvR) : '—'}
      </td>
      <td style={{ ...td(), textAlign: 'right', fontSize: 10, fontWeight: 600,
                   color: excedeu  '#DC2626' : '#888' }}
          title={excedeu  `Previsão acima do saldo: ${saldoPct.toFixed(2)}%` : `Saldo restante: ${saldoPct.toFixed(2)}%`}>
        {fmtBRL(saldoR)}{excedeu && ' ⚠'}
      </td>
      <td style={td()}>
        {/* observação omitida na visão hierárquica para não poluir */}
      </td>
      <td style={{ ...td(), whiteSpace: 'nowrap' }}>
        {adiantada && onRemoverAdiantada && !disabled && (
          <button onClick={onRemoverAdiantada}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7C3AED', fontSize: 14, marginRight: 2 }}
            title="Remover adiantamento">⚡×</button>
        )}
        {isAdmin && hasEdit && !disabled && (
          <button onClick={onRemover}
            style={{ background: 'none', border: '0.5px solid #185FA5', cursor: 'pointer', color: '#185FA5', fontSize: 9, borderRadius: 3, padding: '1px 4px' }}
            title={`Voltar a acompanhar o Serviço ${vinculadoA}`}>↺ auto</button>
        )}
        {!isAdmin && hasEdit && !adiantada && !disabled && (
          <button onClick={onRemover}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#A32D2D', fontSize: 14 }}
            title="Zerar esta previsão">×</button>
        )}
      </td>
    </tr>
  )
}

const th = () => ({
  padding: '6px 8px', fontSize: 9, fontWeight: 500,
  color: '#c8daf0', textAlign: 'right',
  borderBottom: '1px solid rgba(255,255,255,0.1)', whiteSpace: 'nowrap',
})
const td = () => ({ padding: '4px 8px', verticalAlign: 'middle', fontSize: 11 })

// ── Modal Adiantar Atividade ──────────────────────────────────────────

function isManualCodigo(codigo = '') {
  return codigo.split('.').some(p => /^M\d+$/i.test(p))
}

function AtividadeManualModal({ ano, mes, allItems, parentSet, edits, onSetEdit, onClose, onChanged }) {
  const pais = useMemo(
    () => allItems.filter(it => parentSet.has(it.codigo)).sort((a, b) => a.codigo.localeCompare(b.codigo, undefined, { numeric: true })),
    [allItems, parentSet]
  )
  const manuais = useMemo(() => allItems.filter(it => isManualCodigo(it.codigo)), [allItems])
  const [parentCodigo, setParentCodigo] = useState(pais[0]?.codigo || '')
  const [descricao, setDescricao] = useState('')
  const [valor, setValor] = useState('')
  const [pct, setPct] = useState(100)
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    if (!parentCodigo && pais[0]) setParentCodigo(pais[0].codigo)
  }, [parentCodigo, pais])

  const parent = pais.find(p => p.codigo === parentCodigo)

  async function criar() {
    const valorNum = Number(String(valor).replace(',', '.'))
    if (!parentCodigo) return alert('Selecione o item pai da EAP.')
    if (!descricao.trim()) return alert('Informe a descri??o da atividade.')
    if (!Number.isFinite(valorNum) || valorNum <= 0) return alert('Informe um peso/valor estimado maior que zero.')
    if (Number(pct) < 0 || Number(pct) > 100) return alert('O % previsto deve ficar entre 0% e 100%.')
    setSalvando(true)
    try {
      const item = await criarAtividadeManualEap({
        parent_codigo: parentCodigo,
        descricao: descricao.trim(),
        valor: valorNum,
        unidade: '%',
      })
      onSetEdit(item.codigo, Number(pct) || 0)
      await lancarPrevisaoMensal(ano, mes, {
        itens: [{ eap_codigo: item.codigo, pct_previsto: Number(pct) || 0, observacao: 'Atividade manual' }],
      })
      alert(`Atividade criada e prevista: ${item.codigo}.`)
      onChanged()
    } catch (e) {
      alert('Erro ao criar atividade manual: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  async function remover(codigo) {
    if (!confirm(`Remover a atividade manual ${codigo}? As previs?es em edi??o dela tamb?m ser?o apagadas.`)) return
    setSalvando(true)
    try {
      await removerAtividadeManualEap(codigo)
      onChanged()
    } catch (e) {
      alert('Erro ao remover atividade manual: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: '#fff', borderRadius: 8, width: 760, maxWidth: '95vw', maxHeight: '86vh', overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.3)' }}>
        <div style={{ background: '#0f766e', color: '#fff', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <strong style={{ fontSize: 14 }}>Atividade manual da previs?o</strong>
          <button onClick={onClose} style={{ background: 'none', border: 0, color: '#fff', fontSize: 20, cursor: 'pointer' }}>?</button>
        </div>
        <div style={{ padding: 14, display: 'grid', gap: 10 }}>
          <label style={{ fontSize: 11, fontWeight: 600 }}>
            Item pai da EAP
            <select value={parentCodigo} onChange={e => setParentCodigo(e.target.value)}
              style={{ marginTop: 4, width: '100%', padding: '7px 8px', border: '1px solid #D0D0CC', borderRadius: 5, fontSize: 12 }}>
              {pais.map(p => <option key={p.codigo} value={p.codigo}>{p.codigo} - {p.descricao} ({fmtBRL(p.valor)})</option>)}
            </select>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 150px 110px', gap: 10 }}>
            <label style={{ fontSize: 11, fontWeight: 600 }}>
              Descri??o da nova atividade
              <input value={descricao} onChange={e => setDescricao(e.target.value)} className="input-base"
                style={{ marginTop: 4, width: '100%', fontSize: 12 }} />
            </label>
            <label style={{ fontSize: 11, fontWeight: 600 }}>
              Peso estimado (R$)
              <input value={valor} onChange={e => setValor(e.target.value)} className="input-base"
                style={{ marginTop: 4, width: '100%', fontSize: 12, textAlign: 'right' }} />
            </label>
            <label style={{ fontSize: 11, fontWeight: 600 }}>
              % previsto
              <input type="number" min={0} max={100} value={pct} onChange={e => setPct(e.target.value)} className="input-base"
                style={{ marginTop: 4, width: '100%', fontSize: 12, textAlign: 'right' }} />
            </label>
          </div>
          {parent && (
            <div style={{ fontSize: 11, color: '#64748b' }}>
              A atividade entrar? abaixo de <strong>{parent.codigo}</strong>. O resumo do pai ser? recalculado pelo peso financeiro informado e o fechamento bloqueia qualquer pai acima de 100%.
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={criar} disabled={salvando} style={{ background: '#0f766e', color: '#fff', border: 0, borderRadius: 5, padding: '7px 18px', fontWeight: 700, cursor: 'pointer' }}>
              {salvando ? 'Salvando...' : 'Adicionar atividade'}
            </button>
          </div>
        </div>
        <div style={{ borderTop: '1px solid #E5E7EB', padding: 14, maxHeight: 240, overflow: 'auto' }}>
          <strong style={{ fontSize: 12, color: '#063057' }}>Atividades manuais existentes</strong>
          {manuais.length === 0 ? (
            <p style={{ fontSize: 12, color: '#999', marginTop: 8 }}>Nenhuma atividade manual criada.</p>
          ) : manuais.map(it => (
            <div key={it.codigo} style={{ display: 'grid', gridTemplateColumns: '110px 1fr 120px 80px', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #F0F0EC', fontSize: 11 }}>
              <span style={{ fontFamily: 'monospace', color: '#0f766e', fontWeight: 700 }}>{it.codigo}</span>
              <span>{it.descricao}</span>
              <span style={{ textAlign: 'right' }}>{fmtBRL(it.valor)}</span>
              <button onClick={() => remover(it.codigo)} disabled={salvando}
                style={{ border: '1px solid #A32D2D', color: '#A32D2D', background: '#fff', borderRadius: 4, padding: '3px 6px', cursor: 'pointer' }}>
                Remover
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function AdiantarModal({ ano, mes, allItems, parentSet, monthKey, adiantadasSet, onClose, onAdiantado }) {
  const [busca, setBusca] = useState('')
  const [collapsed, setCollapsed] = useState({})
  const [selecionado, setSelecionado] = useState(null) // { item, mesOrigAno, mesOrigMes }
  const [pctPrev, setPctPrev] = useState(0)
  const [obs, setObs] = useState('')
  const [salvando, setSalvando] = useState(false)

  // Itens que NÃO pertencem ao mês atual (não têm dist_mensal[monthKey])
  // e ainda não foram adiantados para este mês
  const itensApto = useMemo(() => {
    return allItems.filter(it => {
      if (parentSet.has(it.codigo)) return false          // só folhas
      if (adiantadasSet.has(it.codigo)) return false       // já adiantada
      const distMes = it.dist_mensal?.[monthKey]  0
      if (distMes > 0) return false                        // já pertence ao mês
      return true
    })
  }, [allItems, parentSet, adiantadasSet, monthKey])

  // Filtro por busca
  const itensFiltrados = useMemo(() => {
    if (!busca.trim()) return itensApto
    const q = busca.toLowerCase()
    return itensApto.filter(it =>
      it.descricao.toLowerCase().includes(q) || it.codigo.startsWith(busca)
    ).slice(0, 200)
  }, [itensApto, busca])

  // Árvore: calcula parentSet dos itens filtrados (para mostrar só ramos relevantes)
  const { treeItems, filtParentSet } = useMemo(() => {
    const codsSet = new Set(itensFiltrados.map(it => it.codigo))
    // adiciona ancestrais
    itensFiltrados.forEach(it => {
      let parts = it.codigo.split('.')
      while (parts.length > 1) { parts.pop(); codsSet.add(parts.join('.')) }
    })
    const tree = allItems.filter(it => codsSet.has(it.codigo))
    const fp = new Set()
    tree.forEach(it => { if (it.parent_codigo) fp.add(it.parent_codigo) })
    return { treeItems: tree, filtParentSet: fp }
  }, [allItems, itensFiltrados])

  function toggleCol(cod) { setCollapsed(p => ({ ...p, [cod]: !p[cod] })) }

  function isVis(it) {
    if (it.nivel === 1) return true
    const parts = it.codigo.split('.')
    for (let i = 1; i < parts.length; i++) {
      const anc = parts.slice(0, i).join('.')
      if (collapsed[anc]) return false
    }
    return true
  }

  // Meses disponíveis nos dados do item selecionado
  const mesesDisponiveis = useMemo(() => {
    if (!selecionado) return []
    const dm = selecionado.item.dist_mensal || {}
    return Object.entries(dm)
      .filter(([, v]) => v > 0)
      .map(([k]) => k)
      .sort()
  }, [selecionado])

  const [mesOrigKey, setMesOrigKey] = useState('')
  useEffect(() => {
    if (mesesDisponiveis.length > 0) setMesOrigKey(mesesDisponiveis[0])
  }, [mesesDisponiveis])

  async function handleAdiantar() {
    if (!selecionado) return
    const [oAno, oMes] = mesOrigKey  mesOrigKey.split('-').map(Number) : [ano, mes]
    setSalvando(true)
    try {
      await adiantarPrevisaoMensal(ano, mes, {
        eap_codigo: selecionado.item.codigo,
        pct_previsto: pctPrev,
        mes_original_ano: oAno,
        mes_original_mes: oMes,
        observacao: obs || null,
        lancado_por: null,
      })
      onAdiantado()
    } catch (e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: '#fff', borderRadius: 8, width: 700, maxWidth: '95vw',
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      }}>
        {/* Cabeçalho */}
        <div style={{ background: '#7C3AED', color: '#fff', padding: '12px 16px', borderRadius: '8px 8px 0 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>⚡ Adiantar Atividade — {MESES[mes - 1]}/{ano}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}>×</button>
        </div>

        {/* Busca */}
        <div style={{ padding: '10px 14px 6px', borderBottom: '1px solid #E0E0DC' }}>
          <input
            className="input-base" placeholder="Buscar item EAP (não pertence a este mês)…"
            style={{ width: '100%', fontSize: 12 }}
            value={busca} onChange={e => setBusca(e.target.value)}
          />
          <p style={{ fontSize: 10, color: '#888', margin: '4px 0 0' }}>
            Mostrando {itensFiltrados.length} itens folha disponíveis para adiantamento.
          </p>
        </div>

        {/* Árvore */}
        <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
          {treeItems.length === 0 && (
            <p style={{ fontSize: 12, color: '#999', padding: 16, textAlign: 'center' }}>Nenhum item disponível.</p>
          )}
          {treeItems.map(it => {
            if (!isVis(it)) return null
            const isFolha = !filtParentSet.has(it.codigo)
            const bg = WBS_BG[Math.min(it.nivel - 1, WBS_BG.length - 1)]
            const fw = WBS_FW[Math.min(it.nivel - 1, WBS_FW.length - 1)]
            const indentPx = (it.nivel - 1) * 16
            const isSel = selecionado?.item.codigo === it.codigo

            if (!isFolha) {
              return (
                <div key={it.codigo}
                  onClick={() => toggleCol(it.codigo)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: bg, color: '#fff', fontWeight: fw,
                    padding: `3px 10px 3px ${indentPx + 10}px`,
                    cursor: 'pointer', fontSize: 11, userSelect: 'none',
                  }}>
                  <span style={{ fontSize: 10, opacity: 0.8 }}>{collapsed[it.codigo]  '▸' : '▾'}</span>
                  <span style={{ opacity: 0.7, fontSize: 9, fontFamily: 'monospace', marginRight: 4 }}>{it.codigo}</span>
                  {it.descricao}
                </div>
              )
            }

            return (
              <div key={it.codigo}
                onClick={() => { setSelecionado({ item: it }); setPctPrev(0); setObs('') }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: `4px 10px 4px ${indentPx + 10}px`,
                  cursor: 'pointer', fontSize: 11,
                  background: isSel  '#ede8ff' : 'transparent',
                  borderLeft: isSel  '3px solid #7C3AED' : '3px solid transparent',
                  borderBottom: '0.5px solid #f0f0ec',
                }}>
                <span style={{ fontFamily: 'monospace', color: '#7C3AED', fontSize: 9, fontWeight: 600 }}>{it.codigo}</span>
                <span style={{ flex: 1 }}>{it.descricao}</span>
                <span style={{ fontSize: 9, color: '#aaa' }}>{fmtBRL(it.valor)}</span>
              </div>
            )
          })}
        </div>

        {/* Painel inferior (quando selecionado) */}
        {selecionado && (
          <div style={{ borderTop: '1px solid #E0E0DC', padding: '12px 14px', background: '#fafaf8', borderRadius: '0 0 8px 8px' }}>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#7C3AED', marginBottom: 8 }}>
              {selecionado.item.codigo} — {selecionado.item.descricao}
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <label style={{ fontSize: 11 }}>
                Mês de origem:&nbsp;
                <select value={mesOrigKey} onChange={e => setMesOrigKey(e.target.value)}
                  style={{ fontSize: 11, padding: '2px 6px', border: '1px solid #D0D0CC', borderRadius: 4 }}>
                  {mesesDisponiveis.length === 0
                     <option value="">—</option>
                    : mesesDisponiveis.map(k => {
                        const [y, m] = k.split('-')
                        return <option key={k} value={k}>{MESES[Number(m) - 1]}/{y}</option>
                      })
                  }
                </select>
              </label>
              <label style={{ fontSize: 11 }}>
                % Previsto:&nbsp;
                <input type="number" min={0} max={100} step={0.5} value={pctPrev}
                  onChange={e => setPctPrev(Number(e.target.value) || 0)}
                  style={{ width: 70, padding: '2px 4px', fontSize: 11, border: '1px solid #D0D0CC', borderRadius: 4, textAlign: 'right' }}
                />
                %
              </label>
              <label style={{ fontSize: 11, flex: 1 }}>
                Observação:&nbsp;
                <input type="text" value={obs} onChange={e => setObs(e.target.value)}
                  style={{ width: '100%', padding: '2px 4px', fontSize: 11, border: '1px solid #D0D0CC', borderRadius: 4 }}
                />
              </label>
              <button onClick={handleAdiantar} disabled={salvando}
                style={{ background: '#7C3AED', color: '#fff', border: 'none', borderRadius: 5, padding: '6px 18px', fontWeight: 700, fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                {salvando  'Salvando…' : '⚡ Confirmar Adiantamento'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tabela de Pendências do Mês Anterior ─────────────────────────────
function TabelaPendencias({ pendencias, loading, mesPrevLabel, onIncluir, onIncluirTodos }) {
  const totalGapR = pendencias.reduce((s, p) => s + (p.valor * p.gap / 100), 0)

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 110px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: '#555' }}>
          Itens previstos em <strong>{mesPrevLabel}</strong> que não foram totalmente realizados.
          Inclua no mês atual para redistribuir o saldo pendente.
        </span>
        {pendencias.length > 0 && (
          <button
            onClick={() => onIncluirTodos(pendencias)}
            style={{
              marginLeft: 'auto', background: '#063057', color: '#fff', border: 'none',
              borderRadius: 5, padding: '5px 16px', fontWeight: 600, fontSize: 11,
              cursor: 'pointer', whiteSpace: 'nowrap',
            }}>
            ↓ Incluir todos ({pendencias.length})
          </button>
        )}
      </div>

      <div style={{ overflow: 'auto', flex: 1 }}>
        {loading  (
          <p style={{ color: '#999', fontSize: 12, padding: 16 }}>Carregando…</p>
        ) : pendencias.length === 0  (
          <p style={{ color: '#999', fontSize: 12, padding: 20, textAlign: 'center' }}>
            Nenhuma pendência do mês anterior. Todos os itens previstos foram realizados (ou não há BM fechado).
          </p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
              <tr style={{ background: '#063057', color: '#fff' }}>
                <th style={thP()}>Código</th>
                <th style={{ ...thP(), textAlign: 'left', minWidth: 240 }}>Descrição</th>
                <th style={{ ...thP(), textAlign: 'right' }}>Valor (R$)</th>
                <th style={{ ...thP(), textAlign: 'right' }}>Previsto (%)</th>
                <th style={{ ...thP(), textAlign: 'right' }}>Realizado (%)</th>
                <th style={{ ...thP(), textAlign: 'right', color: '#fde68a' }}>Gap (%)</th>
                <th style={{ ...thP(), textAlign: 'right', color: '#fde68a' }}>Gap (R$)</th>
                <th style={thP()}></th>
              </tr>
            </thead>
            <tbody>
              {pendencias.map((p, idx) => {
                const gapR = p.valor * p.gap / 100
                return (
                  <tr key={p.eap_codigo}
                    style={{ borderBottom: '0.5px solid #E0E0DC', background: idx % 2 === 0  '#fff' : '#fafaf8' }}>
                    <td style={{ ...tdP(), fontFamily: 'monospace', color: '#185FA5', fontWeight: 600, fontSize: 10 }}>
                      {p.eap_codigo}
                    </td>
                    <td style={{ ...tdP(), textAlign: 'left' }}>{p.descricao}</td>
                    <td style={{ ...tdP(), textAlign: 'right', color: '#555', fontSize: 10 }}>{fmtBRL(p.valor)}</td>
                    <td style={{ ...tdP(), textAlign: 'right', color: '#555' }}>{p.pct_previsto.toFixed(2)}%</td>
                    <td style={{ ...tdP(), textAlign: 'right', color: p.pct_realizado > 0  '#3B6D11' : '#bbb' }}>
                      {p.pct_realizado > 0  p.pct_realizado.toFixed(2) + '%' : '—'}
                    </td>
                    <td style={{ ...tdP(), textAlign: 'right', color: '#B45309', fontWeight: 600 }}>
                      {p.gap.toFixed(2)}%
                    </td>
                    <td style={{ ...tdP(), textAlign: 'right', color: '#B45309', fontWeight: 600, fontSize: 10 }}>
                      {fmtBRL(gapR)}
                    </td>
                    <td style={{ ...tdP(), whiteSpace: 'nowrap' }}>
                      <button
                        onClick={() => onIncluir(p)}
                        style={{
                          background: '#063057', color: '#fff', border: 'none',
                          borderRadius: 4, padding: '2px 10px', fontSize: 10,
                          cursor: 'pointer', fontWeight: 600,
                        }}
                        title={`Adicionar ${p.gap.toFixed(2)}% à previsão do mês atual`}>
                        ↓ Incluir
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr style={{ background: '#F2F2F0', fontWeight: 700, borderTop: '1px solid #D0D0CC' }}>
                <td colSpan={6} style={{ ...tdP(), textAlign: 'right', color: '#555' }}>Total gap:</td>
                <td style={{ ...tdP(), textAlign: 'right', color: '#B45309' }}>{fmtBRL(totalGapR)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        )}
      </div>
    </div>
  )
}

const thP = () => ({
  padding: '6px 8px', fontSize: 9, fontWeight: 500,
  color: '#c8daf0', textAlign: 'right',
  borderBottom: '1px solid rgba(255,255,255,0.1)', whiteSpace: 'nowrap',
})
const tdP = () => ({ padding: '4px 8px', verticalAlign: 'middle', fontSize: 11 })
