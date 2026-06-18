import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import StatusPill, { getStatus } from '../components/StatusPill'
import { getQcron, updateProgramacao, updateProgramacoesBulk, getSemana, getSemanas, getSubTarefas, createSubTarefa, updateSubTarefa, deleteSubTarefa, getTarefas, adiantarAtividade, removerAdiantada } from '../api'
import { fmtDate } from '../utils/formatters'
import { logError } from '../utils/errors'

export default function MontarQprog() {
  const { semana: semanaParam } = useParams()
  const navigate = useNavigate()
  const [semana, setSemana] = useState(null)
  const [tarefas, setTarefas] = useState([])
  const [semanas, setSemanas] = useState([])
  const [loading, setLoading] = useState(true)
  const [busca, setBusca] = useState('')
  const [filtroStatus, setFiltroStatus] = useState('todas')
  const [filtroDataDe, setFiltroDataDe] = useState('')
  const [filtroDataAte, setFiltroDataAte] = useState('')
  const [filtroSemanaData, setFiltroSemanaData] = useState('')
  const [disciplinasSel, setDisciplinasSel] = useState(new Set(['todas']))
  const [discDropOpen, setDiscDropOpen] = useState(false)
  const [modalTarefa, setModalTarefa] = useState(null)
  const [saving, setSaving] = useState(false)
  const [modalAdiantar, setModalAdiantar] = useState(false)
  const [agruparWbs, setAgruparWbs] = useState(false)
  const [wbsExpanded, setWbsExpanded] = useState(new Set())

  useEffect(() => {
    if (!semanaParam || semanaParam === '—') return
    setLoading(true)
    Promise.all([getSemana(semanaParam), getQcron(semanaParam), getSemanas()])
      .then(([s, q, todas]) => {
        setSemana(s)
        setTarefas(q)
        setSemanas(todas)
      })
      .catch(logError('MontarQprog:loadSemana'))
      .finally(() => setLoading(false))
  }, [semanaParam])

  const disciplinas = [...new Set(tarefas.map(t => t.tarefa?.disciplina).filter(Boolean))]

  const tarefasFiltradas = tarefas.filter(t => {
    const nome = (t.tarefa?.nome || '').toLowerCase()
    const id = (t.tarefa?.activity_id || '').toLowerCase()
    const matchBusca = !busca || nome.includes(busca.toLowerCase()) || id.includes(busca.toLowerCase())
    const matchStatus =
      filtroStatus === 'todas'  true :
      filtroStatus === 'qprog'  t.no_qprog :
      !t.no_qprog
    const matchDisc = disciplinasSel.has('todas') || disciplinasSel.has(t.tarefa?.disciplina)
    // Filtro por intervalo de datas: tarefa cruza o intervalo se inicio_prog <= dateFim E termino_prog >= dateIni
    const de = filtroDataDe || null
    const ate = filtroDataAte || null
    const ini = t.inicio_prog?.slice(0, 10) || null
    const fim = t.termino_prog?.slice(0, 10) || null
    const matchData = (!de && !ate) || (ini && fim && (!de || ini <= ate) && (!ate || fim >= de))
    return matchBusca && matchStatus && matchDisc && matchData
  })

  const qprogCount = tarefas.filter(t => t.no_qprog).length
  const foraCount = tarefas.length - qprogCount
  const pctProgramado = tarefas.length > 0  Math.round(qprogCount / tarefas.length * 100) : 0

  const toggleQprog = useCallback(async (prog) => {
    const novoValor = !prog.no_qprog
    setTarefas(prev => prev.map(t => t.id === prog.id  { ...t, no_qprog: novoValor } : t))
    try {
      await updateProgramacao(semanaParam, prog.id, { no_qprog: novoValor })
    } catch {
      setTarefas(prev => prev.map(t => t.id === prog.id  { ...t, no_qprog: prog.no_qprog } : t))
    }
  }, [semanaParam])

  const [selecionandoTodas, setSelecionandoTodas] = useState(false)

  const selecionarTodas = useCallback(async () => {
    if (selecionandoTodas || tarefasFiltradas.length === 0) return
    const todasMarcadas = tarefasFiltradas.every(t => t.no_qprog)
    const novoValor = !todasMarcadas
    setSelecionandoTodas(true)
    // Atualiza UI imediatamente
    const ids = new Set(tarefasFiltradas.map(t => t.id))
    setTarefas(prev => prev.map(t => ids.has(t.id)  { ...t, no_qprog: novoValor } : t))
    try {
      // Uma única chamada bulk em vez de N PATCHs paralelos
      await updateProgramacoesBulk(semanaParam, [...ids], { no_qprog: novoValor })
    } catch {
      // Reverte em caso de erro
      setTarefas(prev => prev.map(t => ids.has(t.id)  { ...t, no_qprog: !novoValor } : t))
    } finally {
      setSelecionandoTodas(false)
    }
  }, [semanaParam, tarefasFiltradas, selecionandoTodas])

  const onRemoverAdiantada = useCallback(async (prog) => {
    if (!window.confirm(`Remover "${prog.tarefa?.nome}" do adiantamento desta semana?`)) return
    try {
      await removerAdiantada(semanaParam, prog.id)
      setTarefas(prev => prev.filter(t => t.id !== prog.id))
    } catch (e) {
      alert('Erro ao remover: ' + (e.response?.data?.detail || e.message))
    }
  }, [semanaParam])

  const onAdiantar = async (tarefaId) => {
    try {
      const nova = await adiantarAtividade(semanaParam, tarefaId)
      setTarefas(prev => [...prev, nova])
      setModalAdiantar(false)
    } catch (e) {
      const msg = e.response?.data?.detail || e.message
      alert('Erro ao adiantar: ' + msg)
    }
  }

  const salvarModal = async (progId, dados) => {
    setSaving(true)
    try {
      const updated = await updateProgramacao(semanaParam, progId, dados)
      setTarefas(prev => prev.map(t => t.id === progId  { ...t, ...updated } : t))
      setModalTarefa(null)
    } catch (e) {
      alert('Erro ao salvar: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSaving(false)
    }
  }

  const getSemanaForDate = (dateStr) => {
    if (!dateStr || !semanas.length) return null
    const d = dateStr.slice(0, 10)
    return semanas.find(s => s.data_inicio <= d && s.data_fim >= d)?.codigo || null
  }

  const getDisciplineStyle = (disc) => {
    const map = {
      'Civil': 'tag-civil',
      'Caldeiraria': 'tag-caldeiraria',
      'Suprimentos': 'tag-suprimentos',
    }
    return map[disc] || 'tag-civil'
  }

  return (
    <div className="min-h-screen flex flex-col" style={{background:'#F2F2F0'}}>
      {/* Toolbar — linha 1: seletor de semana + busca + status + disciplina */}
      <div className="bg-white flex gap-2.5 items-center flex-wrap px-4 py-2" style={{borderBottom:'0.5px solid #E0E0DC'}}>
        <div style={{fontWeight:500,fontSize:13,color:'#063057',whiteSpace:'nowrap'}}>
          Montar QPROG
        </div>
        <select
          value={semanaParam}
          onChange={e => navigate(`/qprog/${e.target.value}`)}
          className="input-base"
          style={{width:'auto',fontSize:12,fontWeight:500,color:'#063057',minWidth:160}}
        >
          {semanas.map(s => (
            <option key={s.codigo} value={s.codigo}>
              {s.codigo} — {s.data_inicio?.split('-').slice(1).reverse().join('/')} a {s.data_fim?.split('-').slice(1).reverse().join('/')}
            </option>
          ))}
        </select>
        <div style={{width:'0.5px',height:20,background:'#E0E0DC'}} />
        <input
          className="input-base"
          style={{width:200}}
          placeholder="Buscar por ID ou nome..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
        />
        <div style={{width:'0.5px',height:20,background:'#E0E0DC'}} />
        {['todas','qprog','fora'].map(f => (
          <button key={f} onClick={() => setFiltroStatus(f)} style={{
            border: filtroStatus === f  '0.5px solid #185FA5' : '0.5px solid #E0E0DC',
            borderRadius:6, padding:'4px 10px', fontSize:11,
            background: filtroStatus === f  '#E6F1FB' : '#F5F5F2',
            color: filtroStatus === f  '#185FA5' : '#555', cursor:'pointer'
          }}>
            {f === 'todas'  'Todas' : f === 'qprog'  'No QPROG' : 'Fora'}
          </button>
        ))}
        <div style={{width:'0.5px',height:20,background:'#E0E0DC'}} />
        {(() => {
          const todasMarcadas = tarefasFiltradas.length > 0 && tarefasFiltradas.every(t => t.no_qprog)
          return (
            <button
              onClick={selecionarTodas}
              disabled={selecionandoTodas || tarefasFiltradas.length === 0}
              style={{
                fontSize:11, padding:'4px 10px', borderRadius:6, cursor:'pointer',
                border: todasMarcadas  '0.5px solid #3B6D11' : '0.5px solid #185FA5',
                background: todasMarcadas  '#EAF3DE' : '#E6F1FB',
                color: todasMarcadas  '#3B6D11' : '#185FA5',
                whiteSpace:'nowrap', opacity: selecionandoTodas  0.6 : 1,
              }}
            >
              {selecionandoTodas  '...' : todasMarcadas  '✓ Desmarcar todas' : '☑ Selecionar todas'}
            </button>
          )
        })()}
        <div style={{width:'0.5px',height:20,background:'#E0E0DC'}} />
        <div style={{position:'relative'}}>
          <button
            onClick={() => setDiscDropOpen(o => !o)}
            style={{
              fontSize:11, padding:'4px 10px', borderRadius:6, cursor:'pointer',
              border: disciplinasSel.has('todas')  '0.5px solid #E0E0DC' : '0.5px solid #185FA5',
              background: disciplinasSel.has('todas')  '#F5F5F2' : '#E6F1FB',
              color: disciplinasSel.has('todas')  '#555' : '#185FA5',
              whiteSpace:'nowrap',
            }}
          >
            {disciplinasSel.has('todas')
               'Todas as fases ▾'
              : `${disciplinasSel.size} fase(s) ▾`}
          </button>
          {discDropOpen && (
            <div style={{
              position:'absolute', top:'calc(100% + 4px)', left:0, zIndex:50,
              background:'white', border:'0.5px solid #E0E0DC', borderRadius:8,
              boxShadow:'0 4px 16px rgba(0,0,0,0.10)', padding:'6px 0', minWidth:220,
            }}
              onMouseLeave={() => setDiscDropOpen(false)}
            >
              {/* Todas */}
              <label style={{display:'flex',alignItems:'center',gap:8,padding:'5px 12px',cursor:'pointer',fontSize:11}}
                onMouseEnter={e => e.currentTarget.style.background='#F5F5F2'}
                onMouseLeave={e => e.currentTarget.style.background='white'}
              >
                <input type="checkbox" checked={disciplinasSel.has('todas')}
                  onChange={() => setDisciplinasSel(new Set(['todas']))} />
                <span style={{fontWeight:500}}>Todas as fases</span>
              </label>
              <div style={{height:'0.5px',background:'#E0E0DC',margin:'4px 0'}} />
              {disciplinas.map(d => (
                <label key={d} style={{display:'flex',alignItems:'center',gap:8,padding:'5px 12px',cursor:'pointer',fontSize:11}}
                  onMouseEnter={e => e.currentTarget.style.background='#F5F5F2'}
                  onMouseLeave={e => e.currentTarget.style.background='white'}
                >
                  <input type="checkbox"
                    checked={!disciplinasSel.has('todas') && disciplinasSel.has(d)}
                    onChange={() => {
                      setDisciplinasSel(prev => {
                        const next = new Set(prev.has('todas')  [] : prev)
                        if (next.has(d)) {
                          next.delete(d)
                          if (next.size === 0) return new Set(['todas'])
                        } else {
                          next.add(d)
                          if (next.size === disciplinas.length) return new Set(['todas'])
                        }
                        return next
                      })
                    }}
                  />
                  {d}
                </label>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={() => { setAgruparWbs(v => !v); setWbsExpanded(new Set()) }}
          style={{
            fontSize:11, padding:'4px 10px', borderRadius:6, cursor:'pointer',
            border: agruparWbs  '0.5px solid #063057' : '0.5px solid #E0E0DC',
            background: agruparWbs  '#EBF2FA' : '#F5F5F2',
            color: agruparWbs  '#063057' : '#555',
            whiteSpace:'nowrap',
          }}
        >
          {agruparWbs  '⊞ Hierarquia WBS' : '⊟ Hierarquia WBS'}
        </button>
        <button
          onClick={() => setModalAdiantar(true)}
          style={{
            fontSize:11, padding:'4px 10px', borderRadius:6, cursor:'pointer',
            border:'0.5px solid #BA7517', background:'#FAEEDA', color:'#854F0B',
            whiteSpace:'nowrap', marginLeft:'auto',
          }}
        >
          ⚡ Adiantar atividade
        </button>
        <span style={{fontSize:11,color:'#999'}}>
          {tarefasFiltradas.length} de {tarefas.length} tarefas
        </span>
      </div>

      {/* Toolbar — linha 2: filtro por data / semana */}
      <div className="bg-white flex gap-2.5 items-center flex-wrap px-4 py-1.5" style={{borderBottom:'0.5px solid #E0E0DC'}}>
        <span style={{fontSize:10,color:'#999',textTransform:'uppercase',letterSpacing:'0.05em',whiteSpace:'nowrap'}}>Filtrar por data</span>
        <div style={{display:'flex',alignItems:'center',gap:4}}>
          <span style={{fontSize:10,color:'#999'}}>de</span>
          <input type="date" value={filtroDataDe} onChange={e => { setFiltroDataDe(e.target.value); setFiltroSemanaData('') }}
            className="input-base" style={{fontSize:11,width:130}} />
          <span style={{fontSize:10,color:'#999'}}>até</span>
          <input type="date" value={filtroDataAte} onChange={e => { setFiltroDataAte(e.target.value); setFiltroSemanaData('') }}
            className="input-base" style={{fontSize:11,width:130}} />
        </div>
        <div style={{width:'0.5px',height:20,background:'#E0E0DC'}} />
        <span style={{fontSize:10,color:'#999',textTransform:'uppercase',letterSpacing:'0.05em',whiteSpace:'nowrap'}}>ou por semana</span>
        <select
          value={filtroSemanaData}
          onChange={e => {
            const cod = e.target.value
            setFiltroSemanaData(cod)
            if (cod) {
              const s = semanas.find(x => x.codigo === cod)
              if (s) { setFiltroDataDe(s.data_inicio); setFiltroDataAte(s.data_fim) }
            } else {
              setFiltroDataDe(''); setFiltroDataAte('')
            }
          }}
          className="input-base"
          style={{width:'auto',fontSize:11,minWidth:140}}
        >
          <option value="">Todas as semanas</option>
          {semanas.map(s => <option key={s.codigo} value={s.codigo}>{s.codigo} ({s.data_inicio?.split('-').slice(1).reverse().join('/')} a {s.data_fim?.split('-').slice(1).reverse().join('/')})</option>)}
        </select>
        {(filtroDataDe || filtroDataAte) && (
          <button onClick={() => { setFiltroDataDe(''); setFiltroDataAte(''); setFiltroSemanaData('') }}
            style={{fontSize:10,color:'#E05252',background:'none',border:'0.5px solid #E05252',borderRadius:4,padding:'2px 7px',cursor:'pointer'}}>
            ✕ limpar
          </button>
        )}
      </div>

      {/* Table */}
      <div style={{overflowX:'auto',overflowY:'auto',flex:1,maxHeight:'calc(100vh - 220px)'}}>
        {loading  (
          <div className="p-8 text-center" style={{color:'#999'}}>Carregando QCRON...</div>
        ) : tarefas.length === 0  (
          <div className="p-8 text-center">
            <p style={{color:'#555',fontSize:14}}>Nenhuma tarefa no QCRON desta semana.</p>
            <p style={{color:'#999',fontSize:12,marginTop:4}}>Importe um arquivo primeiro.</p>
          </div>
        ) : (
          <table style={{width:'100%',borderCollapse:'collapse',minWidth:900}}>
            <thead>
              <tr style={{background:'#F5F5F2',position:'sticky',top:0,zIndex:3}}>
                {['Status','ID / Nome','Disciplina / Área','Supervisor','Datas QCRON','Semana','% Avanço','QPROG','Observação'].map(h => (
                  <th key={h} style={{padding:'8px 12px',fontSize:10,fontWeight:500,color:'#555',textAlign:'left',borderBottom:'0.5px solid #E0E0DC',whiteSpace:'nowrap'}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {agruparWbs  (() => {
                // ── Modo WBS: árvore completa de hierarquia ─────────────
                const WBS_COLORS = ['#063057','#0D4070','#185FA5','#2070B4','#2880C0']

                function countAll(node) {
                  let n = node.progs.length
                  for (const c of node.children.values()) n += countAll(c)
                  return n
                }

                function buildTree(list) {
                  const root = { children: new Map(), progs: [] }
                  for (const prog of list) {
                    const path = prog.tarefa?.wbs_path || []
                    const levels = path.slice(1) // ignora raiz do projeto
                    let node = root
                    for (const lvl of levels) {
                      if (!node.children.has(lvl)) node.children.set(lvl, { children: new Map(), progs: [] })
                      node = node.children.get(lvl)
                    }
                    node.progs.push(prog)
                  }
                  return root
                }

                const tree = buildTree(tarefasFiltradas)
                const rows = []

                function renderProgRow(prog, indent) {
                  const sIni = getSemanaForDate(prog.inicio_prog)
                  const sFim = getSemanaForDate(prog.termino_prog)
                  return (
                    <tr key={prog.id} style={{background: prog.no_qprog  '#f7fbf2' : 'white', borderBottom:'0.5px solid #E0E0DC'}}
                      onMouseEnter={e => e.currentTarget.style.background = prog.no_qprog  '#eef7e4' : '#F5F5F2'}
                      onMouseLeave={e => e.currentTarget.style.background = prog.no_qprog  '#f7fbf2' : 'white'}
                    >
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        <StatusPill status={getStatus(prog, 'planejamento')} />
                      </td>
                      <td style={{padding:`8px 12px 8px ${12 + indent}px`,verticalAlign:'middle'}}>
                        <div style={{fontFamily:'monospace',fontSize:10,color:'#999'}}>{prog.tarefa?.activity_id}</div>
                        <div style={{display:'flex',alignItems:'center',gap:5,flexWrap:'wrap'}}>
                          <div style={{fontSize:12,color:'#111',lineHeight:1.35,maxWidth:260,cursor:'pointer'}} onClick={() => setModalTarefa(prog)}>
                            {prog.tarefa?.nome}
                          </div>
                          {prog.adiantada && (
                            <span title={prog.semana_original  `Adiantada da ${prog.semana_original}` : 'Atividade adiantada'}
                              style={{display:'inline-flex',alignItems:'center',gap:4,fontSize:9,fontWeight:600,background:'#FAEEDA',color:'#854F0B',border:'0.5px solid #E8C07A',borderRadius:10,padding:'1px 4px 1px 6px',whiteSpace:'nowrap',flexShrink:0}}>
                              ⚡ {prog.semana_original || 'Adiantada'}
                              <button onClick={e => { e.stopPropagation(); onRemoverAdiantada(prog) }} title="Remover adiantamento"
                                style={{background:'rgba(0,0,0,0.1)',border:'none',cursor:'pointer',color:'#854F0B',fontWeight:700,fontSize:9,borderRadius:8,padding:'0px 4px',lineHeight:'14px'}}>×</button>
                            </span>
                          )}
                          {prog.sub_tarefas?.length > 0 && (
                            <span onClick={() => setModalTarefa(prog)} title={`${prog.sub_tarefas.length} sub-tarefa(s)`}
                              style={{display:'inline-flex',alignItems:'center',gap:3,fontSize:9,fontWeight:600,cursor:'pointer',background:'#E6F1FB',color:'#185FA5',border:'0.5px solid #B8D4F0',borderRadius:10,padding:'1px 6px',whiteSpace:'nowrap',flexShrink:0}}>
                              ⊟ {prog.sub_tarefas.length}
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        {prog.tarefa?.disciplina && <span className={`tag ${getDisciplineStyle(prog.tarefa.disciplina)}`}>{prog.tarefa.disciplina}</span>}
                        {prog.tarefa?.area_unidade && <span className="tag tag-area" style={{marginLeft:3}}>{prog.tarefa.area_unidade}</span>}
                      </td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle',fontSize:11,color:'#555'}}>{prog.tarefa?.supervisor || '—'}</td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        <div style={{fontSize:9,color:'#999'}}>Início</div>
                        <div style={{fontSize:11,color:'#555',whiteSpace:'nowrap'}}>{fmtDate(prog.inicio_prog)}</div>
                        <div style={{fontSize:9,color:'#999',marginTop:2}}>Término</div>
                        <div style={{fontSize:11,color:'#555',whiteSpace:'nowrap'}}>{fmtDate(prog.termino_prog)}</div>
                      </td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        <div style={{display:'flex',flexDirection:'column',gap:2}}>
                          {sIni && <span style={{fontSize:10,fontFamily:'monospace',fontWeight:500,color: sIni===semanaParam?'#185FA5':'#555',background: sIni===semanaParam?'#E6F1FB':'#F5F5F2',borderRadius:4,padding:'2px 5px',display:'inline-block'}}>{sIni}</span>}
                          {sFim && sFim !== sIni && <span style={{fontSize:10,fontFamily:'monospace',fontWeight:500,color: sFim===semanaParam?'#185FA5':'#888',background: sFim===semanaParam?'#E6F1FB':'#F5F5F2',borderRadius:4,padding:'2px 5px',display:'inline-block'}}>→ {sFim}</span>}
                          {!sIni && !sFim && <span style={{color:'#ccc',fontSize:10}}>—</span>}
                        </div>
                      </td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        <div style={{display:'flex',flexDirection:'column',gap:2}}>
                          <div style={{display:'flex',alignItems:'center',gap:6}}>
                            <div style={{width:48,height:4,background:'#E0E0DC',borderRadius:3,overflow:'hidden'}}>
                              <div style={{width:`${prog.pct_executado||0}%`,height:'100%',background:'#8dc63f',borderRadius:3}} />
                            </div>
                            <span style={{fontSize:11,color:'#555',minWidth:28}}>{prog.pct_executado||0}%</span>
                            <span style={{fontSize:9,color:'#aaa'}}>exec</span>
                          </div>
                          <div style={{display:'flex',alignItems:'center',gap:6}}>
                            <div style={{width:48,height:4,background:'#E0E0DC',borderRadius:3,overflow:'hidden'}}>
                              <div style={{width:`${prog.pct_avanco||0}%`,height:'100%',background:'#185FA5',borderRadius:3,opacity:0.5}} />
                            </div>
                            <span style={{fontSize:10,color:'#aaa',minWidth:28}}>{prog.pct_avanco||0}%</span>
                            <span style={{fontSize:9,color:'#ccc'}}>prev</span>
                          </div>
                        </div>
                      </td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        <label className="toggle-wrap">
                          <input type="checkbox" checked={prog.no_qprog} onChange={() => toggleQprog(prog)} />
                          <span className="toggle-slider" />
                        </label>
                      </td>
                      <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                        <input defaultValue={prog.observacoes || ''}
                          onBlur={e => updateProgramacao(semanaParam, prog.id, { observacoes: e.target.value })}
                          style={{border:'0.5px solid #E0E0DC',borderRadius:4,padding:'3px 7px',fontSize:11,background:'white',width:140}}
                          placeholder="observação..." />
                      </td>
                    </tr>
                  )
                }

                function renderNode(node, depth, pathKey) {
                  // Nós filhos (grupos WBS)
                  for (const [name, child] of node.children) {
                    const childKey = pathKey  `${pathKey}||${name}` : name
                    const expanded = wbsExpanded.has(childKey)
                    const total = countAll(child)
                    const color = WBS_COLORS[Math.min(depth, WBS_COLORS.length - 1)]
                    const indent = depth * 16
                    rows.push(
                      <tr key={`wbs-${childKey}`} style={{background: color, cursor:'pointer'}}
                        onClick={() => setWbsExpanded(prev => {
                          const next = new Set(prev)
                          if (next.has(childKey)) next.delete(childKey); else next.add(childKey)
                          return next
                        })}
                      >
                        <td colSpan={9} style={{padding:`5px 12px 5px ${12 + indent}px`,color:'white',fontWeight: depth === 0  600 : 500,fontSize: depth === 0  11 : 10}}>
                          <span style={{marginRight:7,fontSize:9,opacity:0.8}}>{expanded  '▼' : '▶'}</span>
                          {name}
                          <span style={{marginLeft:8,fontSize:10,opacity:0.6,fontWeight:400}}>({total})</span>
                        </td>
                      </tr>
                    )
                    if (expanded) {
                      // Atividades diretas deste nó filho
                      child.progs.forEach(prog => rows.push(renderProgRow(prog, (depth + 1) * 16)))
                      // Sub-grupos deste nó filho
                      renderNode(child, depth + 1, childKey)
                    }
                  }
                }

                renderNode(tree, 0, '')
                return rows
              })() : tarefasFiltradas.map(prog => (
                <tr
                  key={prog.id}
                  style={{
                    background: prog.no_qprog  '#f7fbf2' : 'white',
                    borderBottom:'0.5px solid #E0E0DC'
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = prog.no_qprog  '#eef7e4' : '#F5F5F2'}
                  onMouseLeave={e => e.currentTarget.style.background = prog.no_qprog  '#f7fbf2' : 'white'}
                >
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <StatusPill status={getStatus(prog, 'planejamento')} />
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <div style={{fontFamily:'monospace',fontSize:10,color:'#999'}}>{prog.tarefa?.activity_id}</div>
                    <div style={{display:'flex',alignItems:'center',gap:5,flexWrap:'wrap'}}>
                      <div
                        style={{fontSize:12,color:'#111',lineHeight:1.35,maxWidth:260,cursor:'pointer'}}
                        onClick={() => setModalTarefa(prog)}
                      >
                        {prog.tarefa?.nome}
                      </div>
                      {prog.adiantada && (
                        <span
                          title={prog.semana_original  `Adiantada da ${prog.semana_original}` : 'Atividade adiantada'}
                          style={{
                            display:'inline-flex',alignItems:'center',gap:4,
                            fontSize:9,fontWeight:600,
                            background:'#FAEEDA',color:'#854F0B',
                            border:'0.5px solid #E8C07A',
                            borderRadius:10,padding:'1px 4px 1px 6px',whiteSpace:'nowrap',flexShrink:0
                          }}
                        >
                          ⚡ {prog.semana_original || 'Adiantada'}
                          <button
                            onClick={e => { e.stopPropagation(); onRemoverAdiantada(prog) }}
                            title="Remover adiantamento"
                            style={{
                              background:'rgba(0,0,0,0.1)',border:'none',cursor:'pointer',
                              color:'#854F0B',fontWeight:700,fontSize:9,
                              borderRadius:8,padding:'0px 4px',lineHeight:'14px',
                            }}
                          >×</button>
                        </span>
                      )}
                      {prog.sub_tarefas?.length > 0 && (
                        <span
                          onClick={() => setModalTarefa(prog)}
                          title={`${prog.sub_tarefas.length} sub-tarefa(s)`}
                          style={{
                            display:'inline-flex',alignItems:'center',gap:3,
                            fontSize:9,fontWeight:600,cursor:'pointer',
                            background:'#E6F1FB',color:'#185FA5',
                            border:'0.5px solid #B8D4F0',
                            borderRadius:10,padding:'1px 6px',whiteSpace:'nowrap',flexShrink:0
                          }}
                        >
                          ⊟ {prog.sub_tarefas.length}
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    {prog.tarefa?.disciplina && (
                      <span className={`tag ${getDisciplineStyle(prog.tarefa.disciplina)}`}>{prog.tarefa.disciplina}</span>
                    )}
                    {prog.tarefa?.area_unidade && (
                      <span className="tag tag-area" style={{marginLeft:3}}>{prog.tarefa.area_unidade}</span>
                    )}
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle',fontSize:11,color:'#555'}}>
                    {prog.tarefa?.supervisor || '—'}
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <div style={{fontSize:9,color:'#999'}}>Início</div>
                    <div style={{fontSize:11,color:'#555',whiteSpace:'nowrap'}}>{fmtDate(prog.inicio_prog)}</div>
                    <div style={{fontSize:9,color:'#999',marginTop:2}}>Término</div>
                    <div style={{fontSize:11,color:'#555',whiteSpace:'nowrap'}}>{fmtDate(prog.termino_prog)}</div>
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    {(() => {
                      const sIni = getSemanaForDate(prog.inicio_prog)
                      const sFim = getSemanaForDate(prog.termino_prog)
                      return (
                        <div style={{display:'flex',flexDirection:'column',gap:2}}>
                          {sIni && (
                            <span style={{
                              fontSize:10,fontFamily:'monospace',fontWeight:500,
                              color: sIni === semanaParam  '#185FA5' : '#555',
                              background: sIni === semanaParam  '#E6F1FB' : '#F5F5F2',
                              borderRadius:4,padding:'2px 5px',display:'inline-block'
                            }}>{sIni}</span>
                          )}
                          {sFim && sFim !== sIni && (
                            <span style={{
                              fontSize:10,fontFamily:'monospace',fontWeight:500,
                              color: sFim === semanaParam  '#185FA5' : '#888',
                              background: sFim === semanaParam  '#E6F1FB' : '#F5F5F2',
                              borderRadius:4,padding:'2px 5px',display:'inline-block'
                            }}>→ {sFim}</span>
                          )}
                          {!sIni && !sFim && <span style={{color:'#ccc',fontSize:10}}>—</span>}
                        </div>
                      )
                    })()}
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <div style={{display:'flex',flexDirection:'column',gap:2}}>
                      <div style={{display:'flex',alignItems:'center',gap:6}}>
                        <div style={{width:48,height:4,background:'#E0E0DC',borderRadius:3,overflow:'hidden'}}>
                          <div style={{width:`${prog.pct_executado||0}%`,height:'100%',background:'#8dc63f',borderRadius:3}} />
                        </div>
                        <span style={{fontSize:11,color:'#555',minWidth:28}}>{prog.pct_executado||0}%</span>
                        <span style={{fontSize:9,color:'#aaa'}}>exec</span>
                      </div>
                      <div style={{display:'flex',alignItems:'center',gap:6}}>
                        <div style={{width:48,height:4,background:'#E0E0DC',borderRadius:3,overflow:'hidden'}}>
                          <div style={{width:`${prog.pct_avanco||0}%`,height:'100%',background:'#185FA5',borderRadius:3,opacity:0.5}} />
                        </div>
                        <span style={{fontSize:10,color:'#aaa',minWidth:28}}>{prog.pct_avanco||0}%</span>
                        <span style={{fontSize:9,color:'#ccc'}}>prev</span>
                      </div>
                    </div>
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <label className="toggle-wrap">
                      <input
                        type="checkbox"
                        checked={prog.no_qprog}
                        onChange={() => toggleQprog(prog)}
                      />
                      <span className="toggle-slider" />
                    </label>
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <input
                      defaultValue={prog.observacoes || ''}
                      onBlur={e => updateProgramacao(semanaParam, prog.id, { observacoes: e.target.value })}
                      style={{border:'0.5px solid #E0E0DC',borderRadius:4,padding:'3px 7px',fontSize:11,background:'white',width:140}}
                      placeholder="observação..."
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer */}
      <div className="bg-white flex items-center gap-5 flex-wrap px-4 py-2.5" style={{borderTop:'0.5px solid #E0E0DC'}}>
        <FooterStat label="QCRON" value={tarefas.length} />
        <div style={{width:'0.5px',height:32,background:'#E0E0DC'}} />
        <FooterStat label="NO QPROG" value={qprogCount} color="#185FA5" />
        <div style={{width:'0.5px',height:32,background:'#E0E0DC'}} />
        <FooterStat label="FORA" value={foraCount} color="#555" />
        <div style={{width:'0.5px',height:32,background:'#E0E0DC'}} />
        <FooterStat label="% PROGRAMADO" value={pctProgramado + '%'} color={pctProgramado >= 100  '#3B6D11' : '#185FA5'} />
        <button
          className="btn-navy"
          onClick={() => navigate(`/qreal/${semanaParam}`)}
          style={{marginLeft:'auto'}}
        >
          Confirmar QPROG →
        </button>
      </div>

      {/* Modal edição tarefa */}
      {modalTarefa && (
        <TarefaModal
          prog={modalTarefa}
          onClose={() => setModalTarefa(null)}
          onSave={salvarModal}
          saving={saving}
        />
      )}

      {/* Modal adiantar atividade */}
      {modalAdiantar && (
        <AdiantarModal
          semana={semanaParam}
          tarefasJaNaSemana={new Set(tarefas.map(t => t.tarefa_id))}
          onClose={() => setModalAdiantar(false)}
          onConfirm={onAdiantar}
        />
      )}
    </div>
  )
}

function FooterStat({ label, value, color }) {
  return (
    <div style={{display:'flex',flexDirection:'column',gap:1}}>
      <span style={{fontSize:9,color:'#999',textTransform:'uppercase',letterSpacing:'0.05em'}}>{label}</span>
      <span style={{fontSize:15,fontWeight:500,color: color || '#063057'}}>{value}</span>
    </div>
  )
}

function TarefaModal({ prog, onClose, onSave, saving }) {
  // Datas do cronograma (QPROG) ficam congeladas — exibidas apenas para
  // leitura. O planejador preenche inicio_real / termino_real manualmente
  // quando a atividade é executada; essas datas têm prioridade no PDF.
  const cronoInicio = prog.inicio_qprog || prog.inicio_prog || ''
  const cronoTermino = prog.termino_qprog || prog.termino_prog || ''

  const [form, setForm] = useState({
    inicio_real: prog.inicio_real?.slice(0,10) || '',
    termino_real: prog.termino_real?.slice(0,10) || '',
    observacoes: prog.observacoes || '',
  })

  const [subTarefas, setSubTarefas] = useState([])
  const [novaDesc, setNovaDesc] = useState('')
  const [novaInicio, setNovaInicio] = useState('')
  const [novaTermino, setNovaTermino] = useState('')
  const [addingNew, setAddingNew] = useState(false)

  useEffect(() => {
    getSubTarefas(prog.id).then(setSubTarefas).catch(logError(`MontarQprog:getSubTarefas(${prog.id})`))
  }, [prog.id])

  const adicionarSub = async () => {
    if (!novaDesc.trim()) return
    try {
      const sub = await createSubTarefa(prog.id, {
        descricao: novaDesc.trim(),
        status: 'nao_executada',
        inicio_qprog: novaInicio || null,
        termino_qprog: novaTermino || null,
      })
      setSubTarefas(prev => [...prev, sub])
      setNovaDesc('')
      setNovaInicio('')
      setNovaTermino('')
      setAddingNew(false)
    } catch (e) {
      alert('Erro ao criar sub-tarefa')
    }
  }

  const alterarCampo = async (sub, campo, valor) => {
    try {
      const updated = await updateSubTarefa(prog.id, sub.id, { [campo]: valor || null })
      setSubTarefas(prev => prev.map(s => s.id === sub.id  updated : s))
    } catch (e) {
      alert('Erro ao atualizar sub-tarefa')
    }
  }

  const removerSub = async (sub) => {
    try {
      await deleteSubTarefa(prog.id, sub.id)
      setSubTarefas(prev => prev.filter(s => s.id !== sub.id))
    } catch (e) {
      alert('Erro ao remover sub-tarefa')
    }
  }

  const STATUS_SUB = [
    { value: 'nao_executada', label: 'Não Executada', bg: '#F5F5F2', color: '#888'    },
    { value: 'em_andamento',  label: 'Em Andamento',  bg: '#FFF3CD', color: '#BA7517' },
    { value: 'parcial',       label: 'Parcial',       bg: '#FAEEDA', color: '#854F0B' },
    { value: 'concluida',     label: 'Concluída',     bg: '#EAF3DE', color: '#3B6D11' },
  ]

  const getSubStyle = (status) => STATUS_SUB.find(s => s.value === status) || STATUS_SUB[0]

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:100}}>
      <div style={{background:'white',borderRadius:12,border:'0.5px solid #E0E0DC',width:540,maxWidth:'96vw',maxHeight:'90vh',display:'flex',flexDirection:'column'}}>
        {/* Header */}
        <div style={{padding:'14px 18px 12px',borderBottom:'0.5px solid #E0E0DC',display:'flex',justifyContent:'space-between',alignItems:'flex-start',flexShrink:0}}>
          <div>
            <div style={{fontSize:13,fontWeight:500,color:'#111',lineHeight:1.3}}>{prog.tarefa?.nome}</div>
            <div style={{fontSize:10,color:'#999',fontFamily:'monospace',marginTop:2}}>{prog.tarefa?.activity_id}</div>
          </div>
          <button onClick={onClose} style={{background:'none',border:'none',fontSize:18,cursor:'pointer',color:'#999'}}>×</button>
        </div>

        {/* Body — scrollable */}
        <div style={{padding:'16px 18px',display:'flex',flexDirection:'column',gap:14,overflowY:'auto'}}>

          {/* Datas do cronograma (QPROG) — congeladas, só leitura */}
          <div className="grid grid-cols-2 gap-2">
            <label style={{display:'flex',flexDirection:'column',gap:4}}>
              <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Início QPROG (cronograma)</span>
              <input type="date" className="input-base" value={cronoInicio?.slice(0,10) || ''}
                readOnly disabled
                style={{background:'#F5F5F2',color:'#666',cursor:'not-allowed'}} />
            </label>
            <label style={{display:'flex',flexDirection:'column',gap:4}}>
              <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Término QPROG (cronograma)</span>
              <input type="date" className="input-base" value={cronoTermino?.slice(0,10) || ''}
                readOnly disabled
                style={{background:'#F5F5F2',color:'#666',cursor:'not-allowed'}} />
            </label>
          </div>

          {/* Datas REAIS — preenchidas manualmente pelo planejador */}
          <div className="grid grid-cols-2 gap-2">
            <label style={{display:'flex',flexDirection:'column',gap:4}}>
              <span style={{fontSize:10,fontWeight:500,color:'#063057',textTransform:'uppercase',letterSpacing:'0.05em'}}>Início Real</span>
              <input type="date" className="input-base" value={form.inicio_real}
                onChange={e => setForm(f => ({...f, inicio_real: e.target.value}))} />
            </label>
            <label style={{display:'flex',flexDirection:'column',gap:4}}>
              <span style={{fontSize:10,fontWeight:500,color:'#063057',textTransform:'uppercase',letterSpacing:'0.05em'}}>Término Real</span>
              <input type="date" className="input-base" value={form.termino_real}
                onChange={e => setForm(f => ({...f, termino_real: e.target.value}))} />
            </label>
          </div>

          {/* % Executado (read-only, do P6) */}
          <div style={{display:'flex',flexDirection:'column',gap:4}}>
            <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>% de Avanço (Executado P6)</span>
            <div style={{display:'flex',alignItems:'center',gap:10}}>
              <div style={{flex:1,height:6,background:'#E0E0DC',borderRadius:3,overflow:'hidden'}}>
                <div style={{width:`${prog.pct_executado||0}%`,height:'100%',background:'#8dc63f',borderRadius:3}} />
              </div>
              <span style={{fontSize:14,fontWeight:500,color:'#063057',minWidth:40}}>{prog.pct_executado||0}%</span>
            </div>
            <span style={{fontSize:9,color:'#aaa'}}>Valor importado do P6 — atualizado via reimportação</span>
          </div>

          {/* Observações */}
          <label style={{display:'flex',flexDirection:'column',gap:4}}>
            <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Observações</span>
            <textarea className="input-base" rows={2} value={form.observacoes}
              onChange={e => setForm(f => ({...f, observacoes: e.target.value}))} />
          </label>

          {/* Infos */}
          <div className="grid grid-cols-3 gap-2">
            {[
              ['Disciplina', prog.tarefa?.disciplina || '—'],
              ['Área', prog.tarefa?.area_unidade || '—'],
              ['Supervisor', prog.tarefa?.supervisor || '—'],
            ].map(([label, val]) => (
              <div key={label} style={{background:'#F5F5F2',borderRadius:8,padding:'8px 10px'}}>
                <div style={{fontSize:9,color:'#999',marginBottom:2}}>{label}</div>
                <div style={{fontSize:12,color:'#111',fontWeight:500}}>{val}</div>
              </div>
            ))}
          </div>

          {/* Divisor Sub-tarefas */}
          <div style={{height:'0.5px',background:'#E0E0DC'}} />

          {/* Sub-tarefas */}
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
              <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>
                Sub-tarefas {subTarefas.length > 0 && <span style={{fontWeight:400,color:'#aaa'}}>({subTarefas.length})</span>}
              </span>
              {!addingNew && (
                <button
                  onClick={() => setAddingNew(true)}
                  style={{fontSize:10,color:'#185FA5',background:'none',border:'0.5px solid #185FA5',borderRadius:4,padding:'2px 8px',cursor:'pointer'}}
                >
                  + Adicionar
                </button>
              )}
            </div>

            {subTarefas.length === 0 && !addingNew && (
              <div style={{fontSize:11,color:'#bbb',textAlign:'center',padding:'8px 0'}}>
                Nenhuma sub-tarefa cadastrada
              </div>
            )}

            {subTarefas.map(sub => {
              const st = getSubStyle(sub.status)
              return (
                <div key={sub.id} style={{
                  padding:'10px 12px',borderRadius:8,
                  border:'0.5px solid #E0E0DC',background:'#FAFAF8',
                  display:'flex',flexDirection:'column',gap:8
                }}>
                  {/* Linha 1: descrição + remover */}
                  <div style={{display:'flex',alignItems:'flex-start',gap:6}}>
                    <span style={{fontSize:12,color:'#222',flex:1,lineHeight:1.35}}>{sub.descricao}</span>
                    <button
                      onClick={() => removerSub(sub)}
                      style={{background:'none',border:'none',cursor:'pointer',color:'#ccc',fontSize:14,padding:'0 2px',lineHeight:1,flexShrink:0}}
                      title="Remover"
                    >×</button>
                  </div>
                  {/* Linha 2: status + datas */}
                  <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
                    <select
                      value={sub.status}
                      onChange={e => alterarCampo(sub, 'status', e.target.value)}
                      style={{
                        fontSize:10,fontWeight:500,border:'none',borderRadius:6,padding:'3px 6px',
                        background:st.bg,color:st.color,cursor:'pointer',outline:'none',flexShrink:0
                      }}
                    >
                      {STATUS_SUB.map(s => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                    <div style={{display:'flex',alignItems:'center',gap:4,marginLeft:'auto'}}>
                      <span style={{fontSize:9,color:'#aaa',whiteSpace:'nowrap'}}>Início</span>
                      <input
                        type="date"
                        className="input-base"
                        style={{fontSize:10,width:120,padding:'2px 6px'}}
                        value={sub.inicio_qprog?.slice(0,10) || ''}
                        onChange={e => alterarCampo(sub, 'inicio_qprog', e.target.value)}
                      />
                      <span style={{fontSize:9,color:'#aaa',whiteSpace:'nowrap'}}>Término</span>
                      <input
                        type="date"
                        className="input-base"
                        style={{fontSize:10,width:120,padding:'2px 6px'}}
                        value={sub.termino_qprog?.slice(0,10) || ''}
                        onChange={e => alterarCampo(sub, 'termino_qprog', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              )
            })}

            {/* Formulário para nova sub-tarefa */}
            {addingNew && (
              <div style={{padding:'10px 12px',borderRadius:8,border:'0.5px dashed #185FA5',background:'#F0F7FF',display:'flex',flexDirection:'column',gap:8}}>
                <input
                  autoFocus
                  className="input-base"
                  style={{fontSize:12}}
                  placeholder="Descrição da sub-tarefa..."
                  value={novaDesc}
                  onChange={e => setNovaDesc(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') adicionarSub()
                    if (e.key === 'Escape') { setAddingNew(false); setNovaDesc(''); setNovaInicio(''); setNovaTermino('') }
                  }}
                />
                <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap'}}>
                  <span style={{fontSize:9,color:'#aaa'}}>Início</span>
                  <input type="date" className="input-base" style={{fontSize:10,width:120,padding:'2px 6px'}}
                    value={novaInicio} onChange={e => setNovaInicio(e.target.value)} />
                  <span style={{fontSize:9,color:'#aaa'}}>Término</span>
                  <input type="date" className="input-base" style={{fontSize:10,width:120,padding:'2px 6px'}}
                    value={novaTermino} onChange={e => setNovaTermino(e.target.value)} />
                  <div style={{marginLeft:'auto',display:'flex',gap:6}}>
                    <button onClick={adicionarSub} className="btn-navy" style={{fontSize:11,padding:'4px 14px'}}>OK</button>
                    <button
                      onClick={() => { setAddingNew(false); setNovaDesc(''); setNovaInicio(''); setNovaTermino('') }}
                      style={{fontSize:11,padding:'4px 10px',background:'none',border:'0.5px solid #D0D0CC',borderRadius:6,cursor:'pointer',color:'#555'}}
                    >✕</button>
                  </div>
                </div>
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div style={{padding:'10px 18px',borderTop:'0.5px solid #E0E0DC',display:'flex',justifyContent:'flex-end',gap:8,flexShrink:0}}>
          <button onClick={onClose} style={{background:'none',border:'0.5px solid #D0D0CC',color:'#555',padding:'6px 14px',borderRadius:6,fontSize:12,cursor:'pointer'}}>
            Cancelar
          </button>
          <button
            onClick={() => onSave(prog.id, {
              inicio_real: form.inicio_real || null,
              termino_real: form.termino_real || null,
              observacoes: form.observacoes,
            })}
            disabled={saving}
            className="btn-navy"
          >
            {saving  'Salvando...' : 'Salvar'}
          </button>
        </div>
      </div>
    </div>
  )
}

function AdiantarModal({ semana, tarefasJaNaSemana, onClose, onConfirm }) {
  const [busca, setBusca] = useState('')
  const [resultados, setResultados] = useState([])
  const [buscando, setBuscando] = useState(false)
  const [selecionada, setSelecionada] = useState(null)
  const [confirmando, setConfirmando] = useState(false)

  useEffect(() => {
    if (!busca.trim() || busca.length < 2) { setResultados([]); return }
    setBuscando(true)
    const timer = setTimeout(() => {
      getTarefas({ busca })
        .then(res => setResultados(res.filter(t => !tarefasJaNaSemana.has(t.id))))
        .catch(logError('MontarQprog:getTarefas'))
        .finally(() => setBuscando(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [busca])

  const confirmar = async () => {
    if (!selecionada) return
    setConfirmando(true)
    try {
      await onConfirm(selecionada.id)
    } finally {
      setConfirmando(false)
    }
  }

  const getDisciplineColor = (disc) => {
    const map = { 'Civil': '#185FA5', 'Caldeiraria': '#854F0B', 'Suprimentos': '#3B6D11' }
    return map[disc] || '#555'
  }

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:110}}>
      <div style={{background:'white',borderRadius:12,border:'0.5px solid #E0E0DC',width:520,maxWidth:'96vw',maxHeight:'85vh',display:'flex',flexDirection:'column'}}>
        {/* Header */}
        <div style={{padding:'14px 18px 12px',borderBottom:'0.5px solid #E0E0DC',display:'flex',justifyContent:'space-between',alignItems:'center',flexShrink:0}}>
          <div>
            <div style={{fontSize:13,fontWeight:500,color:'#111'}}>⚡ Adiantar atividade</div>
            <div style={{fontSize:10,color:'#999',marginTop:2}}>Semana <strong>{semana}</strong> — busque uma atividade de outra semana</div>
          </div>
          <button onClick={onClose} style={{background:'none',border:'none',fontSize:18,cursor:'pointer',color:'#999'}}>×</button>
        </div>

        {/* Busca */}
        <div style={{padding:'12px 18px',borderBottom:'0.5px solid #E0E0DC',flexShrink:0}}>
          <input
            autoFocus
            className="input-base"
            style={{width:'100%',fontSize:12}}
            placeholder="Buscar por ID ou nome da atividade..."
            value={busca}
            onChange={e => { setBusca(e.target.value); setSelecionada(null) }}
          />
          {busca.length > 0 && busca.length < 2 && (
            <div style={{fontSize:10,color:'#aaa',marginTop:4}}>Digite pelo menos 2 caracteres</div>
          )}
        </div>

        {/* Resultados */}
        <div style={{overflowY:'auto',flex:1,padding:'8px 0'}}>
          {buscando && (
            <div style={{fontSize:11,color:'#aaa',textAlign:'center',padding:'16px 0'}}>Buscando...</div>
          )}
          {!buscando && busca.length >= 2 && resultados.length === 0 && (
            <div style={{fontSize:11,color:'#bbb',textAlign:'center',padding:'16px 0'}}>Nenhuma atividade encontrada fora desta semana</div>
          )}
          {!buscando && busca.length < 2 && (
            <div style={{fontSize:11,color:'#ccc',textAlign:'center',padding:'16px 0'}}>Use a busca acima para encontrar atividades</div>
          )}
          {resultados.map(t => {
            const isSel = selecionada?.id === t.id
            return (
              <div
                key={t.id}
                onClick={() => setSelecionada(isSel  null : t)}
                style={{
                  padding:'10px 18px',cursor:'pointer',
                  background: isSel  '#FFF8EE' : 'white',
                  borderLeft: isSel  '3px solid #BA7517' : '3px solid transparent',
                  borderBottom:'0.5px solid #F0F0EC',
                }}
                onMouseEnter={e => { if (!isSel) e.currentTarget.style.background='#FAFAF8' }}
                onMouseLeave={e => { if (!isSel) e.currentTarget.style.background='white' }}
              >
                <div style={{display:'flex',alignItems:'center',gap:8}}>
                  <span style={{fontFamily:'monospace',fontSize:10,color:'#999',flexShrink:0}}>{t.activity_id}</span>
                  {t.disciplina && (
                    <span style={{fontSize:9,fontWeight:600,color:getDisciplineColor(t.disciplina),background:'#F5F5F2',borderRadius:4,padding:'1px 5px',flexShrink:0}}>
                      {t.disciplina}
                    </span>
                  )}
                </div>
                <div style={{fontSize:12,color:'#222',marginTop:3,lineHeight:1.3}}>{t.nome}</div>
                {t.area_unidade && <div style={{fontSize:10,color:'#aaa',marginTop:2}}>{t.area_unidade}</div>}
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div style={{padding:'10px 18px',borderTop:'0.5px solid #E0E0DC',display:'flex',alignItems:'center',gap:8,flexShrink:0}}>
          {selecionada && (
            <div style={{flex:1,fontSize:11,color:'#854F0B',background:'#FAEEDA',borderRadius:6,padding:'4px 10px',lineHeight:1.3}}>
              <strong>{selecionada.activity_id}</strong> — {selecionada.nome}
            </div>
          )}
          {!selecionada && <div style={{flex:1}} />}
          <button onClick={onClose} style={{background:'none',border:'0.5px solid #D0D0CC',color:'#555',padding:'6px 14px',borderRadius:6,fontSize:12,cursor:'pointer'}}>
            Cancelar
          </button>
          <button
            onClick={confirmar}
            disabled={!selecionada || confirmando}
            style={{
              padding:'6px 16px',borderRadius:6,fontSize:12,cursor: selecionada  'pointer' : 'not-allowed',
              background: selecionada  '#BA7517' : '#E0D0B0',
              color: 'white', border:'none', fontWeight:500,
              opacity: confirmando  0.7 : 1,
            }}
          >
            {confirmando  'Adiantando...' : '⚡ Confirmar adiantamento'}
          </button>
        </div>
      </div>
    </div>
  )
}
