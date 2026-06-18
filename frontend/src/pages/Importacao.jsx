import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getImports, importXlsx, importXer, importSemanas, clearImports, createSemana, updateSemana, deleteSemana } from '../api'
import { useSemana } from '../context/SemanaContext'
import { logError } from '../utils/errors'

// Retorna segunda e domingo da semana corrente
function semanaAtualDates() {
  const today = new Date()
  const day = today.getDay() // 0=Dom
  const diffMon = day === 0  -6 : 1 - day
  const mon = new Date(today)
  mon.setDate(today.getDate() + diffMon)
  const sun = new Date(mon)
  sun.setDate(mon.getDate() + 6)
  const fmt = d => d.toISOString().split('T')[0]
  return { inicio: fmt(mon), fim: fmt(sun) }
}

// Sugere próximo código S_XXX baseado na última semana
function proximoCodigo(semanas) {
  if (!semanas.length) return 'S_001'
  const last = semanas[semanas.length - 1].codigo
  const m = last.match(/S_(\d+)/)
  if (!m) return 'S_001'
  const next = String(parseInt(m[1]) + 1).padStart(3, '0')
  return `S_${next}`
}

const STEPS = [
  'Lendo arquivo',
  'Identificando colunas',
  'Extraindo tarefas',
  'Calculando QCRON',
  'Salvando no banco',
  'Concluído',
]

export default function Importacao() {
  const navigate = useNavigate()
  const { semanas, semanaAtual, refetchSemanas } = useSemana()
  const [tipo, setTipo] = useState('xlsx')
  const [arquivo, setArquivo] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [semanaSel, setSemanasSel] = useState('')
  const [abaSel, setAbaSel] = useState('')
  const [historico, setHistorico] = useState([])
  const [processando, setProcessando] = useState(false)
  const [step, setStep] = useState(-1)
  const [resultado, setResultado] = useState(null)
  const [erro, setErro] = useState(null)
  const dropRef = useRef(null)

  // Estado do painel de gestão de semanas
  const [gerenciar, setGerenciar] = useState(false)
  const [editando, setEditando] = useState(null)   // codigo da semana em edição
  const [editInicio, setEditInicio] = useState('')
  const [editFim, setEditFim] = useState('')
  const [salvandoEdit, setSalvandoEdit] = useState(false)
  const [erroEdit, setErroEdit] = useState('')

  // Estado de importação de semanas via arquivo
  const [importandoSemanas, setImportandoSemanas] = useState(false)
  const [resultadoSemanas, setResultadoSemanas] = useState(null)
  const importSemanaRef = useRef(null)

  // Disciplinas para filtro do QCRON na importação
  const TODAS_DISCIPLINAS = [
    'Marcos', 'Mobilização', 'Engenharia de detalhamento',
    'Construção Civil', 'Eletromecânica', 'Comissionamento', 'Fornecimento de bens',
  ]
  const [disciplinasSel, setDisciplinasSel] = useState(new Set(['todas']))
  const [discDropOpen, setDiscDropOpen] = useState(false)

  // Estado do painel "nova semana"
  const [novaSemana, setNovaSemana] = useState(false)
  const [novaCodigo, setNovaCodigo] = useState('')
  const [novaInicio, setNovaInicio] = useState('')
  const [novaFim, setNovaFim] = useState('')
  const [criandoSemana, setCriandoSemana] = useState(false)
  const [erroSemana, setErroSemana] = useState('')

  useEffect(() => {
    if (semanaAtual) setSemanasSel(semanaAtual.codigo)
    getImports().then(setHistorico).catch(logError('Importacao:getImports'))
  }, [semanaAtual])

  const abrirEditar = (s) => {
    setEditando(s.codigo)
    setEditInicio(s.data_inicio)
    setEditFim(s.data_fim)
    setErroEdit('')
  }

  const salvarEdicao = async (codigo) => {
    if (!editInicio || !editFim) { setErroEdit('Preencha as datas.'); return }
    setSalvandoEdit(true)
    setErroEdit('')
    try {
      await updateSemana(codigo, { data_inicio: editInicio, data_fim: editFim })
      await refetchSemanas()
      setEditando(null)
    } catch (e) {
      setErroEdit(e.response?.data?.detail || 'Erro ao salvar.')
    } finally {
      setSalvandoEdit(false)
    }
  }

  const excluirSemana = async (codigo) => {
    if (!confirm(`Excluir a semana ${codigo} Isso remove também todas as programações vinculadas.`)) return
    try {
      await deleteSemana(codigo)
      await refetchSemanas()
      if (semanaSel === codigo) setSemanasSel('')
    } catch (e) {
      alert(e.response?.data?.detail || 'Erro ao excluir.')
    }
  }

  // Abre o painel de nova semana com valores sugeridos
  const abrirNovaSemana = () => {
    const { inicio, fim } = semanaAtualDates()
    setNovaCodigo(proximoCodigo(semanas))
    setNovaInicio(inicio)
    setNovaFim(fim)
    setErroSemana('')
    setNovaSemana(true)
  }

  const criarSemana = async () => {
    if (!novaCodigo || !novaInicio || !novaFim) {
      setErroSemana('Preencha todos os campos.')
      return
    }
    if (!/^S_\d{3,}$/.test(novaCodigo)) {
      setErroSemana('Código deve ser no formato S_035')
      return
    }
    setCriandoSemana(true)
    setErroSemana('')
    try {
      await createSemana({ codigo: novaCodigo, data_inicio: novaInicio, data_fim: novaFim })
      await refetchSemanas()
      setSemanasSel(novaCodigo)
      setNovaSemana(false)
    } catch (e) {
      setErroSemana(e.response?.data?.detail || 'Erro ao criar semana.')
    } finally {
      setCriandoSemana(false)
    }
  }

  const handleImportSemanas = async (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setImportandoSemanas(true)
    setResultadoSemanas(null)
    try {
      const fd = new FormData()
      fd.append('file', f)
      const res = await importSemanas(fd)
      setResultadoSemanas(res)
      await refetchSemanas()
    } catch (err) {
      alert(err.response?.data?.detail || 'Erro ao importar semanas.')
    } finally {
      setImportandoSemanas(false)
      e.target.value = ''
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer?.files?.[0] || e.target.files?.[0]
    if (f) setArquivo(f)
  }

  const simularSteps = async () => {
    for (let i = 0; i < STEPS.length - 1; i++) {
      setStep(i)
      await new Promise(r => setTimeout(r, 300))
    }
  }

  const importar = async () => {
    if (!arquivo || !semanaSel) return
    setProcessando(true)
    setErro(null)
    setResultado(null)
    setStep(0)

    const fd = new FormData()
    fd.append('file', arquivo)
    fd.append('semana', semanaSel)
    if (tipo === 'xlsx' && abaSel) fd.append('aba', abaSel)
    if (!disciplinasSel.has('todas')) {
      fd.append('disciplinas', [...disciplinasSel].join(','))
    }

    try {
      const [, res] = await Promise.all([simularSteps(), tipo === 'xlsx'  importXlsx(fd) : importXer(fd)])
      setStep(STEPS.length - 1)
      setResultado(res)
      getImports().then(setHistorico)
      refetchSemanas()
    } catch (e) {
      setErro(e.response?.data?.detail || e.message || 'Erro desconhecido')
      setStep(-1)
    } finally {
      setProcessando(false)
    }
  }

  const fmtDateTime = (d) => {
    if (!d) return '—'
    return new Date(d).toLocaleString('pt-BR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' })
  }

  return (
    <div className="min-h-screen flex flex-col" style={{background:'#F2F2F0'}}>
      <div className="p-4 flex flex-col gap-4" style={{maxWidth:900,margin:'0 auto',width:'100%'}}>
        <div style={{fontWeight:500,fontSize:14,color:'#063057'}}>Importar Arquivo</div>

        {/* Tipo */}
        <div className="grid grid-cols-2 gap-3">
          {[
            ['xlsx', 'Excel', '.xlsx', 'Cronograma exportado do controle interno ETM'],
            ['xer', 'Primavera', '.xer', 'Exportação direta do Oracle Primavera P6'],
          ].map(([t, label, ext, desc]) => (
            <div
              key={t}
              onClick={() => setTipo(t)}
              style={{
                background:'white', borderRadius:12, padding:'14px 16px', cursor:'pointer',
                border: tipo === t  '1.5px solid #063057' : '0.5px solid #E0E0DC',
              }}
            >
              <div style={{fontSize:13,fontWeight:500,color: tipo===t  '#063057' : '#111'}}>{label} <span style={{fontSize:11,color:'#999'}}>{ext}</span></div>
              <div style={{fontSize:11,color:'#555',marginTop:3}}>{desc}</div>
            </div>
          ))}
        </div>

        {/* Dropzone */}
        <div
          ref={dropRef}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => !arquivo && dropRef.current.querySelector('input').click()}
          style={{
            background: 'white', borderRadius:12, padding:'32px',
            textAlign:'center', cursor: arquivo  'default' : 'pointer',
            border: arquivo
               '1.5px solid #8dc63f'
              : dragging
               '2px dashed #8dc63f'
              : '1.5px dashed #D0D0CC',
          }}
        >
          <input type="file" accept={tipo === 'xlsx'  '.xlsx' : '.xer'} style={{display:'none'}} onChange={onDrop} />
          {!arquivo  (
            <>
              <div style={{fontSize:32,marginBottom:8}}>📁</div>
              <div style={{fontSize:13,color:'#555'}}>Arraste o arquivo aqui ou <span style={{color:'#185FA5'}}>clique para selecionar</span></div>
              <div style={{fontSize:11,color:'#999',marginTop:4}}>Aceita arquivos {tipo === 'xlsx'  '.xlsx' : '.xer'}</div>
            </>
          ) : (
            <>
              <div style={{fontSize:32,marginBottom:8}}>✅</div>
              <div style={{fontSize:13,fontWeight:500,color:'#3B6D11'}}>{arquivo.name}</div>
              <div style={{fontSize:11,color:'#999',marginTop:2}}>{(arquivo.size / 1024).toFixed(1)} KB</div>
              <button
                onClick={e => { e.stopPropagation(); setArquivo(null); setResultado(null); setStep(-1) }}
                style={{marginTop:8,fontSize:11,color:'#A32D2D',background:'none',border:'none',cursor:'pointer',textDecoration:'underline'}}
              >
                remover
              </button>
            </>
          )}
        </div>

        {/* Config */}
        <div className="grid grid-cols-2 gap-3">
          <div style={{display:'flex',flexDirection:'column',gap:4}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
              <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Semana de Referência</span>
              <div style={{display:'flex',gap:4,alignItems:'center'}}>
                <button
                  onClick={abrirNovaSemana}
                  style={{fontSize:10,color:'#185FA5',background:'none',border:'0.5px solid #185FA5',borderRadius:4,padding:'2px 8px',cursor:'pointer'}}
                >
                  + Nova semana
                </button>
                <button
                  onClick={() => importSemanaRef.current?.click()}
                  disabled={importandoSemanas}
                  title="Importar semanas da aba 'Semanas' de um arquivo XLSX"
                  style={{fontSize:10,color:'#3B6D11',background:'none',border:'0.5px solid #8dc63f',borderRadius:4,padding:'2px 8px',cursor:'pointer',opacity:importandoSemanas?0.6:1}}
                >
                  {importandoSemanas  '⏳ importando...' : '📅 Importar do XLSX'}
                </button>
                <input ref={importSemanaRef} type="file" accept=".xlsx" style={{display:'none'}} onChange={handleImportSemanas} />
              </div>
            </div>

            {/* Aviso quando lista vazia */}
            {semanas.length === 0 && !novaSemana && (
              <div style={{background:'#FFF8E6',border:'0.5px solid #E6C96A',borderRadius:8,padding:'10px 12px',fontSize:12,color:'#7A5800'}}>
                ⚠ Nenhuma semana cadastrada ainda.{' '}
                <button onClick={abrirNovaSemana} style={{color:'#185FA5',background:'none',border:'none',cursor:'pointer',textDecoration:'underline',fontSize:12,padding:0}}>
                  Criar agora
                </button>
              </div>
            )}

            {/* Resultado da importação de semanas */}
            {resultadoSemanas && (
              <div style={{background:'#EBF7DE',border:'0.5px solid #8dc63f',borderRadius:8,padding:'8px 12px',fontSize:11,color:'#3B6D11',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <span>✓ {resultadoSemanas.criadas} semanas criadas, {resultadoSemanas.atualizadas} atualizadas ({resultadoSemanas.total} total)</span>
                <button onClick={() => setResultadoSemanas(null)} style={{background:'none',border:'none',cursor:'pointer',color:'#3B6D11',fontSize:13}}>×</button>
              </div>
            )}

            {/* Painel inline de nova semana */}
            {novaSemana && (
              <div style={{background:'#EBF2FA',border:'1px solid #185FA5',borderRadius:10,padding:'14px 16px',display:'flex',flexDirection:'column',gap:10}}>
                <div style={{fontSize:11,fontWeight:500,color:'#063057'}}>Nova Semana</div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8}}>
                  <label style={{display:'flex',flexDirection:'column',gap:3}}>
                    <span style={{fontSize:9,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Código</span>
                    <input
                      className="input-base"
                      value={novaCodigo}
                      onChange={e => setNovaCodigo(e.target.value.toUpperCase())}
                      placeholder="S_035"
                      style={{fontFamily:'monospace',fontWeight:500}}
                    />
                  </label>
                  <label style={{display:'flex',flexDirection:'column',gap:3}}>
                    <span style={{fontSize:9,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Início (seg)</span>
                    <input type="date" className="input-base" value={novaInicio} onChange={e => setNovaInicio(e.target.value)} />
                  </label>
                  <label style={{display:'flex',flexDirection:'column',gap:3}}>
                    <span style={{fontSize:9,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Fim (dom)</span>
                    <input type="date" className="input-base" value={novaFim} onChange={e => setNovaFim(e.target.value)} />
                  </label>
                </div>
                {erroSemana && <div style={{fontSize:11,color:'#A32D2D'}}>{erroSemana}</div>}
                <div style={{display:'flex',gap:8}}>
                  <button
                    onClick={criarSemana}
                    disabled={criandoSemana}
                    style={{background:'#063057',color:'white',border:'none',borderRadius:6,padding:'6px 14px',fontSize:12,fontWeight:500,cursor:'pointer'}}
                  >
                    {criandoSemana  'Criando...' : 'Criar semana'}
                  </button>
                  <button
                    onClick={() => setNovaSemana(false)}
                    style={{background:'none',border:'0.5px solid #D0D0CC',color:'#555',borderRadius:6,padding:'6px 14px',fontSize:12,cursor:'pointer'}}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {/* Dropdown normal */}
            {!novaSemana && (
              <select
                value={semanaSel}
                onChange={e => setSemanasSel(e.target.value)}
                className="input-base"
              >
                <option value="">Selecione a semana...</option>
                {semanas.map(s => (
                  <option key={s.codigo} value={s.codigo}>{s.codigo} — {s.data_inicio?.split('-').reverse().join('/')} a {s.data_fim?.split('-').reverse().join('/')}</option>
                ))}
              </select>
            )}

            {/* Filtro de disciplinas para o QCRON */}
            {!novaSemana && (
              <div>
                <div style={{fontSize:9,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em',marginBottom:4}}>
                  Fase no QCRON
                </div>
                <div style={{position:'relative',display:'inline-block'}}>
                  <button
                    onClick={() => setDiscDropOpen(o => !o)}
                    style={{
                      fontSize:11, padding:'5px 10px', borderRadius:6, cursor:'pointer',
                      border: disciplinasSel.has('todas')  '0.5px solid #E0E0DC' : '0.5px solid #185FA5',
                      background: disciplinasSel.has('todas')  '#F5F5F2' : '#E6F1FB',
                      color: disciplinasSel.has('todas')  '#555' : '#185FA5',
                      whiteSpace:'nowrap',
                    }}
                  >
                    {disciplinasSel.has('todas')  'Todas as fases ▾' : `${disciplinasSel.size} fase(s) ▾`}
                  </button>
                  {discDropOpen && (
                    <div style={{
                      position:'absolute', top:'calc(100% + 4px)', left:0, zIndex:50,
                      background:'white', border:'0.5px solid #E0E0DC', borderRadius:8,
                      boxShadow:'0 4px 16px rgba(0,0,0,0.10)', padding:'6px 0', minWidth:240,
                    }}
                      onMouseLeave={() => setDiscDropOpen(false)}
                    >
                      <label style={{display:'flex',alignItems:'center',gap:8,padding:'5px 12px',cursor:'pointer',fontSize:11}}
                        onMouseEnter={e => e.currentTarget.style.background='#F5F5F2'}
                        onMouseLeave={e => e.currentTarget.style.background='white'}
                      >
                        <input type="checkbox" checked={disciplinasSel.has('todas')}
                          onChange={() => setDisciplinasSel(new Set(['todas']))} />
                        <span style={{fontWeight:500}}>Todas as fases</span>
                      </label>
                      <div style={{height:'0.5px',background:'#E0E0DC',margin:'4px 0'}} />
                      {TODAS_DISCIPLINAS.map(d => (
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
                                  if (next.size === TODAS_DISCIPLINAS.length) return new Set(['todas'])
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
                {!disciplinasSel.has('todas') && (
                  <div style={{marginTop:4,fontSize:10,color:'#185FA5'}}>
                    Apenas: {[...disciplinasSel].join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Link gerenciar semanas */}
            {!novaSemana && semanas.length > 0 && (
              <button
                onClick={() => setGerenciar(g => !g)}
                style={{alignSelf:'flex-start',fontSize:10,color:'#185FA5',background:'none',border:'none',cursor:'pointer',padding:0,textDecoration:'underline'}}
              >
                {gerenciar  '▲ fechar' : '⚙ gerenciar semanas'}
              </button>
            )}

            {/* Painel de gerenciamento */}
            {gerenciar && !novaSemana && (
              <div style={{border:'0.5px solid #E0E0DC',borderRadius:8,overflow:'hidden',marginTop:2}}>
                {semanas.map((s, i) => (
                  <div key={s.codigo}>
                    {editando === s.codigo  (
                      /* Linha de edição inline */
                      <div style={{padding:'10px 12px',background:'#EBF2FA',display:'flex',flexDirection:'column',gap:8}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
                          <label style={{display:'flex',flexDirection:'column',gap:3}}>
                            <span style={{fontSize:9,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Início</span>
                            <input type="date" className="input-base" value={editInicio} onChange={e => setEditInicio(e.target.value)} />
                          </label>
                          <label style={{display:'flex',flexDirection:'column',gap:3}}>
                            <span style={{fontSize:9,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Fim</span>
                            <input type="date" className="input-base" value={editFim} onChange={e => setEditFim(e.target.value)} />
                          </label>
                        </div>
                        {erroEdit && <span style={{fontSize:11,color:'#A32D2D'}}>{erroEdit}</span>}
                        <div style={{display:'flex',gap:6}}>
                          <button
                            onClick={() => salvarEdicao(s.codigo)}
                            disabled={salvandoEdit}
                            style={{background:'#063057',color:'white',border:'none',borderRadius:4,padding:'4px 12px',fontSize:11,fontWeight:500,cursor:'pointer'}}
                          >
                            {salvandoEdit  'Salvando...' : 'Salvar'}
                          </button>
                          <button
                            onClick={() => setEditando(null)}
                            style={{background:'none',border:'0.5px solid #D0D0CC',color:'#555',borderRadius:4,padding:'4px 10px',fontSize:11,cursor:'pointer'}}
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Linha normal */
                      <div style={{
                        padding:'8px 12px',
                        borderBottom: i < semanas.length - 1  '0.5px solid #E0E0DC' : 'none',
                        display:'flex',alignItems:'center',gap:8,
                        background: s.codigo === semanaSel  '#F0F6FF' : 'white',
                      }}>
                        <span style={{fontFamily:'monospace',fontSize:11,fontWeight:600,color:'#063057',minWidth:52}}>{s.codigo}</span>
                        <span style={{fontSize:11,color:'#555',flex:1}}>{s.data_inicio?.split('-').reverse().join('/')} a {s.data_fim?.split('-').reverse().join('/')}</span>
                        <button
                          onClick={() => abrirEditar(s)}
                          title="Editar datas"
                          style={{background:'none',border:'0.5px solid #D0D0CC',borderRadius:4,padding:'3px 8px',fontSize:11,color:'#185FA5',cursor:'pointer'}}
                        >
                          ✏ editar
                        </button>
                        <button
                          onClick={() => excluirSemana(s.codigo)}
                          title="Excluir semana"
                          style={{background:'none',border:'0.5px solid #FFCDD2',borderRadius:4,padding:'3px 8px',fontSize:11,color:'#A32D2D',cursor:'pointer'}}
                        >
                          🗑 excluir
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {tipo === 'xlsx' && (
            <label style={{display:'flex',flexDirection:'column',gap:4}}>
              <span style={{fontSize:10,fontWeight:500,color:'#555',textTransform:'uppercase',letterSpacing:'0.05em'}}>Aba do arquivo (opcional)</span>
              <input
                className="input-base"
                value={abaSel}
                onChange={e => setAbaSel(e.target.value)}
                placeholder="Ex: Programacao Folha 01"
              />
            </label>
          )}
        </div>

        {/* Progress */}
        {step >= 0 && (
          <div className="card">
            <div className="section-label">Progresso</div>
            <div style={{display:'flex',flexDirection:'column',gap:8,marginTop:8}}>
              {STEPS.map((s, i) => (
                <div key={s} style={{display:'flex',alignItems:'center',gap:10}}>
                  <div style={{
                    width:18,height:18,borderRadius:'50%',flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center',fontSize:10,fontWeight:600,
                    background: i < step  '#8dc63f' : i === step  '#063057' : '#E0E0DC',
                    color: i <= step  'white' : '#999',
                  }}>
                    {i < step  '✓' : i + 1}
                  </div>
                  <span style={{fontSize:12,color: i <= step  '#111' : '#999',fontWeight: i === step  500 : 'normal'}}>
                    {s}
                    {i === step && processando && <span style={{color:'#185FA5'}}> ...</span>}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Erro */}
        {erro && (
          <div style={{background:'#FCEBEB',border:'0.5px solid #E24B4A',borderRadius:8,padding:'12px 16px',fontSize:12,color:'#A32D2D'}}>
            ⚠ {erro}
          </div>
        )}

        {/* Resultado */}
        {resultado && (
          <div className="card">
            <div className="section-label-green">Tarefas Encontradas — {resultado.tarefas_encontradas} total · {resultado.qcron_count} no QCRON</div>
            <div style={{display:'flex',gap:12,marginBottom:12,marginTop:8,flexWrap:'wrap'}}>
              {[
                ['Encontradas', resultado.tarefas_encontradas, '#185FA5'],
                ['Novas', resultado.tarefas_novas, '#3B6D11'],
                ['Atualizadas', resultado.tarefas_atualizadas, '#854F0B'],
                ['No QCRON', resultado.qcron_count, '#063057'],
              ].map(([l,v,c]) => (
                <div key={l} style={{background:'#F5F5F2',borderRadius:8,padding:'8px 12px'}}>
                  <div style={{fontSize:9,color:'#999',textTransform:'uppercase'}}>{l}</div>
                  <div style={{fontSize:18,fontWeight:500,color:c}}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{overflowX:'auto',maxHeight:240,overflowY:'auto'}}>
              <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
                <thead>
                  <tr style={{background:'#F5F5F2',position:'sticky',top:0}}>
                    {['ID','Nome','Disciplina','Supervisor','Início','Término','%'].map(h => (
                      <th key={h} style={{padding:'6px 10px',fontSize:10,fontWeight:500,color:'#555',textAlign:'left',borderBottom:'0.5px solid #E0E0DC'}}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(resultado.detalhes || []).slice(0, 50).map(t => (
                    <tr key={t.id} style={{borderBottom:'0.5px solid #E0E0DC'}}>
                      <td style={{padding:'5px 10px',fontFamily:'monospace',fontSize:10,color:'#999'}}>{t.activity_id}</td>
                      <td style={{padding:'5px 10px',maxWidth:220}}>{t.nome}</td>
                      <td style={{padding:'5px 10px'}}>{t.disciplina || '—'}</td>
                      <td style={{padding:'5px 10px'}}>{t.supervisor || '—'}</td>
                      <td style={{padding:'5px 10px',whiteSpace:'nowrap'}}>{t.inicio_lb || '—'}</td>
                      <td style={{padding:'5px 10px',whiteSpace:'nowrap'}}>{t.termino_lb || '—'}</td>
                      <td style={{padding:'5px 10px'}}>{t.duracao || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Histórico */}
        {historico.length > 0 && (
          <div className="card">
            <div style={{display:'flex',alignItems:'center',marginBottom:8}}>
              <div className="section-label" style={{marginBottom:0}}>Histórico de Importações</div>
              <button
                onClick={async () => {
                  if (!confirm('Limpar todo o histórico de importações?')) return
                  await clearImports()
                  setHistorico([])
                }}
                style={{marginLeft:'auto',fontSize:10,color:'#A32D2D',background:'none',border:'0.5px solid #FFCDD2',borderRadius:4,padding:'2px 8px',cursor:'pointer'}}
              >
                🗑 Limpar histórico
              </button>
            </div>
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:12,marginTop:8}}>
              <thead>
                <tr style={{background:'#F5F5F2'}}>
                  {['Semana','Arquivo','Data/Hora','Tipo','Status'].map(h => (
                    <th key={h} style={{padding:'6px 10px',fontSize:10,fontWeight:500,color:'#555',textAlign:'left',borderBottom:'0.5px solid #E0E0DC'}}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {historico.map(h => (
                  <tr key={h.id} style={{borderBottom:'0.5px solid #E0E0DC'}}>
                    <td style={{padding:'6px 10px',fontWeight:500,color:'#063057'}}>{h.semana_ref}</td>
                    <td style={{padding:'6px 10px',color:'#555',maxWidth:200}}>{h.arquivo_original || '—'}</td>
                    <td style={{padding:'6px 10px',color:'#999',whiteSpace:'nowrap'}}>{fmtDateTime(h.importado_em)}</td>
                    <td style={{padding:'6px 10px'}}>
                      <span style={{fontSize:9,padding:'1px 6px',borderRadius:3,fontWeight:500,background: h.tipo === 'xlsx'  '#EAF3DE' : '#E6F1FB',color: h.tipo === 'xlsx'  '#3B6D11' : '#185FA5'}}>
                        {h.tipo.toUpperCase()}
                      </span>
                    </td>
                    <td style={{padding:'6px 10px',color: h.status === 'ok'  '#3B6D11' : '#A32D2D'}}>{h.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Botões */}
        <div className="flex justify-end gap-3">
          <button onClick={() => navigate(-1)} style={{background:'none',border:'0.5px solid #D0D0CC',color:'#555',padding:'8px 18px',borderRadius:6,fontSize:12,cursor:'pointer'}}>
            Cancelar
          </button>
          {resultado  (
            <button onClick={() => navigate(`/qprog/${semanaSel}`)} className="btn-navy">
              Ir para Montar QPROG →
            </button>
          ) : (
            <button
              onClick={importar}
              disabled={!arquivo || !semanaSel || processando}
              className="btn-navy"
              style={{opacity: (!arquivo || !semanaSel || processando)  0.5 : 1}}
            >
              {processando  'Importando...' : 'Importar arquivo'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
