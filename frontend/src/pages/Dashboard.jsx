import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Chart, ArcElement, DoughnutController, Tooltip } from 'chart.js'
import { useSemana } from '../context/SemanaContext'
import { useIndicadores, useTextos } from '../hooks/useApi'
import { fmtPeriodo, execPct, execColor } from '../utils/formatters'

Chart.register(ArcElement, DoughnutController, Tooltip)

export default function Dashboard() {
  const { semanas, semanaAtual } = useSemana()
  const [expandirHistorico, setExpandirHistorico] = useState(false)
  const donut1Ref = useRef(null)
  const donut2Ref = useRef(null)
  const chart1Ref = useRef(null)
  const chart2Ref = useRef(null)
  const rowAtualRef = useRef(null)

  const semanaAtualIdx = semanas.findIndex(s => s.codigo === semanaAtual?.codigo)
  const semanaAnterior = semanaAtualIdx > 0  semanas[semanaAtualIdx - 1] : null
  // Próximas 2 semanas — usadas no donut IPROG (atual + 2 à frente).
  const semanaProx1 = semanaAtualIdx >= 0  semanas[semanaAtualIdx + 1] : null
  const semanaProx2 = semanaAtualIdx >= 0  semanas[semanaAtualIdx + 2] : null

  // Scroll automático para a semana atual quando o histórico é aberto
  useEffect(() => {
    if (expandirHistorico && rowAtualRef.current) {
      setTimeout(() => {
        rowAtualRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      }, 50)
    }
  }, [expandirHistorico])

  // React Query cuida de cache, retry e dedup automaticamente.
  const { data: indicadores }    = useIndicadores(semanaAtual?.codigo)
  const { data: indicadoresAnt } = useIndicadores(semanaAnterior?.codigo)
  const { data: indProx1 }       = useIndicadores(semanaProx1?.codigo)
  const { data: indProx2 }       = useIndicadores(semanaProx2?.codigo)
  const { data: textos }         = useTextos(semanaAtual?.codigo)

  // ── IPROG (3 semanas: atual + 2 à frente) ───────────────────────────────
  // Soma QCRON e QPROG para mostrar o índice agregado de programação.
  const ipQcron = (indicadores?.qcron  0) + (indProx1?.qcron  0) + (indProx2?.qcron  0)
  const ipQprog = (indicadores?.qprog  0) + (indProx1?.qprog  0) + (indProx2?.qprog  0)
  const ipPctAcum = ipQcron > 0  Math.round(ipQprog / ipQcron * 10000) / 100 : 0

  const semanasProx = [semanaAtual, semanaProx1, semanaProx2].filter(Boolean)
  const codProx = semanasProx.map(s => s.codigo).join('/')

  // ── ICPROG (semana anterior) ────────────────────────────────────────────
  const icQprog = indicadoresAnt?.qprog  0
  const icQreal = indicadoresAnt?.qreal_concluidas  0
  const icPctAcum = icQprog > 0  Math.round(icQreal / icQprog * 10000) / 100 : 0

  useEffect(() => {
    // Donut 1 (anterior): ICPROG = QREAL / QPROG (azul=qprog, verde=qreal).
    // Donut 2 (3-sem):    IPROG  = QPROG / QCRON (azul=qcron, verde=qprog).
    // As fatias mostram os dois valores lado a lado (não val/total).
    const drawDonut = (canvasRef, chartRef, valAzul, valVerde) => {
      if (!canvasRef.current) return
      if (chartRef.current) chartRef.current.destroy()
      const ctx = canvasRef.current.getContext('2d')
      chartRef.current = new Chart(ctx, {
        type: 'doughnut',
        data: {
          datasets: [{
            data: [valAzul, valVerde],
            backgroundColor: ['#063057', '#8dc63f'],
            borderWidth: 0,
            offset: [0, 6],
          }]
        },
        options: {
          cutout: '55%',
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          animation: false,
        },
      })
    }
    drawDonut(donut1Ref, chart1Ref, icQprog, icQreal)
    drawDonut(donut2Ref, chart2Ref, ipQcron, ipQprog)
    return () => {
      chart1Ref.current?.destroy()
      chart2Ref.current?.destroy()
    }
  }, [icQprog, icQreal, ipQcron, ipQprog])

  // Anterior + atual + 2 à frente = 4 semanas
  // Janela normal: 1 anterior + atual + 2 à frente.
  // Expandido: do início do projeto até atual + 2 à frente (histórico completo).
  const semanasTabela = expandirHistorico
     semanas.slice(0, semanaAtualIdx + 3)
    : semanas.slice(Math.max(0, semanaAtualIdx - 1), semanaAtualIdx + 3)

  return (
    <div className="min-h-screen" style={{background:'#F2F2F0'}}>
      <div className="p-4 flex flex-col gap-3.5">

        {/* KPIs */}
        <div className="grid grid-cols-2 gap-3.5">
          <div className="card">
            <div style={{fontSize:10,color:'#555',marginBottom:10,display:'flex',alignItems:'center',gap:6}}>
              SEMANA ANTERIOR
              {semanaAnterior && <span style={{background:'#D3D1C7',color:'#444',fontSize:9,padding:'1px 6px',borderRadius:4,fontWeight:500}}>{semanaAnterior.codigo}</span>}
              <span style={{fontSize:10,color:'#999',marginLeft:2}}>{fmtPeriodo(semanaAnterior)}</span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              <KpiCard label="QCRON" value={indicadoresAnt?.qcron  '—'} sub="previsto" />
              <KpiCard label="QPROG" value={indicadoresAnt?.qprog  '—'} sub="programadas" />
              <KpiCard label="QREAL" value={indicadoresAnt?.qreal_concluidas  '—'} sub="executadas" />
              <KpiCard
                label="% Execução"
                value={indicadoresAnt  execPct(indicadoresAnt) + '%' : '—'}
                sub="QREAL / QPROG"
                destaque
                valueColor={execColor(execPct(indicadoresAnt))}
              />
            </div>
          </div>
          <div className="card">
            <div style={{fontSize:10,color:'#555',marginBottom:10,display:'flex',alignItems:'center',gap:6}}>
              SEMANA CORRENTE
              {semanaAtual && <span style={{background:'#185FA5',color:'white',fontSize:9,padding:'1px 6px',borderRadius:4,fontWeight:500}}>{semanaAtual.codigo}</span>}
              <span style={{fontSize:10,color:'#999',marginLeft:2}}>{fmtPeriodo(semanaAtual)}</span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              <KpiCard label="QCRON" value={indicadores?.qcron  '—'} sub="previsto" />
              <KpiCard label="QPROG" value={indicadores?.qprog  '—'} sub="programadas" />
              <KpiCard label="QREAL" value={indicadores?.qreal_concluidas  '—'} sub="executadas" />
              <KpiCard
                label="% Execução"
                value={indicadores  execPct(indicadores) + '%' : '—'}
                sub="QREAL / QPROG"
                destaque
                valueColor={execColor(execPct(indicadores))}
              />
            </div>
          </div>
        </div>

        {/* Mid row */}
        <div className="grid grid-cols-2 gap-3.5">
          <div className="card">
            <div style={{display:'flex',alignItems:'center',marginBottom:8}}>
              <div className="section-label" style={{marginBottom:0}}>Projeção — Semanas</div>
              <button
                onClick={() => setExpandirHistorico(v => !v)}
                style={{
                  marginLeft:'auto', fontSize:10, color:'#185FA5', background:'none',
                  border:'1px solid #185FA5', borderRadius:4, padding:'2px 8px',
                  cursor:'pointer', fontWeight:500,
                }}
              >
                {expandirHistorico  '▲ Recolher' : '▼ Ver histórico completo'}
              </button>
            </div>
            <div style={expandirHistorico  {maxHeight:340,overflowY:'auto',borderRadius:6} : {}}>
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
              <thead style={{position: expandirHistorico  'sticky' : 'static', top:0, background:'white', zIndex:1}}>
                <tr>
                  {['Semana','Período','QCRON','QPROG','QREAL','% Exec'].map((h,i) => (
                    <th key={h} style={{fontSize:10,color:'#999',fontWeight:500,textAlign:i>1?'right':'left',padding:'4px 8px',borderBottom:'0.5px solid #E0E0DC'}}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {semanasTabela.map(s => {
                  const isAtual = s.codigo === semanaAtual?.codigo
                  const isAnt = s.codigo === semanaAnterior?.codigo
                  const isFechada = s.fechada
                  const hasLive = !isFechada && (s.live_qcron  0) > 0
                  const pctSnap = s.snap_qprog > 0  Math.round(s.snap_qreal / s.snap_qprog * 100) : null
                  const pctLive = s.live_pct_exec  0
                  const rowStyle = isAtual
                     {background:'#EBF2FA',fontWeight:500,color:'#063057'}
                    : {color: isAnt  '#555' : '#999'}
                  return (
                    <tr key={s.codigo} ref={isAtual  rowAtualRef : null} style={rowStyle}>
                      <td style={{padding:'7px 8px',borderBottom:'0.5px solid #E0E0DC'}}>
                        {s.codigo}
                        {isAtual && <span style={{fontSize:9,background:'#185FA5',color:'white',padding:'1px 5px',borderRadius:3,fontWeight:500,marginLeft:4}}>atual</span>}
                        {isAnt && <span style={{fontSize:9,background:'#D3D1C7',color:'#444',padding:'1px 5px',borderRadius:3,fontWeight:500,marginLeft:4}}>ant</span>}
                        {isFechada && <span style={{fontSize:9,background:'#E0E0DC',color:'#555',padding:'1px 5px',borderRadius:3,fontWeight:500,marginLeft:4}}>✓</span>}
                      </td>
                      <td style={{padding:'7px 8px',borderBottom:'0.5px solid #E0E0DC',fontSize:11}}>{fmtPeriodo(s)}</td>
                      {/* QCRON: snapshot se fechada, live_qcron se importado mas aberto, — se vazio */}
                      <td style={{padding:'7px 8px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',fontWeight:isAtual?500:'normal',
                        color: isFechada  '#555' : hasLive  '#185FA5' : '#CCC'}}>
                        {isFechada  s.snap_qcron : hasLive  s.live_qcron : '—'}
                      </td>
                      {/* QPROG */}
                      <td style={{padding:'7px 8px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',
                        color: isFechada  '#185FA5' : hasLive  '#185FA5' : '#CCC'}}>
                        {isFechada  s.snap_qprog : hasLive  (s.live_qprog  '—') : '—'}
                      </td>
                      {/* QREAL */}
                      <td style={{padding:'7px 8px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',
                        color: isFechada  '#3B6D11' : hasLive  '#3B6D11' : '#CCC'}}>
                        {isFechada  s.snap_qreal : hasLive  (s.live_qreal  '—') : '—'}
                      </td>
                      {/* % Exec */}
                      <td style={{padding:'7px 8px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',
                        color: isFechada  execColor(pctSnap) : hasLive  execColor(pctLive) : '#999',
                        fontWeight: (isFechada || hasLive)  500 : 'normal'}}>
                        {isFechada && pctSnap !== null  pctSnap + '%'
                          : hasLive  pctLive + '%'
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            </div>
          </div>

          <div className="card">
            <div className="section-label">Indicadores</div>

            <div className="grid grid-cols-2 gap-3">
              {/* Donut 1 — ICPROG (anterior): QREAL / QPROG */}
              <DonutBlock
                subtitulo={`Semana ${semanaAnterior?.codigo || '—'}`}
                titulo="QREAL / QPROG"
                canvasRef={donut1Ref}
                labels={[
                  { color:'#063057', titulo:'IC PROGRAMADO', valor: icQprog },
                  { color:'#8dc63f', titulo:'IC REAL',       valor: icQreal },
                ]}
                acumLabel="ICPROG- ACUM"
                acumPct={icPctAcum}
              />

              {/* Donut 2 — IPROG (atual + 2 à frente): QPROG / QCRON */}
              <DonutBlock
                subtitulo={`Semanas ${codProx || '—'}`}
                titulo="QPROG / QCRON"
                canvasRef={donut2Ref}
                labels={[
                  { color:'#063057', titulo:'IP PREVISTO',   valor: ipQcron },
                  { color:'#8dc63f', titulo:'IP PROGRAMADO', valor: ipQprog },
                ]}
                acumLabel="IPROG- ACUM"
                acumPct={ipPctAcum}
              />
            </div>
          </div>
        </div>

        {/* Bottom row */}
        {(() => {
          const justificativas = (() => { try { return JSON.parse(textos?.justificativas_atraso || '[]').filter(Boolean) } catch { return [] } })()
          const marcos = (() => { try { return JSON.parse(textos?.marcos_observacoes || '[]').filter(Boolean) } catch { return [] } })()
          return (
            <div className="grid grid-cols-2 gap-3.5">
              <div className="card">
                <div style={{display:'flex',alignItems:'center',marginBottom:8}}>
                  <div className="section-label" style={{marginBottom:0}}>Justificativas de Desvio</div>
                  <Link to={`/textos/${semanaAtual?.codigo}`} style={{fontSize:10,color:'#185FA5',marginLeft:'auto',textDecoration:'none'}}>editar</Link>
                </div>
                {justificativas.length === 0
                   <p style={{fontSize:12,color:'#999',fontStyle:'italic',margin:0}}>Nenhuma justificativa cadastrada. <Link to={`/textos/${semanaAtual?.codigo}`} style={{color:'#185FA5'}}>Adicionar</Link></p>
                  : <div style={{display:'flex',flexDirection:'column',gap:6}}>
                      {justificativas.map((j, i) => (
                        <div key={i} style={{display:'flex',gap:8,alignItems:'flex-start'}}>
                          <span style={{width:7,height:7,borderRadius:'50%',background:'#BA7517',marginTop:5,flexShrink:0,display:'inline-block'}}/>
                          <span style={{fontSize:12,color:'#333',lineHeight:1.4}}>{j}</span>
                        </div>
                      ))}
                    </div>
                }
              </div>
              <div className="card">
                <div style={{display:'flex',alignItems:'center',marginBottom:8}}>
                  <div className="section-label-green" style={{marginBottom:0}}>Marcos / Observações</div>
                  <Link to={`/textos/${semanaAtual?.codigo}`} style={{fontSize:10,color:'#185FA5',marginLeft:'auto',textDecoration:'none'}}>editar</Link>
                </div>
                {marcos.length === 0
                   <p style={{fontSize:12,color:'#999',fontStyle:'italic',margin:0}}>Nenhum marco cadastrado. <Link to={`/textos/${semanaAtual?.codigo}`} style={{color:'#185FA5'}}>Adicionar</Link></p>
                  : <div style={{display:'flex',flexDirection:'column',gap:6}}>
                      {marcos.map((m, i) => (
                        <div key={i} style={{display:'flex',gap:8,alignItems:'flex-start'}}>
                          <span style={{width:7,height:7,borderRadius:'50%',background:'#8dc63f',marginTop:5,flexShrink:0,display:'inline-block'}}/>
                          <span style={{fontSize:12,color:'#333',lineHeight:1.4}}>{m}</span>
                        </div>
                      ))}
                    </div>
                }
              </div>
            </div>
          )
        })()}

        {!semanaAtual && (
          <div className="card text-center py-8">
            <p style={{color:'#555',fontSize:14}}>Nenhuma semana configurada ainda.</p>
            <p style={{color:'#999',fontSize:12,marginTop:4}}>Importe um arquivo ou crie uma semana para começar.</p>
            <Link to="/importar" className="btn-navy inline-block mt-4 text-white no-underline px-4 py-2 rounded">
              Importar Arquivo
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

function KpiCard({ label, value, sub, destaque, valueColor }) {
  return (
    <div style={{background: destaque  '#E6F1FB' : '#F5F5F2',borderRadius:8,padding:'10px 12px'}}>
      <div style={{fontSize:10,color:'#555',marginBottom:4}}>{label}</div>
      <div style={{fontSize:22,fontWeight:500,color: valueColor || '#063057',lineHeight:1}}>{value}</div>
      <div style={{fontSize:10,color:'#999',marginTop:3}}>{sub}</div>
    </div>
  )
}

/**
 * Bloco de donut compacto: título sobre a fatia, donut centralizado,
 * legenda + valores embaixo, e badge ACUM no rodapé.
 *
 * As fatias são proporcionais aos dois `valor` em `labels` (não val/total).
 * O ACUM% é calculado independentemente pelo componente pai.
 */
function DonutBlock({ subtitulo, titulo, canvasRef, labels, acumLabel, acumPct }) {
  const fmtPct = (n) =>
    (Number.isFinite(n)  n : 0).toFixed(2).replace('.', ',') + '%'
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'stretch'}}>
      {/* Cabeçalho — semana(s) + descrição */}
      <div style={{
        background:'#063057', color:'white', textAlign:'center',
        fontSize:11, fontWeight:600, padding:'5px 6px', borderRadius:4,
        marginBottom:8, lineHeight:1.25,
      }}>
        <div>{subtitulo}</div>
        <div style={{fontSize:10,fontWeight:500,opacity:0.85}}>{titulo}</div>
      </div>

      {/* Donut centralizado */}
      <div style={{display:'flex',justifyContent:'center'}}>
        <canvas ref={canvasRef} width={130} height={130} />
      </div>

      {/* Legendas com valores */}
      <div style={{display:'flex',justifyContent:'center',gap:14,marginTop:8,flexWrap:'wrap'}}>
        {labels.map(l => (
          <div key={l.titulo} style={{display:'flex',alignItems:'center',gap:6}}>
            <span style={{width:9,height:9,background:l.color,borderRadius:2,flexShrink:0}}/>
            <div style={{fontSize:9,color:'#333',lineHeight:1.2,textAlign:'left'}}>
              <div style={{fontWeight:600}}>{l.titulo}</div>
              <div style={{fontSize:12,fontWeight:700,color:l.color}}>{l.valor}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Badge ACUM centralizado */}
      <div style={{display:'flex',justifyContent:'center',marginTop:10}}>
        <div style={{background:'#F0F0EC',borderRadius:4,padding:'4px 10px'}}>
          <span style={{fontSize:10,color:'#555',fontWeight:600,marginRight:6}}>{acumLabel}</span>
          <span style={{fontSize:13,fontWeight:700,color:'#063057'}}>{fmtPct(acumPct)}</span>
        </div>
      </div>
    </div>
  )
}
