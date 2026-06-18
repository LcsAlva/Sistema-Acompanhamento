// Tela "Lançar Avanço Semanal" — substitui o email semanal de avanço.
//
// Mostra os itens previstos do mês e, para a semana selecionada,
// permite lançar o DELTA (% que avançou nessa semana). Calcula o
// acumulado em tempo real para o operador ter feedback visual.

import { useState, useEffect, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useSemana } from '../context/SemanaContext'
import {
  getPrevisaoMensal, getMedicaoMes,
  getAvancoSemana, lancarAvancoSemana,
  getEapItens,
} from '../api'
import { logError } from '../utils/errors'

const fmtBRL = (v) => 'R$ ' + (v  0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtPct = (v) => (v  0).toFixed(2).replace('.', ',') + '%'

export default function LancarAvanco() {
  const params = useParams()  // /medicao/:ano/:mes
  const { semanas, semanaAtual } = useSemana()
  const [ano, setAno] = useState(Number(params.ano) || new Date().getFullYear())
  const [mes, setMes] = useState(Number(params.mes) || (new Date().getMonth() + 1))
  const [semanaSel, setSemanaSel] = useState(semanaAtual?.codigo || '')
  const [previsoes, setPrevisoes] = useState([])
  const [medicao, setMedicao] = useState([])
  const [avancoSemana, setAvancoSemana] = useState([])
  const [folhas, setFolhas] = useState([])
  const [edits, setEdits] = useState({})       // { codigo: { delta, observacao } }
  const [loading, setLoading] = useState(true)
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    if (!semanaSel && semanaAtual) setSemanaSel(semanaAtual.codigo)
  }, [semanaAtual, semanaSel])

  const carregar = () => {
    if (!semanaSel) return
    setLoading(true)
    Promise.all([
      getPrevisaoMensal(ano, mes),
      getMedicaoMes(ano, mes),
      getAvancoSemana(semanaSel),
      getEapItens({ so_folhas: true, limit: 2000 }),
    ])
      .then(([p, m, a, f]) => {
        setPrevisoes(p)
        setMedicao(m)
        setAvancoSemana(a)
        setFolhas(f)
        // Estado inicial: deltas já lançados nesta semana
        const e = {}
        for (const x of a) e[x.eap_codigo] = { delta: x.pct_delta, observacao: x.observacao || '' }
        setEdits(e)
      })
      .catch(logError('LancarAvanco:carregar'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { carregar() }, [ano, mes, semanaSel])

  const folhaPorCodigo = useMemo(() => {
    const m = {}; folhas.forEach(f => m[f.codigo] = f); return m
  }, [folhas])

  const medicaoPorCodigo = useMemo(() => {
    const m = {}; medicao.forEach(x => m[x.eap_codigo] = x); return m
  }, [medicao])

  // Itens a exibir: união (previstos no mês ∪ já lançados na semana)
  const codigosVisiveis = useMemo(() => {
    const set = new Set()
    for (const p of previsoes) set.add(p.eap_codigo)
    for (const a of avancoSemana) set.add(a.eap_codigo)
    return [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
  }, [previsoes, avancoSemana])

  const setEdit = (codigo, patch) => {
    setEdits(prev => ({
      ...prev,
      [codigo]: { ...(prev[codigo] || { delta: 0, observacao: '' }), ...patch },
    }))
  }

  const handleSalvar = async () => {
    if (!semanaSel) { alert('Selecione uma semana.'); return }
    setSalvando(true)
    try {
      const itens = codigosVisiveis.map(codigo => ({
        eap_codigo: codigo,
        pct_delta: Number(edits[codigo]?.delta || 0),
        observacao: edits[codigo]?.observacao || null,
      }))
      const res = await lancarAvancoSemana({ semana_codigo: semanaSel, itens })
      alert(`Avanço lançado: ${res.inseridos} novos, ${res.atualizados} atualizados, ${res.removidos} removidos.`)
      carregar()
    } catch (e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const total = useMemo(() => {
    let dr = 0, vd = 0
    for (const codigo of codigosVisiveis) {
      const f = folhaPorCodigo[codigo]
      const delta = Number(edits[codigo]?.delta || 0)
      if (f && delta) {
        dr += delta
        vd += (f.valor || 0) * delta / 100
      }
    }
    return { delta: dr, valor: vd, n: codigosVisiveis.length }
  }, [edits, codigosVisiveis, folhaPorCodigo])

  return (
    <div className="min-h-screen p-4" style={{background:'#F2F2F0'}}>
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <h1 style={{fontSize:18,fontWeight:600,color:'#063057'}}>Lançar Avanço Semanal</h1>
        <select value={mes} onChange={e => setMes(Number(e.target.value))}
                className="input-base" style={{width:90,fontSize:12}}>
          {['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'].map((m,i) =>
            <option key={i} value={i+1}>{m}</option>
          )}
        </select>
        <input type="number" value={ano} onChange={e => setAno(Number(e.target.value))}
               className="input-base" style={{width:80,fontSize:12}} />
        <span style={{fontSize:11,color:'#777'}}>·</span>
        <select value={semanaSel} onChange={e => setSemanaSel(e.target.value)}
                className="input-base" style={{minWidth:200,fontSize:12}}>
          <option value="">-- selecionar semana --</option>
          {semanas.map(s => (
            <option key={s.codigo} value={s.codigo}>
              {s.codigo} — {s.data_inicio?.split('-').slice(1).reverse().join('/')} a {s.data_fim?.split('-').slice(1).reverse().join('/')}
            </option>
          ))}
        </select>
        <span style={{fontSize:11,color:'#777'}}>
          {total.n} itens · Σ delta {total.delta.toFixed(2)}% · {fmtBRL(total.valor)}
        </span>
        <div style={{marginLeft:'auto',display:'flex',gap:8}}>
          <Link to={`/previsao/${ano}/${mes}`} className="btn-navy" style={{background:'#185FA5'}}>
            ← Editar Previsão
          </Link>
          <button onClick={handleSalvar} disabled={salvando || !semanaSel} className="btn-navy">
            {salvando  'Salvando…' : '💾 Salvar Avanço'}
          </button>
        </div>
      </div>

      <div className="card" style={{height:'calc(100vh - 110px)',overflow:'auto'}}>
        {loading  (
          <p style={{color:'#999',padding:16}}>Carregando…</p>
        ) : !semanaSel  (
          <p style={{color:'#999',padding:16,fontStyle:'italic'}}>Selecione uma semana acima.</p>
        ) : codigosVisiveis.length === 0  (
          <p style={{color:'#999',padding:16,fontStyle:'italic'}}>
            Nenhum item previsto neste mês. Vá em "Editar Previsão" para definir.
          </p>
        ) : (
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
            <thead style={{position:'sticky',top:0,background:'#F5F5F2',zIndex:1}}>
              <tr>
                <th style={th()}>Código</th>
                <th style={{...th(),width:'30%'}}>Descrição</th>
                <th style={{...th(),textAlign:'right'}}>Valor (R$)</th>
                <th style={{...th(),textAlign:'right'}}>Previsto</th>
                <th style={{...th(),textAlign:'right'}}>Acum. Anterior</th>
                <th style={{...th(),textAlign:'right',width:90}}>Δ Semana</th>
                <th style={{...th(),textAlign:'right'}}>Acum. Atual</th>
                <th style={{...th(),textAlign:'right'}}>R$ Período</th>
                <th style={{...th(),width:'15%'}}>Observação</th>
              </tr>
            </thead>
            <tbody>
              {codigosVisiveis.map(codigo => {
                const f = folhaPorCodigo[codigo]
                const med = medicaoPorCodigo[codigo]
                const prev = previsoes.find(p => p.eap_codigo === codigo)
                const ed = edits[codigo]
                const delta = Number(ed?.delta || 0)
                const acumAnt = (med?.pct_acum_anterior || 0)
                const pctMes = (med?.pct_periodo || 0)
                // Acum atual SIMULADO: o medicaoMes já reflete TODOS os deltas
                // do mês até hoje. Para feedback live, sobrepomos o delta editado.
                const acumLive = acumAnt + pctMes - (avancoSemana.find(a => a.eap_codigo === codigo)?.pct_delta || 0) + delta
                const valorPeriodo = (f?.valor || 0) * delta / 100

                return (
                  <tr key={codigo} style={{
                    borderBottom:'0.5px solid #E0E0DC',
                    background: delta  '#F7FBF2' : 'white',
                  }}>
                    <td style={{...td(),fontFamily:'monospace',color:'#185FA5',fontWeight:600}}>{codigo}</td>
                    <td style={td()}>{f?.descricao || '—'}</td>
                    <td style={{...td(),textAlign:'right'}}>{fmtBRL(f?.valor)}</td>
                    <td style={{...td(),textAlign:'right',color:'#888'}}>
                      {prev  fmtPct(prev.pct_previsto) : '—'}
                    </td>
                    <td style={{...td(),textAlign:'right',color: acumAnt > 0  '#3B6D11' : '#bbb'}}>
                      {acumAnt > 0  fmtPct(acumAnt) : '—'}
                    </td>
                    <td style={{...td(),textAlign:'right'}}>
                      <input type="number" min={-100} max={100} step={0.5}
                        value={ed?.delta  0}
                        onChange={e => setEdit(codigo, { delta: Number(e.target.value), observacao: ed?.observacao || '' })}
                        style={{width:70,padding:'2px 4px',fontSize:11,textAlign:'right',border:'0.5px solid #D0D0CC',borderRadius:3}}
                      />
                    </td>
                    <td style={{...td(),textAlign:'right',fontWeight:600,color: acumLive >= 100  '#3B6D11' : acumLive > 0  '#185FA5' : '#bbb'}}>
                      {fmtPct(acumLive)}
                    </td>
                    <td style={{...td(),textAlign:'right',color: delta  '#3B6D11' : '#bbb'}}>
                      {delta  fmtBRL(valorPeriodo) : '—'}
                    </td>
                    <td style={td()}>
                      <input
                        value={ed?.observacao || ''}
                        onChange={e => setEdit(codigo, { delta: ed?.delta || 0, observacao: e.target.value })}
                        placeholder="opcional…"
                        style={{width:'100%',padding:'2px 4px',fontSize:11,border:'0.5px solid #D0D0CC',borderRadius:3}}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

const th = () => ({ padding:'6px 8px',fontSize:9,fontWeight:500,color:'#555',textAlign:'left',borderBottom:'1px solid #E0E0DC',whiteSpace:'nowrap' })
const td = () => ({ padding:'5px 8px',verticalAlign:'middle' })
