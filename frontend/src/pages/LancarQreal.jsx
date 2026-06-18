import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getQprog, updateProgramacao, fecharSemana, getSemana } from '../api'
import { useSemana } from '../context/SemanaContext'
import { logError } from '../utils/errors'

export default function LancarQreal() {
  const { semana: semanaParam } = useParams()
  const navigate = useNavigate()
  const { semanas, refetchSemanas } = useSemana()
  const [tarefas, setTarefas] = useState([])
  const [semanaObj, setSemanaObj] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busca, setBusca] = useState('')
  const [filtro, setFiltro] = useState('todas')
  const [salvando, setSalvando] = useState(false)
  const [fechando, setFechando] = useState(false)

  useEffect(() => {
    if (!semanaParam || semanaParam === '—') return
    setLoading(true)
    Promise.all([getSemana(semanaParam), getQprog(semanaParam)])
      .then(([s, data]) => {
        setSemanaObj(s)
        setTarefas(data.map(t => ({
          ...t,
          _status: t.qreal_concluida  'conc' : t.pct_qreal > 0  'parc' : null,
          _pct: t.pct_qreal || 50,
        })))
      })
      .catch(logError('LancarQreal:loadSemana'))
      .finally(() => setLoading(false))
  }, [semanaParam])

  const setStatus = (id, status) => {
    setTarefas(prev => prev.map(t => t.id === id
       { ...t, _status: t._status === status  null : status }
      : t
    ))
  }

  const setPct = (id, pct) => {
    setTarefas(prev => prev.map(t => t.id === id  { ...t, _pct: pct } : t))
  }

  const concluidas = tarefas.filter(t => t._status === 'conc').length
  const parciais = tarefas.filter(t => t._status === 'parc').length
  const naoExec = tarefas.filter(t => t._status === 'nao').length
  const pendentes = tarefas.filter(t => !t._status).length
  const ic = tarefas.length > 0  Math.round(concluidas / tarefas.length * 100) : 0
  const icColor = ic >= 100  '#3B6D11' : ic >= 70  '#BA7517' : '#A32D2D'

  const tarefasFiltradas = tarefas.filter(t => {
    const match = !busca || (t.tarefa?.nome || '').toLowerCase().includes(busca.toLowerCase())
    const matchF =
      filtro === 'todas'  true :
      filtro === 'pendentes'  !t._status :
      filtro === 'conc'  t._status === 'conc' :
      filtro === 'parc'  t._status === 'parc' :
      t._status === 'nao'
    return match && matchF
  })

  const salvar = async () => {
    if (pendentes > 0) {
      if (!confirm(`Ainda há ${pendentes} tarefa(s) pendentes. Salvar assim mesmo?`)) return
    }
    setSalvando(true)
    try {
      await Promise.all(tarefas.map(t => {
        const isConc = t._status === 'conc'
        const pctReal = t._status === 'conc'  100 : t._status === 'parc'  t._pct : 0
        return updateProgramacao(semanaParam, t.id, {
          qreal_concluida: isConc,
          pct_qreal: pctReal,
        })
      }))
      navigate('/dashboard')
    } catch (e) {
      alert('Erro ao salvar: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  const handleFechar = async () => {
    if (!confirm(`Fechar a semana ${semanaParam} Os indicadores serão congelados e não poderão ser alterados automaticamente.`)) return
    setFechando(true)
    try {
      await fecharSemana(semanaParam)
      await refetchSemanas()
      setSemanaObj(prev => ({ ...prev, fechada: true }))
      alert(`Semana ${semanaParam} fechada com sucesso!`)
    } catch (e) {
      alert('Erro ao fechar semana: ' + (e.response?.data?.detail || e.message))
    } finally {
      setFechando(false)
    }
  }

  const fmtDate = (d) => { if (!d) return '—'; const [y,m,day]=d.split('-'); return `${day}/${m}` }

  const rowBg = (status) => {
    if (status === 'conc') return '#f7fbf2'
    if (status === 'parc') return '#fffbf5'
    if (status === 'nao') return '#fff9f9'
    return 'white'
  }

  return (
    <div className="min-h-screen flex flex-col" style={{background:'#F2F2F0'}}>
      {/* KPI bar */}
      <div className="bg-white px-4 py-2.5 flex items-center gap-4 flex-wrap" style={{borderBottom:'0.5px solid #E0E0DC'}}>
        <div style={{fontWeight:500,fontSize:13,color:'#063057',whiteSpace:'nowrap'}}>Lançar QREAL</div>
        <select
          value={semanaParam}
          onChange={e => navigate(`/qreal/${e.target.value}`)}
          className="input-base"
          style={{width:'auto',fontSize:12,fontWeight:500,color:'#063057',minWidth:160}}
        >
          {semanas.map(s => (
            <option key={s.codigo} value={s.codigo}>
              {s.codigo} — {s.data_inicio?.split('-').slice(1).reverse().join('/')} a {s.data_fim?.split('-').slice(1).reverse().join('/')}
            </option>
          ))}
        </select>
        <div style={{width:'0.5px',height:24,background:'#E0E0DC'}} />
        {[
          ['QPROG', tarefas.length, '#063057'],
          ['Concluídas', concluidas, '#3B6D11'],
          ['Parciais', parciais, '#BA7517'],
          ['Não exec.', naoExec, '#A32D2D'],
          ['Pendentes', pendentes, '#999'],
        ].map(([l, v, c]) => (
          <div key={l} style={{display:'flex',flexDirection:'column',gap:1}}>
            <span style={{fontSize:9,color:'#999',textTransform:'uppercase',letterSpacing:'0.05em'}}>{l}</span>
            <span style={{fontSize:15,fontWeight:500,color:c}}>{v}</span>
          </div>
        ))}
        <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
          <span style={{fontSize:11,color:'#555'}}>IC: <strong style={{color:icColor}}>{ic}%</strong></span>
          <div style={{width:100,height:7,background:'#E0E0DC',borderRadius:4,overflow:'hidden'}}>
            <div style={{width:`${Math.min(ic,100)}%`,height:'100%',background:icColor,borderRadius:4}} />
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-white px-4 py-2 flex gap-2 items-center flex-wrap" style={{borderBottom:'0.5px solid #E0E0DC'}}>
        <input
          className="input-base"
          style={{width:220}}
          placeholder="Buscar tarefa..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
        />
        {['todas','pendentes','conc','parc','nao'].map(f => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            style={{
              border: filtro === f  '0.5px solid #185FA5' : '0.5px solid #E0E0DC',
              borderRadius:6, padding:'5px 10px', fontSize:11,
              background: filtro === f  '#E6F1FB' : '#F5F5F2',
              color: filtro === f  '#185FA5' : '#555', cursor:'pointer'
            }}
          >
            {f === 'todas'  'Todas' : f === 'pendentes'  'Pendentes' : f === 'conc'  'Concluídas' : f === 'parc'  'Parciais' : 'Não exec.'}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{overflowX:'auto',overflowY:'auto',flex:1,maxHeight:'calc(100vh - 200px)'}}>
        {loading  (
          <div className="p-8 text-center" style={{color:'#999'}}>Carregando QPROG...</div>
        ) : tarefas.length === 0  (
          <div className="p-8 text-center">
            <p style={{color:'#555',fontSize:14}}>Nenhuma tarefa no QPROG desta semana.</p>
          </div>
        ) : (
          <table style={{width:'100%',borderCollapse:'collapse',minWidth:800}}>
            <thead>
              <tr style={{background:'#F5F5F2',position:'sticky',top:0,zIndex:3}}>
                {['ID / Nome','Disciplina / Área','Supervisor','Período QPROG','Status','% Real','Observação'].map(h => (
                  <th key={h} style={{padding:'8px 12px',fontSize:10,fontWeight:500,color:'#555',textAlign:'left',borderBottom:'0.5px solid #E0E0DC',whiteSpace:'nowrap'}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tarefasFiltradas.map(prog => (
                <tr key={prog.id} style={{background:rowBg(prog._status),borderBottom:'0.5px solid #E0E0DC'}}>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <div style={{fontFamily:'monospace',fontSize:10,color:'#999'}}>{prog.tarefa?.activity_id}</div>
                    <div style={{fontSize:12,color:'#111',lineHeight:1.35,maxWidth:260}}>{prog.tarefa?.nome}</div>
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    {prog.tarefa?.disciplina && <span className="tag tag-civil">{prog.tarefa.disciplina}</span>}
                    {prog.tarefa?.area_unidade && <span className="tag tag-area" style={{marginLeft:3}}>{prog.tarefa.area_unidade}</span>}
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle',fontSize:11,color:'#555'}}>{prog.tarefa?.supervisor || '—'}</td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle',fontSize:11,color:'#555',whiteSpace:'nowrap'}}>
                    {fmtDate(prog.inicio_qprog || prog.inicio_prog)} → {fmtDate(prog.termino_qprog || prog.termino_prog)}
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle'}}>
                    <div style={{display:'flex',gap:4}}>
                      {[
                        ['conc', '#EAF3DE', '#3B6D11', 'Concluída'],
                        ['parc', '#FAEEDA', '#854F0B', 'Parcial'],
                        ['nao',  '#FCEBEB', '#A32D2D', 'Não exec.'],
                      ].map(([s, bg, color, label]) => (
                        <button
                          key={s}
                          onClick={() => setStatus(prog.id, s)}
                          style={{
                            padding:'3px 8px', borderRadius:4, fontSize:10, fontWeight:500, cursor:'pointer',
                            background: prog._status === s  bg : '#F5F5F2',
                            color: prog._status === s  color : '#999',
                            border: `0.5px solid ${prog._status === s  color : '#E0E0DC'}`,
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </td>
                  <td style={{padding:'8px 12px',verticalAlign:'middle',minWidth:140}}>
                    {prog._status === 'conc' && <span style={{fontSize:13,fontWeight:500,color:'#3B6D11'}}>100%</span>}
                    {prog._status === 'nao' && <span style={{fontSize:13,fontWeight:500,color:'#999'}}>0%</span>}
                    {prog._status === 'parc' && (
                      <div style={{display:'flex',flexDirection:'column',gap:4}}>
                        <div style={{display:'flex',alignItems:'center',gap:6}}>
                          <input
                            type="range" min={1} max={99} value={prog._pct}
                            onChange={e => setPct(prog.id, Number(e.target.value))}
                            style={{flex:1}}
                          />
                          <span style={{fontSize:13,fontWeight:500,color: prog._pct >= 70  '#3B6D11' : '#BA7517',minWidth:36}}>{prog._pct}%</span>
                        </div>
                        <div style={{width:'100%',height:4,background:'#E0E0DC',borderRadius:2,overflow:'hidden'}}>
                          <div style={{width:`${prog._pct}%`,height:'100%',background: prog._pct >= 70  '#8dc63f' : '#BA7517',borderRadius:2}} />
                        </div>
                      </div>
                    )}
                    {!prog._status && <span style={{fontSize:11,color:'#999',fontStyle:'italic'}}>pendente</span>}
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
      <div className="bg-white px-4 py-2.5 flex items-center gap-3" style={{borderTop:'0.5px solid #E0E0DC'}}>
        <span style={{fontSize:11,color:'#999'}}>
          {pendentes > 0 && <span style={{color:'#BA7517'}}>⚠ {pendentes} tarefa(s) sem status</span>}
          {pendentes === 0 && <span style={{color:'#3B6D11'}}>✓ Todas as tarefas preenchidas</span>}
        </span>
        {semanaObj?.fechada && (
          <span style={{fontSize:10,background:'#EAF3DE',color:'#3B6D11',border:'0.5px solid #8dc63f',padding:'2px 8px',borderRadius:4,fontWeight:500}}>
            ✓ Semana fechada
          </span>
        )}
        <div style={{marginLeft:'auto',display:'flex',gap:8}}>
          {!semanaObj?.fechada && (
            <button
              onClick={handleFechar}
              disabled={fechando || pendentes > 0}
              title={pendentes > 0  'Preencha todos os status antes de fechar' : 'Congelar indicadores desta semana'}
              style={{
                fontSize:11, fontWeight:500, cursor: pendentes > 0  'not-allowed' : 'pointer',
                background: pendentes > 0  '#F5F5F2' : '#EAF3DE',
                color: pendentes > 0  '#999' : '#3B6D11',
                border: `0.5px solid ${pendentes > 0  '#E0E0DC' : '#8dc63f'}`,
                borderRadius:6, padding:'6px 14px',
              }}
            >
              {fechando  'Fechando...' : '🔒 Fechar Semana'}
            </button>
          )}
          <button
            onClick={salvar}
            disabled={salvando}
            className="btn-navy"
          >
            {salvando  'Salvando...' : 'Salvar QREAL →'}
          </button>
        </div>
      </div>
    </div>
  )
}
