// Página "Avanço Financeiro" — Curva-S + KPIs EVM + Resumo por Fase (Fase 2).
//
// Mostra:
//   1. KPIs (BAC, PV, EV, SPI, Variance)
//   2. Curva-S mensal (PV previsto vs EV realizado via BMs fechados, acumulado)
//   3. Resumo por Fase (comparativo previsto × realizado para o mês selecionado)
//   4. Histórico de BMs fechados + Evolução Mensal

import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useSemana } from '../context/SemanaContext'
import {
  bmDashboardCurvaS,
  bmDashboardKpis,
  bmDashboardHistorico,
  importarEap,
  getResumoFases,
} from '../api'
import { logError } from '../utils/errors'

const fmtBRL = (v) => 'R$ ' + (v  0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtBRLm = (v) => 'R$ ' + ((v  0) / 1_000_000).toFixed(2) + ' mi'
// Formato compacto: M / k / valor exato — para colunas R$ do período
const fmtBRLc = (v) => {
  const n = v  0
  const abs = Math.abs(n)
  if (abs >= 1_000_000) return 'R$ ' + (n / 1_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' M'
  if (abs >= 1_000)     return 'R$ ' + (n / 1_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' k'
  return 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}
const fmtPct2 = (v) => ((v  0) * 100).toFixed(2).replace('.', ',') + '%'
const fmtPctKpi = (v) => (v  0).toFixed(2).replace('.', ',') + '%'

const spiColor = (spi) => spi >= 0.95  '#3B6D11' : spi >= 0.80  '#BA7517' : '#A32D2D'
const spiLabel = (spi) => spi >= 1.0  'Adiantado' : spi >= 0.95  'Em dia' : spi >= 0.80  'Atenção' : 'Atrasado'

const MES_PT = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
                7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}

function labelMes(isoData) {
  if (!isoData) return '—'
  // Aceita tanto ISO "AAAA-MM-DD" quanto a competência "AAAA/MM" devolvida
  // pelos KPIs (competencia_referencia). Antes, split('-') em "2026/06"
  // produzia "undefined/N".
  const [ano, mes] = String(isoData).split(/[-/]/).map(Number)
  if (!ano || !mes) return '—'
  return `${MES_PT[mes]}/${String(ano).slice(2)}`
}

export default function Financeiro() {
  const { semanaAtual } = useSemana()
  const [pontos, setPontos] = useState([])
  const [kpis, setKpis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState(null)
  const [importando, setImportando] = useState(false)
  const [mesSelecionado, setMesSelecionado] = useState(null)
  const [resumoFases, setResumoFases] = useState(null)
  const [historicoBM, setHistoricoBM] = useState([])
  const [zoomX, setZoomX] = useState(1)
  const [zoomY, setZoomY] = useState(1)
  const [hoverPonto, setHoverPonto] = useState(null)

  const carregar = () => {
    setLoading(true)
    setErro(null)
    // Dashboard lê SOMENTE dados consolidados (BMs fechados)
    Promise.all([
      bmDashboardCurvaS(),
      bmDashboardKpis().catch(() => null),
      bmDashboardHistorico().catch(() => []),
    ])
      .then(([c, k, h]) => {
        setPontos(c)
        setKpis(k)
        setHistoricoBM(h)
        if (c.length > 0 && !mesSelecionado) {
          const hoje = new Date().toISOString().slice(0, 10)
          const idx = Math.max(0, c.findIndex(p => p.data >= hoje) - 1)
          setMesSelecionado(c[idx]?.data || c[0].data)
        }
      })
      .catch(e => {
        logError('Financeiro:carregar')(e)
        setErro(e.response?.data?.detail || e.message)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { carregar() }, [])

  // Carrega resumo de fases quando o mês selecionado muda
  useEffect(() => {
    if (!mesSelecionado) return
    const [ano, mes] = mesSelecionado.split('-').map(Number)
    getResumoFases(ano, mes).then(setResumoFases).catch(() => setResumoFases(null))
  }, [mesSelecionado])

  const handleImport = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!confirm(`Importar EAP "${file.name}" Isso substitui a EAP atual.`)) {
      e.target.value = ''
      return
    }
    setImportando(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await importarEap(fd)
      alert(`EAP importada: ${res.itens_total} itens (${res.itens_folha} folhas), ${res.meses.length} meses, R$ ${res.valor_total.toLocaleString('pt-BR')}`)
      carregar()
    } catch (e2) {
      alert('Erro ao importar EAP: ' + (e2.response?.data?.detail || e2.message))
    } finally {
      setImportando(false)
      e.target.value = ''
    }
  }

  const semDados = !loading && pontos.length === 0

  // Curva-S — coordenadas SVG. Margens fixas; largura 100% via viewBox.
  const svgW = 980, svgH = 320
  const ml = 70, mr = 18, mt = 18, mb = 40
  const W = svgW - ml - mr, H = svgH - mt - mb
  const dataMaxAcum = useMemo(() => {
    if (pontos.length === 0) return 1
    return Math.max(...pontos.map(p => Math.max(p.pv_acum, p.ev_acum))) * 1.05
  }, [pontos])
  const maxAcum = dataMaxAcum / zoomY
  const chartWidth = `${Math.round(zoomX * 100)}%`

  const xPos = (i) => pontos.length <= 1  ml : ml + (i * W) / (pontos.length - 1)
  const yPos = (v) => mt + H - (v / maxAcum) * H

  const pvPath = pontos.map((p, i) => `${i === 0  'M' : 'L'} ${xPos(i)} ${yPos(p.pv_acum)}`).join(' ')
  const evPath = pontos
    .filter(p => p.ev_acum > 0)
    .map((p, i, arr) => `${i === 0  'M' : 'L'} ${xPos(pontos.indexOf(p))} ${yPos(p.ev_acum)}`)
    .join(' ')

  const mesSelecionadoLabel = mesSelecionado  labelMes(mesSelecionado) : '—'
  const medicaoDetalhadaUrl = mesSelecionado
     `/medicao/${Number(mesSelecionado.slice(0, 4))}/${Number(mesSelecionado.slice(5, 7))}?view=1`
    : '/medicao?view=1'
  const pvKpi = kpis?.pv_acum_referencia  kpis?.pv
  const evKpi = kpis?.ev_acum_referencia  kpis?.ev
  const spiKpi = kpis?.spi_referencia  kpis?.spi
  const pctPvKpi = kpis?.pct_pv_referencia  kpis?.pct_pv
  const pctEvKpi = kpis?.pct_ev_referencia  kpis?.pct_ev
  const competenciaKpi = kpis?.competencia_referencia  labelMes(kpis.competencia_referencia) : mesSelecionadoLabel
  const tooltipBac = kpis?.bac || pontos[pontos.length - 1]?.pv_acum || 0
  const hoverEvMes = hoverPonto && hoverPonto.ev_mes > 0  hoverPonto.ev_mes : null
  const hoverDesvio = hoverPonto && hoverEvMes != null  hoverEvMes - hoverPonto.pv_mes : null
  const openHoverFases = () => {
    if (!hoverPonto) return
    setMesSelecionado(hoverPonto.data)
    setHoverPonto(null)
    setTimeout(() => {
      const alvo = [...document.querySelectorAll('div')]
        .find(el => /^Resumo por Fase/.test((el.textContent || '').trim()))
      alvo?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  }

  return (
    <div className="min-h-screen p-4" style={{background:'#F2F2F0'}}>
      <div className="flex items-center gap-3 mb-3">
        <h1 style={{fontSize:18,fontWeight:600,color:'#063057'}}>Avanço Financeiro</h1>
        <span style={{fontSize:11,color:'#777'}}>{semanaAtual?.codigo} · curva-S financeira e EVM</span>
        <div style={{marginLeft:'auto',display:'flex',gap:8,alignItems:'center'}}>
          <label style={{cursor:'pointer'}}>
            <input type="file" accept=".xlsx" onChange={handleImport} style={{display:'none'}} disabled={importando} />
            <span className="btn-navy" style={{display:'inline-block'}}>
              {importando  'Importando…' : '⬆ Importar EAP'}
            </span>
          </label>
          <Link to="/eap/mapear" className="btn-navy" style={{background:'#185FA5'}}>
            🔗 Mapear Tarefas
          </Link>
        </div>
      </div>

      {erro && (
        <div className="card" style={{background:'#FCEBEB',color:'#A32D2D',marginBottom:12}}>
          Erro ao carregar dados: {erro}
        </div>
      )}

      {semDados && !erro && (
        <div className="card text-center" style={{padding:'40px 20px'}}>
          <p style={{color:'#555',fontSize:14}}>Nenhuma EAP importada ainda.</p>
          <p style={{color:'#999',fontSize:12,marginTop:6}}>
            Clique em "⬆ Importar EAP" e selecione o XLSX da Petrobras (revisão atual).
          </p>
        </div>
      )}

      {!semDados && (
        <>
          {/* KPIs — somente BMs fechados */}
          {kpis && (
            <>
              {kpis.ultimo_bm && (
                <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 6 }}>
                  Dados consolidados até o BM {kpis.ultimo_bm} · somente BMs fechados
                </div>
              )}
              <div className="grid grid-cols-4 gap-3 mb-3">
                <KpiCard label="Orçamento (BAC)" value={fmtBRLm(kpis.bac)} sub={fmtBRL(kpis.bac)} color="#063057" />
                <KpiCard label="Previsto (PV acum.)" value={fmtBRLm(pvKpi)} sub={`${fmtPctKpi(pctPvKpi)} do contrato - ref. ${competenciaKpi}`} color="#185FA5" />
                <KpiCard label="Realizado (EV acum.)" value={fmtBRLm(evKpi)} sub={`${fmtPctKpi(pctEvKpi)} do contrato`} color="#3B6D11" />
                <KpiCard
                  label={`SPI - ${spiLabel(spiKpi)}`}
                  value={(spiKpi || 0).toFixed(3).replace('.', ',')}
                  sub={`Variance ${kpis.cv_pct >= 0  '+' : ''}${fmtPctKpi(kpis.cv_pct)} · VAC ${fmtBRLm(kpis.vac)}`}
                  color={spiColor(spiKpi)}
                />
              </div>
              {kpis.cobertura_escopo_pct != null && (
                <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 12 }}>
                  Cobertura do escopo medido: <strong>{fmtPctKpi(kpis.cobertura_escopo_pct)}</strong> do contrato
                  {' '}· SPI, PV, EV, EAC e VAC refletem apenas as folhas medidas no BM (não o contrato inteiro).
                </div>
              )}
            </>
          )}

          {/* Curva-S — full width */}
          <div className="card mb-3">
            <div style={{display:'flex',alignItems:'center',gap:14,flexWrap:'wrap',marginBottom:8}}>
              <div style={{fontSize:12,fontWeight:600,color:'#063057'}}>
                Curva-S Financeira (acumulado)
              </div>
              <label style={{fontSize:10,color:'#555',display:'flex',alignItems:'center',gap:6,marginLeft:'auto'}}>
                Zoom X
                <input type="range" min="0.75" max="2.5" step="0.05" value={zoomX} onChange={e => setZoomX(Number(e.target.value))} style={{width:110}} />
              </label>
              <label style={{fontSize:10,color:'#555',display:'flex',alignItems:'center',gap:6}}>
                Zoom Y
                <input type="range" min="0.6" max="2.2" step="0.05" value={zoomY} onChange={e => setZoomY(Number(e.target.value))} style={{width:110}} />
              </label>
              <button type="button" onClick={() => { setZoomX(1); setZoomY(1) }} style={{fontSize:10,border:'1px solid #D0D0CC',borderRadius:4,padding:'3px 8px',background:'#fff',color:'#555'}}>
                Reset
              </button>
            </div>
            <div style={{overflowX:'auto'}}>
            <svg viewBox={`0 0 ${svgW} ${svgH}`} style={{width:chartWidth,minWidth:'100%',height:'auto'}}>
              <defs>
                <clipPath id="curvaClip">
                  <rect x={ml} y={mt} width={W} height={H} />
                </clipPath>
              </defs>
              {[0, 0.25, 0.5, 0.75, 1].map(f => {
                const y = yPos(f * maxAcum)
                return (
                  <g key={f}>
                    <line x1={ml} y1={y} x2={ml + W} y2={y} stroke="#E0E0DC" strokeWidth={0.5} />
                    <text x={ml - 6} y={y + 3} fontSize={9} fill="#777" textAnchor="end">
                      {fmtBRLm(f * maxAcum)}
                    </text>
                  </g>
                )
              })}
              {pontos.map((p, i) => {
                const labelStep = zoomX >= 1.8  1 : zoomX >= 1.25  2 : 3
                if (i % labelStep !== 0 && i !== pontos.length - 1) return null
                return (
                  <text key={p.data} x={xPos(i)} y={mt + H + 14} fontSize={9} fill="#555" textAnchor="middle">
                    {p.label}
                  </text>
                )
              })}
              <g clipPath="url(#curvaClip)">
                <path d={pvPath} fill="none" stroke="#185FA5" strokeWidth={2} />
                {evPath && <path d={evPath} fill="none" stroke="#3B6D11" strokeWidth={2.5} />}
                {pontos.map((p, i) => (
                  <g
                    key={p.data}
                    onClick={() => setMesSelecionado(p.data)}
                    onMouseMove={e => setHoverPonto({ ...p, x: e.clientX, y: e.clientY })}
                    onMouseEnter={e => setHoverPonto({ ...p, x: e.clientX, y: e.clientY })}
                    onMouseLeave={() => setTimeout(() => setHoverPonto(null), 250)}
                    style={{cursor:'pointer'}}
                  >
                    <circle cx={xPos(i)} cy={yPos(p.pv_acum)} r={3} fill="#185FA5" />
                    {p.ev_acum > 0 && <circle cx={xPos(i)} cy={yPos(p.ev_acum)} r={3} fill="#3B6D11" />}
                    {mesSelecionado === p.data && (
                      <line x1={xPos(i)} y1={mt} x2={xPos(i)} y2={mt + H} stroke="#FFA500" strokeDasharray="3 3" strokeWidth={1} />
                    )}
                    <rect x={xPos(i) - 10} y={mt} width={20} height={H} fill="transparent" />
                  </g>
                ))}
              </g>
              <g transform={`translate(${ml},${mt - 8})`}>
                <line x1={0} y1={0} x2={20} y2={0} stroke="#185FA5" strokeWidth={2} />
                <text x={26} y={3} fontSize={10} fill="#555">PV — Previsto</text>
                <line x1={120} y1={0} x2={140} y2={0} stroke="#3B6D11" strokeWidth={2.5} />
                <text x={146} y={3} fontSize={10} fill="#555">EV — Realizado (BMs fechados)</text>
              </g>
            </svg>
            </div>
            {hoverPonto && (
              <div
                onMouseEnter={() => setHoverPonto(hoverPonto)}
                onMouseLeave={() => setHoverPonto(null)}
                style={{
                  position: 'fixed',
                  left: Math.min(window.innerWidth - 290, hoverPonto.x + 14),
                  top: Math.min(window.innerHeight - 150, hoverPonto.y + 14),
                  zIndex: 50,
                  minWidth: 260,
                  background: '#fff',
                  border: '1px solid #cbd5e1',
                  borderRadius: 8,
                  boxShadow: '0 12px 32px rgba(15,23,42,.18)',
                  padding: '10px 12px',
                  fontSize: 12,
                  color: '#1f2937',
                }}
              >
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,marginBottom:8}}>
                  <strong style={{fontSize:13,color:'#063057'}}>{hoverPonto.label}</strong>
                  <button type="button" onClick={openHoverFases} style={{border:'1px solid #185FA5',background:'#185FA5',color:'#fff',borderRadius:5,padding:'4px 8px',fontSize:11,cursor:'pointer'}}>
                    Resumo por fase
                  </button>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'82px 1fr 70px',gap:5,alignItems:'baseline'}}>
                  <span style={{color:'#64748b'}}>Previsto</span>
                  <strong style={{color:'#185FA5',textAlign:'right'}}>{fmtBRL(hoverPonto.pv_mes)}</strong>
                  <span style={{textAlign:'right',color:'#185FA5'}}>{fmtPctKpi(tooltipBac  hoverPonto.pv_mes / tooltipBac * 100 : 0)}</span>
                  <span style={{color:'#64748b'}}>Real</span>
                  <strong style={{color:'#3B6D11',textAlign:'right'}}>{hoverEvMes == null  '-' : fmtBRL(hoverEvMes)}</strong>
                  <span style={{textAlign:'right',color:'#3B6D11'}}>{hoverEvMes == null  '-' : fmtPctKpi(tooltipBac  hoverEvMes / tooltipBac * 100 : 0)}</span>
                  <span style={{color:'#64748b'}}>Desvio</span>
                  <strong style={{textAlign:'right',color:hoverDesvio == null  '#6b7280' : hoverDesvio >= 0  '#166534' : '#b91c1c'}}>{hoverDesvio == null  '-' : fmtBRL(hoverDesvio)}</strong>
                  <span style={{textAlign:'right',color:hoverDesvio == null  '#6b7280' : hoverDesvio >= 0  '#166534' : '#b91c1c'}}>{hoverDesvio == null  '-' : fmtPctKpi(tooltipBac  hoverDesvio / tooltipBac * 100 : 0)}</span>
                </div>
              </div>
            )}
          </div>

          {/* 3 colunas: Resumo Fases (col-span-2) | Histórico BM + Evolução Mensal */}
          <div style={{display:'grid',gridTemplateColumns:'2fr 1fr',gap:12}}>

            {/* Seção A — Resumo por Fase */}
            <div className="card" style={{overflow:'auto'}}>
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8,position:'sticky',top:0,background:'white',paddingBottom:4,zIndex:1}}>
                <div style={{fontSize:12,fontWeight:600,color:'#063057'}}>
                  Resumo por Fase — {mesSelecionadoLabel}
                </div>
                <Link
                  to={medicaoDetalhadaUrl}
                  style={{
                    marginLeft:'auto',
                    border:'1px solid #185FA5',
                    background:'#185FA5',
                    color:'#fff',
                    borderRadius:5,
                    padding:'4px 9px',
                    fontSize:10,
                    fontWeight:600,
                    textDecoration:'none',
                    whiteSpace:'nowrap',
                  }}
                >
                  Medição detalhada
                </Link>
              </div>
              {!resumoFases  (
                <p style={{fontSize:11,color:'#999',fontStyle:'italic'}}>Selecione um mês na curva para ver o comparativo por fase.</p>
              ) : (
                <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
                  <thead>
                    <tr style={{background:'#F5F5F2'}}>
                      {[
                        {h:'Fase',         al:'left'},
                        {h:'Valor R$',     al:'right'},
                        {h:'Prev. %',      al:'right'},
                        {h:'Prev. R$',     al:'right'},
                        {h:'Real %',       al:'right'},
                        {h:'Real R$',      al:'right'},
                        {h:'Desvio %',     al:'right'},
                        {h:'Prev. Acum.',  al:'right'},
                        {h:'Real Acum.',   al:'right'},
                      ].map(({h, al}) => (
                        <th key={h} style={{
                          padding:'4px 6px',fontSize:9,fontWeight:600,color:'#555',
                          textAlign: al, borderBottom:'0.5px solid #E0E0DC', whiteSpace:'nowrap',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resumoFases.fases.map(f => (
                      <tr key={f.codigo} style={{borderBottom:'0.25px solid #ECECE8'}}>
                        <td style={{padding:'4px 6px',fontWeight:500,color:'#063057',fontSize:10}}>{f.descricao}</td>
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#555',fontSize:10}}>{fmtBRLm(f.valor)}</td>
                        {/* Previsto Período */}
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#185FA5'}}>{fmtPct2(f.pct_previsto_periodo)}</td>
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#185FA5',fontSize:10}}>{fmtBRLc(f.valor_previsto_periodo)}</td>
                        {/* Realizado Período */}
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#3B6D11'}}>{fmtPct2(f.pct_realizado_periodo)}</td>
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#3B6D11',fontSize:10}}>{fmtBRLc(f.valor_realizado_periodo)}</td>
                        {/* Desvio */}
                        <td style={{
                          padding:'4px 6px',textAlign:'right',fontWeight:600,
                          color: f.desvio_periodo >= 0  '#3B6D11' : '#A32D2D',
                        }}>
                          {f.desvio_periodo >= 0  '+' : ''}{fmtPct2(f.desvio_periodo)}
                        </td>
                        {/* Acumulado */}
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#185FA5'}}>{fmtPct2(f.pct_previsto_acum)}</td>
                        <td style={{padding:'4px 6px',textAlign:'right',color:'#3B6D11'}}>{fmtPct2(f.pct_realizado_acum)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr style={{background:'#063057',color:'white',fontWeight:600}}>
                      <td style={{padding:'5px 6px',fontSize:11}}>TOTAL</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:11}}>{fmtBRLm(resumoFases.bac)}</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:11}}>{fmtPct2(resumoFases.total_pct_prev_periodo)}</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:10,color:'#a5c8f0'}}>{fmtBRLc(resumoFases.total_valor_prev_periodo)}</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:11}}>{fmtPct2(resumoFases.total_pct_real_periodo)}</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:10,color:'#a5f0c8'}}>{fmtBRLc(resumoFases.total_valor_real_periodo)}</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:11}}>
                        {(() => {
                          const dev = resumoFases.total_pct_real_periodo - resumoFases.total_pct_prev_periodo
                          return (dev >= 0  '+' : '') + fmtPct2(dev)
                        })()}
                      </td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:11}}>{fmtPct2(resumoFases.total_pct_prev_acum)}</td>
                      <td style={{padding:'5px 6px',textAlign:'right',fontSize:11}}>{fmtPct2(resumoFases.total_pct_real_acum)}</td>
                    </tr>
                  </tfoot>
                </table>
              )}
            </div>

            {/* Coluna direita: Histórico BM + Evolução Mensal */}
            <div style={{display:'flex',flexDirection:'column',gap:12}}>

              {/* Seção B — Histórico de BMs */}
              <div className="card" style={{maxHeight:280,overflow:'auto'}}>
                <div style={{fontSize:12,fontWeight:600,color:'#063057',marginBottom:8,position:'sticky',top:0,background:'white',paddingBottom:4}}>
                  BMs Fechados
                </div>
                {historicoBM.length === 0  (
                  <p style={{fontSize:11,color:'#999',fontStyle:'italic'}}>Nenhum BM fechado ainda.</p>
                ) : (
                  <div style={{display:'flex',flexDirection:'column',gap:4}}>
                    {historicoBM.map(bm => {
                      const isoData = `${bm.ano}-${String(bm.mes).padStart(2,'0')}-01`
                      const selecionado = mesSelecionado === isoData
                      return (
                        <div
                          key={bm.ciclo_id}
                          onClick={() => setMesSelecionado(isoData)}
                          style={{
                            display:'flex',alignItems:'center',gap:8,
                            padding:'6px 10px',borderRadius:8,cursor:'pointer',
                            background: selecionado  '#E8F0FA' : '#FAFAF8',
                            border: `0.5px solid ${selecionado  '#185FA5' : '#E0E0DC'}`,
                          }}
                        >
                          <span style={{fontSize:12,fontWeight:700,color:'#063057',minWidth:48}}>{bm.label}</span>
                          <span style={{fontSize:11,color:'#3B6D11',fontWeight:600,minWidth:52}}>{fmtPct2(bm.pct_acum)}</span>
                          <span style={{fontSize:11,color:'#555'}}>{fmtBRLm(bm.ev_acumulado  bm.ev_acum)}</span>
                          {bm.fechado_em && (
                            <span style={{fontSize:9,color:'#999',marginLeft:'auto'}}>
                              {bm.fechado_em.slice(0,10)}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Seção C — Evolução Mensal */}
              <div className="card" style={{maxHeight:280,overflow:'auto'}}>
                <div style={{fontSize:12,fontWeight:600,color:'#063057',marginBottom:8,position:'sticky',top:0,background:'white',paddingBottom:4}}>
                  Evolução Mensal
                </div>
                <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
                  <thead>
                    <tr style={{background:'#F5F5F2'}}>
                      {['Mês', 'PV mês', 'EV mês', 'PV acum.', 'EV acum.'].map((h,i) => (
                        <th key={h} style={{padding:'4px 6px',fontSize:9,fontWeight:500,color:'#555',
                          textAlign:i===0?'left':'right',borderBottom:'0.5px solid #E0E0DC'}}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pontos.map(p => {
                      const sel = p.data === mesSelecionado
                      return (
                        <tr key={p.data}
                            onClick={() => setMesSelecionado(p.data)}
                            style={{
                              background: sel  '#FFF5E0' : 'white',
                              cursor:'pointer',
                              fontWeight: sel  600 : 'normal',
                            }}>
                          <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC'}}>{p.label}</td>
                          <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',color:'#185FA5'}}>{fmtBRLm(p.pv_mes)}</td>
                          <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',color:'#3B6D11'}}>{p.ev_mes > 0  fmtBRLm(p.ev_mes) : '—'}</td>
                          <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right'}}>{fmtBRLm(p.pv_acum)}</td>
                          <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right'}}>{p.ev_acum > 0  fmtBRLm(p.ev_acum) : '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

            </div>
          </div>
        </>
      )}
    </div>
  )
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div className="card" style={{padding:'10px 14px'}}>
      <div style={{fontSize:9,color:'#555',fontWeight:600,letterSpacing:'0.05em',textTransform:'uppercase'}}>{label}</div>
      <div style={{fontSize:22,fontWeight:600,color: color || '#063057',marginTop:4,lineHeight:1.1}}>{value}</div>
      <div style={{fontSize:10,color:'#999',marginTop:3}}>{sub}</div>
    </div>
  )
}

