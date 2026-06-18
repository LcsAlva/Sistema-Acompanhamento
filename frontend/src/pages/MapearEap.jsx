// Página "Mapear EAP" — vincula tarefas do P6 a itens-folha da EAP financeira.
//
// Funciona em duas colunas:
//   - Esquerda: tarefas do P6 (não vinculadas em destaque, vinculadas com check)
//   - Direita: itens-folha da EAP, com busca
// Botão "Auto-mapear" sugere vínculos por similaridade de descrição.

import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  getEapItens,
  getEapLinks,
  createEapLink,
  deleteEapLink,
  autoMapearEap,
  getTarefas,
} from '../api'
import { logError } from '../utils/errors'

const fmtBRL = (v) => 'R$ ' + (v  0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })

export default function MapearEap() {
  const [tarefas, setTarefas] = useState([])
  const [folhas, setFolhas] = useState([])
  const [links, setLinks] = useState([])
  const [tarefaSel, setTarefaSel] = useState(null)
  const [buscaTarefa, setBuscaTarefa] = useState('')
  const [buscaEap, setBuscaEap] = useState('')
  const [filtroNaoMapeadas, setFiltroNaoMapeadas] = useState(true)
  const [sugestoes, setSugestoes] = useState({})  // {tarefa_id: [sugestoes]}
  const [loading, setLoading] = useState(true)
  const [salvando, setSalvando] = useState(false)

  const carregar = () => {
    setLoading(true)
    Promise.all([
      getTarefas({ limit: 5000 }).catch(() => []),
      getEapItens({ so_folhas: true, limit: 2000 }),
      getEapLinks(),
    ])
      .then(([t, f, l]) => {
        setTarefas(Array.isArray(t)  t : (t.itens || []))
        setFolhas(f)
        setLinks(l)
      })
      .catch(logError('MapearEap:carregar'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { carregar() }, [])

  // Index: tarefa_id -> [link, …]
  const linksPorTarefa = useMemo(() => {
    const m = {}
    for (const l of links) {
      if (!m[l.tarefa_id]) m[l.tarefa_id] = []
      m[l.tarefa_id].push(l)
    }
    return m
  }, [links])

  // Index: codigo eap -> item completo
  const folhaPorCodigo = useMemo(() => {
    const m = {}
    folhas.forEach(f => { m[f.codigo] = f })
    return m
  }, [folhas])

  const tarefasFiltradas = useMemo(() => {
    let arr = tarefas
    if (filtroNaoMapeadas) arr = arr.filter(t => !linksPorTarefa[t.id])
    if (buscaTarefa.trim()) {
      const q = buscaTarefa.toLowerCase()
      arr = arr.filter(t =>
        (t.nome || '').toLowerCase().includes(q) ||
        (t.activity_id || '').toLowerCase().includes(q)
      )
    }
    return arr.slice(0, 500)
  }, [tarefas, linksPorTarefa, filtroNaoMapeadas, buscaTarefa])

  const folhasFiltradas = useMemo(() => {
    if (!buscaEap.trim()) return folhas.slice(0, 200)
    const q = buscaEap.toLowerCase()
    return folhas
      .filter(f =>
        (f.descricao || '').toLowerCase().includes(q) ||
        (f.codigo || '').startsWith(buscaEap)
      )
      .slice(0, 300)
  }, [folhas, buscaEap])

  const handleVincular = async (eap_codigo) => {
    if (!tarefaSel) {
      alert('Selecione uma tarefa primeiro.')
      return
    }
    setSalvando(true)
    try {
      const novoLink = await createEapLink({
        tarefa_id: tarefaSel.id,
        eap_codigo,
        peso: 1.0,
      })
      setLinks(prev => [...prev, novoLink])
      // Remove sugestões da tarefa recém vinculada
      setSugestoes(prev => { const n = { ...prev }; delete n[tarefaSel.id]; return n })
    } catch (e) {
      alert('Erro ao vincular: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const handleDesvincular = async (link_id) => {
    if (!confirm('Remover este vínculo?')) return
    try {
      await deleteEapLink(link_id)
      setLinks(prev => prev.filter(l => l.id !== link_id))
    } catch (e) {
      alert('Erro ao desvincular: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleAutoMapear = async () => {
    if (!confirm('Gerar sugestões de mapeamento para tarefas não vinculadas Isso pode levar alguns segundos.')) return
    setSalvando(true)
    try {
      const sug = await autoMapearEap(3)
      const map = {}
      for (const s of sug) map[s.tarefa_id] = s.sugestoes
      setSugestoes(map)
      alert(`${Object.keys(map).length} tarefas com sugestões. Veja em destaque na lista.`)
    } catch (e) {
      alert('Erro ao auto-mapear: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const handleAplicarSugestao = async (tarefa, eap_codigo) => {
    setSalvando(true)
    try {
      const novoLink = await createEapLink({ tarefa_id: tarefa.id, eap_codigo, peso: 1.0 })
      setLinks(prev => [...prev, novoLink])
      setSugestoes(prev => { const n = { ...prev }; delete n[tarefa.id]; return n })
    } catch (e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="min-h-screen p-4" style={{background:'#F2F2F0'}}>
      <div className="flex items-center gap-3 mb-3">
        <h1 style={{fontSize:18,fontWeight:600,color:'#063057'}}>Mapear Tarefas ↔ EAP Financeira</h1>
        <span style={{fontSize:11,color:'#777'}}>
          {tarefas.length} tarefas · {folhas.length} folhas EAP · {links.length} vínculos
        </span>
        <div style={{marginLeft:'auto',display:'flex',gap:8}}>
          <button
            onClick={handleAutoMapear}
            disabled={salvando}
            className="btn-navy"
            style={{background:'#185FA5'}}
          >
            ✨ Auto-mapear
          </button>
          <Link to="/financeiro" className="btn-navy" style={{background:'#3B6D11'}}>
            📊 Avanço Financeiro
          </Link>
        </div>
      </div>

      {loading  (
        <div className="card text-center" style={{padding:40,color:'#999'}}>Carregando…</div>
      ) : (
        <div className="grid grid-cols-2 gap-3" style={{height:'calc(100vh - 110px)'}}>
          {/* COLUNA TAREFAS */}
          <div className="card" style={{display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{display:'flex',gap:8,marginBottom:8,alignItems:'center'}}>
              <input
                className="input-base" placeholder="Buscar tarefa…" style={{flex:1}}
                value={buscaTarefa} onChange={e => setBuscaTarefa(e.target.value)}
              />
              <label style={{display:'flex',alignItems:'center',gap:4,fontSize:11,color:'#555',whiteSpace:'nowrap'}}>
                <input type="checkbox" checked={filtroNaoMapeadas} onChange={e => setFiltroNaoMapeadas(e.target.checked)} />
                só não mapeadas
              </label>
            </div>
            <div style={{overflow:'auto',flex:1}}>
              {tarefasFiltradas.length === 0  (
                <p style={{color:'#999',fontSize:12,fontStyle:'italic',padding:8}}>
                  {filtroNaoMapeadas  'Todas as tarefas já estão mapeadas 🎉' : 'Nenhuma tarefa.'}
                </p>
              ) : (
                tarefasFiltradas.map(t => {
                  const myLinks = linksPorTarefa[t.id] || []
                  const isSel = tarefaSel?.id === t.id
                  const sug = sugestoes[t.id]
                  return (
                    <div key={t.id}
                      onClick={() => setTarefaSel(t)}
                      style={{
                        padding:'7px 10px',
                        borderRadius:4,
                        cursor:'pointer',
                        background: isSel  '#FFF5E0' : (myLinks.length > 0  '#F7FBF2' : 'white'),
                        border: isSel  '1.5px solid #FFA500' : '0.5px solid #E0E0DC',
                        marginBottom:4,
                      }}>
                      <div style={{display:'flex',alignItems:'flex-start',gap:8}}>
                        <span style={{fontFamily:'monospace',fontSize:9,color:'#999'}}>{t.activity_id}</span>
                        {myLinks.length > 0 && <span style={{fontSize:9,color:'#3B6D11',fontWeight:600}}>✓ {myLinks.length}</span>}
                      </div>
                      <div style={{fontSize:11,color:'#222',lineHeight:1.3,marginTop:2}}>{t.nome}</div>
                      <div style={{fontSize:9,color:'#888',marginTop:2}}>
                        {t.disciplina || '—'} · {t.area_unidade || '—'}
                      </div>
                      {/* Vínculos atuais */}
                      {myLinks.map(l => {
                        const f = folhaPorCodigo[l.eap_codigo]
                        return (
                          <div key={l.id} style={{
                            marginTop:4,padding:'3px 6px',background:'#EAF3DE',borderRadius:3,
                            display:'flex',alignItems:'center',gap:6,fontSize:10,
                          }}>
                            <span style={{fontFamily:'monospace',color:'#3B6D11',fontWeight:600}}>{l.eap_codigo}</span>
                            <span style={{flex:1,color:'#333'}}>{f?.descricao || '?'}</span>
                            <span style={{color:'#777'}}>{f && fmtBRL(f.valor)}</span>
                            <button
                              onClick={e => { e.stopPropagation(); handleDesvincular(l.id) }}
                              style={{background:'none',border:'none',cursor:'pointer',color:'#A32D2D',fontSize:13}}
                              title="Remover vínculo"
                            >×</button>
                          </div>
                        )
                      })}
                      {/* Sugestões automáticas */}
                      {sug && sug.length > 0 && myLinks.length === 0 && (
                        <div style={{marginTop:4}}>
                          <div style={{fontSize:9,color:'#185FA5',fontWeight:600,marginBottom:2}}>Sugestões:</div>
                          {sug.map(s => (
                            <div key={s.eap_codigo}
                                 onClick={e => { e.stopPropagation(); handleAplicarSugestao(t, s.eap_codigo) }}
                                 style={{
                                   padding:'2px 6px',background:'#E6F1FB',borderRadius:3,
                                   display:'flex',alignItems:'center',gap:6,fontSize:10,
                                   cursor:'pointer',marginBottom:2,
                                 }}>
                              <span style={{fontFamily:'monospace',color:'#185FA5',fontWeight:600}}>{s.eap_codigo}</span>
                              <span style={{flex:1,color:'#333'}}>{s.descricao}</span>
                              <span style={{color:'#3B6D11',fontWeight:600,minWidth:36,textAlign:'right'}}>
                                {Math.round(s.score * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          </div>

          {/* COLUNA EAP */}
          <div className="card" style={{display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{display:'flex',gap:8,marginBottom:8,alignItems:'center'}}>
              <input
                className="input-base" placeholder="Buscar item EAP (descrição ou código)…" style={{flex:1}}
                value={buscaEap} onChange={e => setBuscaEap(e.target.value)}
              />
              {tarefaSel && (
                <span style={{fontSize:10,color:'#FFA500',fontWeight:600,whiteSpace:'nowrap'}}>
                  ↳ vincular a: {tarefaSel.nome?.slice(0, 30)}
                </span>
              )}
            </div>
            <div style={{overflow:'auto',flex:1}}>
              {folhasFiltradas.map(f => (
                <div key={f.codigo}
                     onClick={() => handleVincular(f.codigo)}
                     style={{
                       padding:'7px 10px',
                       borderRadius:4,
                       cursor: tarefaSel  'pointer' : 'default',
                       background: 'white',
                       border:'0.5px solid #E0E0DC',
                       marginBottom:4,
                       opacity: tarefaSel  1 : 0.7,
                     }}
                     onMouseEnter={e => { if (tarefaSel) e.currentTarget.style.background = '#FFF5E0' }}
                     onMouseLeave={e => e.currentTarget.style.background = 'white'}
                >
                  <div style={{display:'flex',alignItems:'flex-start',gap:8}}>
                    <span style={{fontFamily:'monospace',fontSize:10,color:'#185FA5',fontWeight:600,minWidth:60}}>{f.codigo}</span>
                    <span style={{flex:1,fontSize:11,color:'#222',lineHeight:1.3}}>{f.descricao}</span>
                    <span style={{fontSize:10,color:'#3B6D11',fontWeight:600,whiteSpace:'nowrap'}}>{fmtBRL(f.valor)}</span>
                  </div>
                </div>
              ))}
            </div>
            {!tarefaSel && (
              <div style={{padding:8,fontSize:10,color:'#999',fontStyle:'italic',borderTop:'0.5px solid #E0E0DC'}}>
                Clique numa tarefa à esquerda para selecioná-la, depois clique num item da EAP para vincular.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
