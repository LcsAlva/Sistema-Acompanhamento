import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getTextos, saveTextos } from '../api'
import { useSemana } from '../context/SemanaContext'

const DIAS_PT = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']

const CLIMA_OPCOES = [
  { code: 0,  emoji: '☀️',  desc: 'Céu limpo'   },
  { code: 1,  emoji: '🌤️', desc: 'Poucas nuvens'},
  { code: 2,  emoji: '⛅',  desc: 'Nublado'      },
  { code: 3,  emoji: '☁️',  desc: 'Muito nublado'},
  { code: 61, emoji: '🌧️', desc: 'Chuva'         },
  { code: 80, emoji: '🌦️', desc: 'Pancadas'      },
  { code: 95, emoji: '⛈️', desc: 'Tempestade'    },
]

function gerarDiasSemana(dataInicio, dataFim) {
  if (!dataInicio || !dataFim) return []
  const dias = []
  let cur = new Date(dataInicio + 'T12:00:00')
  const fim = new Date(dataFim + 'T12:00:00')
  while (cur <= fim) {
    const iso = cur.toISOString().slice(0,10)
    dias.push({
      data: iso,
      data_fmt: iso.slice(8,10) + '/' + iso.slice(5,7),
      dia_semana: DIAS_PT[cur.getDay()],
    })
    cur = new Date(cur.getTime() + 86400000)
  }
  return dias
}

function climaVazio(dias) {
  return dias.map(d => ({ ...d, weathercode: 0, temp_max: '', temp_min: '' }))
}

export default function TextosRelatorio() {
  const { semana: semanaParam } = useParams()
  const navigate = useNavigate()
  const { semanas } = useSemana()
  const semanaObj = semanas.find(s => s.codigo === semanaParam) || null

  const [justificativas, setJustificativas] = useState([''])
  const [marcos, setMarcos] = useState([''])
  const [descricao, setDescricao] = useState('')
  const [notaClima, setNotaClima] = useState('')
  const [climaDias, setClimaDias] = useState([])
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    if (!semanaParam || semanaParam === '—') return

    const dias = gerarDiasSemana(semanaObj?.data_inicio, semanaObj?.data_fim)

    getTextos(semanaParam).then(d => {
      try {
        setJustificativas(JSON.parse(d.justificativas_atraso || '[""]') || [''])
        setMarcos(JSON.parse(d.marcos_observacoes || '[""]') || [''])
      } catch { setJustificativas(['']); setMarcos(['']) }
      setDescricao(d.descricao_resumida || '')
      setNotaClima(d.nota_clima || '')

      // Tenta restaurar clima salvo anteriormente
      try {
        const saved = JSON.parse(d.condicoes_climaticas || 'null')
        if (Array.isArray(saved) && saved.length > 0 && !saved[0].erro) {
          // Mescla dados salvos com os dias da semana atual
          const merged = dias.map(dia => {
            const salvo = saved.find(s => s.data === dia.data)
            return salvo  { ...dia, weathercode: salvo.weathercode, temp_max: salvo.temp_max  '', temp_min: salvo.temp_min  '' }
                         : { ...dia, weathercode: 0, temp_max: '', temp_min: '' }
          })
          setClimaDias(merged)
          return
        }
      } catch {}
      setClimaDias(climaVazio(dias))
    }).catch(() => setClimaDias(climaVazio(dias)))
  }, [semanaParam, semanaObj?.data_inicio, semanaObj?.data_fim])

  const editList = (list, setList, idx, val) => {
    const next = [...list]; next[idx] = val; setList(next)
  }
  const addItem  = (list, setList) => setList([...list, ''])
  const removeItem = (list, setList, idx) => setList(list.filter((_, i) => i !== idx))

  const editClima = (idx, field, val) => {
    setClimaDias(prev => prev.map((d, i) => i === idx  { ...d, [field]: val } : d))
  }

  const salvar = async () => {
    setSalvando(true)
    try {
      await saveTextos(semanaParam, {
        semana: semanaParam,
        justificativas_atraso: JSON.stringify(justificativas.filter(Boolean)),
        marcos_observacoes: JSON.stringify(marcos.filter(Boolean)),
        descricao_resumida: descricao,
        condicoes_climaticas: climaDias.length  JSON.stringify(climaDias) : null,
        nota_clima: notaClima,
      })
      navigate('/')
    } catch (e) {
      alert('Erro ao salvar: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{background:'#F2F2F0'}}>
      <div className="p-4 flex flex-col gap-4" style={{maxWidth:1200,margin:'0 auto',width:'100%'}}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <div style={{fontWeight:500,fontSize:14,color:'#063057',whiteSpace:'nowrap'}}>Textos do Relatório</div>
          <select
            value={semanaParam}
            onChange={e => navigate(`/textos/${e.target.value}`)}
            className="input-base"
            style={{width:'auto',fontSize:12,fontWeight:500,color:'#063057',minWidth:160}}
          >
            {semanas.map(s => (
              <option key={s.codigo} value={s.codigo}>
                {s.codigo} — {s.data_inicio?.split('-').slice(1).reverse().join('/')} a {s.data_fim?.split('-').slice(1).reverse().join('/')}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="card">
            <div className="section-label">Justificativas de Desvio</div>
            <div style={{display:'flex',flexDirection:'column',gap:8,marginTop:8}}>
              {justificativas.map((j, i) => (
                <div key={i} style={{display:'flex',gap:8,alignItems:'flex-start'}}>
                  <span style={{width:8,height:8,borderRadius:'50%',background:'#BA7517',marginTop:10,flexShrink:0,display:'inline-block'}}/>
                  <textarea value={j} onChange={e => editList(justificativas, setJustificativas, i, e.target.value)}
                    style={{flex:1,border:'0.5px solid #E0E0DC',borderRadius:6,padding:'6px 10px',fontSize:12,resize:'vertical',minHeight:52,background:'white'}}
                    placeholder="Justificativa..." />
                  <button onClick={() => removeItem(justificativas, setJustificativas, i)}
                    style={{background:'none',border:'none',color:'#999',cursor:'pointer',fontSize:16,padding:'4px'}}>×</button>
                </div>
              ))}
              <button onClick={() => addItem(justificativas, setJustificativas)}
                style={{alignSelf:'flex-start',fontSize:11,color:'#185FA5',background:'none',border:'0.5px solid #185FA5',borderRadius:4,padding:'3px 10px',cursor:'pointer'}}>
                + adicionar
              </button>
            </div>
          </div>
          <div className="card">
            <div className="section-label-green">Marcos / Observações</div>
            <div style={{display:'flex',flexDirection:'column',gap:8,marginTop:8}}>
              {marcos.map((m, i) => (
                <div key={i} style={{display:'flex',gap:8,alignItems:'flex-start'}}>
                  <span style={{width:8,height:8,borderRadius:'50%',background:'#8dc63f',marginTop:10,flexShrink:0,display:'inline-block'}}/>
                  <textarea value={m} onChange={e => editList(marcos, setMarcos, i, e.target.value)}
                    style={{flex:1,border:'0.5px solid #E0E0DC',borderRadius:6,padding:'6px 10px',fontSize:12,resize:'vertical',minHeight:52,background:'white'}}
                    placeholder="Marco ou observação..." />
                  <button onClick={() => removeItem(marcos, setMarcos, i)}
                    style={{background:'none',border:'none',color:'#999',cursor:'pointer',fontSize:16,padding:'4px'}}>×</button>
                </div>
              ))}
              <button onClick={() => addItem(marcos, setMarcos)}
                style={{alignSelf:'flex-start',fontSize:11,color:'#185FA5',background:'none',border:'0.5px solid #185FA5',borderRadius:4,padding:'3px 10px',cursor:'pointer'}}>
                + adicionar
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="section-label">Descrição Resumida da Semana</div>
          <textarea value={descricao} onChange={e => e.target.value.length <= 400 && setDescricao(e.target.value)}
            style={{width:'100%',border:'0.5px solid #E0E0DC',borderRadius:6,padding:'8px 12px',fontSize:12,resize:'vertical',minHeight:80,background:'white',marginTop:8}}
            placeholder="Resumo das atividades realizadas na semana..." />
          <div style={{textAlign:'right',fontSize:10,color:'#999',marginTop:4}}>{descricao.length} / 400 caracteres</div>
        </div>

        {/* Condições Climáticas — entrada manual */}
        <div className="card">
          <div style={{display:'flex',alignItems:'center',marginBottom:10}}>
            <div className="section-label" style={{marginBottom:0}}>Condições Climáticas</div>
            <span style={{marginLeft:'auto',fontSize:10,color:'#999'}}>Preenchimento manual · Mauá, SP</span>
          </div>

          {climaDias.length === 0  (
            <p style={{fontSize:12,color:'#999',fontStyle:'italic'}}>Semana sem datas definidas.</p>
          ) : (
            <div style={{display:'grid',gridTemplateColumns:`repeat(${climaDias.length},1fr)`,gap:8}}>
              {climaDias.map((dia, idx) => (
                <div key={dia.data} style={{border:'0.5px solid #E0E0DC',borderRadius:8,padding:'10px 8px',textAlign:'center',background:'#FAFAF8'}}>
                  <div style={{fontSize:9,color:'#999',textTransform:'uppercase',fontWeight:600}}>{dia.dia_semana}</div>
                  <div style={{fontSize:10,color:'#555',marginBottom:8}}>{dia.data_fmt}</div>

                  {/* Seletor de condição */}
                  <div style={{display:'flex',flexWrap:'wrap',justifyContent:'center',gap:3,marginBottom:8}}>
                    {CLIMA_OPCOES.map(op => (
                      <button key={op.code}
                        title={op.desc}
                        onClick={() => editClima(idx, 'weathercode', op.code)}
                        style={{
                          fontSize:16,padding:'2px 3px',borderRadius:4,cursor:'pointer',
                          border: dia.weathercode === op.code  '2px solid #185FA5' : '1px solid #E0E0DC',
                          background: dia.weathercode === op.code  '#E6F1FB' : 'white',
                          lineHeight:1,
                        }}>
                        {op.emoji}
                      </button>
                    ))}
                  </div>

                  <div style={{fontSize:9,color:'#555',marginBottom:4,fontWeight:500}}>
                    {CLIMA_OPCOES.find(o => o.code === dia.weathercode)?.desc || '—'}
                  </div>

                  {/* Temp máx / mín */}
                  <div style={{display:'flex',gap:4,justifyContent:'center',alignItems:'center'}}>
                    <div style={{textAlign:'center'}}>
                      <div style={{fontSize:8,color:'#A32D2D',fontWeight:600}}>Máx</div>
                      <input type="number" value={dia.temp_max} onChange={e => editClima(idx, 'temp_max', e.target.value)}
                        style={{width:38,border:'0.5px solid #E0E0DC',borderRadius:4,padding:'2px 4px',fontSize:11,textAlign:'center',color:'#A32D2D',fontWeight:600}}
                        placeholder="--" />
                    </div>
                    <div style={{fontSize:10,color:'#ccc',marginTop:10}}>|</div>
                    <div style={{textAlign:'center'}}>
                      <div style={{fontSize:8,color:'#185FA5',fontWeight:600}}>Mín</div>
                      <input type="number" value={dia.temp_min} onChange={e => editClima(idx, 'temp_min', e.target.value)}
                        style={{width:38,border:'0.5px solid #E0E0DC',borderRadius:4,padding:'2px 4px',fontSize:11,textAlign:'center',color:'#185FA5'}}
                        placeholder="--" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{marginTop:12}}>
            <div style={{fontSize:10,fontWeight:500,color:'#555',marginBottom:4,textTransform:'uppercase',letterSpacing:'0.05em'}}>Nota climática</div>
            <textarea value={notaClima} onChange={e => setNotaClima(e.target.value)}
              style={{width:'100%',border:'0.5px solid #E0E0DC',borderRadius:6,padding:'6px 10px',fontSize:12,resize:'vertical',minHeight:52,background:'white'}}
              placeholder="Condições climáticas da semana..." />
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button onClick={() => navigate(-1)} style={{background:'none',border:'0.5px solid #D0D0CC',color:'#555',padding:'8px 18px',borderRadius:6,fontSize:12,cursor:'pointer'}}>
            Cancelar
          </button>
          <button onClick={salvar} disabled={salvando} className="btn-navy">
            {salvando  'Salvando...' : 'Salvar e ir ao Dashboard →'}
          </button>
        </div>
      </div>
    </div>
  )
}
