// Folha 02/02 do relatório — KPIs, donuts, projeção de semanas,
// justificativas/marcos e clima. Toda a página é renderizada por este
// componente; o GerarPdf apenas o monta com os dados.

import { fmtPeriodo, execPct, execColor } from '../../utils/formatters'
import EtmHeader from './EtmHeader'
import DonutSvg from './DonutSvg'
import SecaoClima from './SecaoClima'

const parseLista = (raw) => {
  try { return JSON.parse(raw || '[]').filter(Boolean) }
  catch { return [] }
}

export default function SecaoIndicadores({
  semanaParam,
  semanaObj,
  semanaAntObj,
  indAtual,
  indAnt,
  indProx1,
  indProx2,
  semanaProx1,
  semanaProx2,
  textos,
  clima,
  semanasTabela,
}) {
  const justificativas = parseLista(textos?.justificativas_atraso)
  const marcos         = parseLista(textos?.marcos_observacoes)

  // ── ICPROG (semana anterior): QREAL / QPROG ─────────────────────────────
  const icQprog = indAnt?.qprog  0
  const icQreal = indAnt?.qreal_concluidas  0
  const icPctAcum = icQprog > 0  icQreal / icQprog * 100 : 0

  // ── IPROG (3 semanas: atual + 2 à frente): QPROG / QCRON ────────────────
  const ipQcron = (indAtual?.qcron  0) + (indProx1?.qcron  0) + (indProx2?.qcron  0)
  const ipQprog = (indAtual?.qprog  0) + (indProx1?.qprog  0) + (indProx2?.qprog  0)
  const ipPctAcum = ipQcron > 0  ipQprog / ipQcron * 100 : 0

  const codProx = [semanaObj, semanaProx1, semanaProx2]
    .filter(Boolean)
    .map(s => s.codigo)
    .join('/')

  return (
    <div className="pdf-page pdf-page-break" style={{paddingTop:0}}>
      <div style={{fontFamily:'system-ui,sans-serif',width:'100%',padding:'8px 0',fontSize:10,color:'#111',lineHeight:1.35}}>

        <EtmHeader semanaObj={semanaObj} folha="02/02" />

        <div style={{display:'grid',gridTemplateColumns:'minmax(0,38%) minmax(0,62%)',gap:8,marginTop:8,width:'100%',boxSizing:'border-box'}}>

          {/* COLUNA ESQUERDA: KPIs + Indicadores */}
          <div style={{display:'flex',flexDirection:'column',gap:8,minWidth:0,overflow:'hidden'}}>

            {/* KPIs */}
            {[
              { label: 'SEMANA ANTERIOR', cod: semanaAntObj?.codigo, periodo: fmtPeriodo(semanaAntObj), ind: indAnt },
              { label: 'SEMANA CORRENTE', cod: semanaParam, periodo: fmtPeriodo(semanaObj), ind: indAtual, destaque: true },
            ].map(({ label, cod, periodo, ind, destaque }) => (
              <div key={label} style={{border:`1px solid ${destaque?'#185FA5':'#E0E0DC'}`,borderRadius:6,padding:'8px 10px',background:destaque?'#F0F6FF':'white'}}>
                <div style={{fontSize:8,color:'#555',fontWeight:600,letterSpacing:'0.05em',marginBottom:6,display:'flex',gap:5,alignItems:'center',flexWrap:'wrap'}}>
                  {label}
                  {cod && <span style={{background:destaque?'#185FA5':'#D3D1C7',color:destaque?'white':'#444',fontSize:7,padding:'1px 4px',borderRadius:3,fontWeight:600}}>{cod}</span>}
                  <span style={{fontSize:8,color:'#999',fontWeight:400}}>{periodo}</span>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:5}}>
                  {[
                    ['QCRON',   ind?.qcron  '—',           '#555'],
                    ['QPROG',   ind?.qprog  '—',           '#185FA5'],
                    ['QREAL',   ind?.qreal_concluidas  '—', '#3B6D11'],
                    ['% Exec.', ind  execPct(ind)+'%' : '—', execColor(ind  execPct(ind) : 0)],
                  ].map(([l,v,c]) => (
                    <div key={l} style={{background:'#F5F5F2',borderRadius:4,padding:'5px 6px',textAlign:'center'}}>
                      <div style={{fontSize:7,color:'#555',marginBottom:2}}>{l}</div>
                      <div style={{fontSize:14,fontWeight:600,color:c,lineHeight:1}}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Indicadores — dois donuts: ICPROG (anterior) e IPROG (3 semanas) */}
            <div style={{border:'1px solid #E0E0DC',borderRadius:6,padding:'8px 10px',flex:1}}>
              <div style={{fontSize:8,fontWeight:600,color:'#063057',letterSpacing:'0.06em',textTransform:'uppercase',marginBottom:8,borderLeft:'3px solid #063057',paddingLeft:5}}>
                Indicadores
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
                <DonutSvg
                  subtitulo={`Semana ${semanaAntObj?.codigo || '—'}`}
                  titulo="QREAL / QPROG"
                  valAzul={icQprog} valVerde={icQreal}
                  labels={[
                    { color:'#063057', titulo:'IC PROGRAMADO', valor: icQprog },
                    { color:'#8dc63f', titulo:'IC REAL',       valor: icQreal },
                  ]}
                  acumLabel="ICPROG- ACUM"
                  acumPct={icPctAcum}
                />
                <DonutSvg
                  subtitulo={`Semanas ${codProx || '—'}`}
                  titulo="QPROG / QCRON"
                  valAzul={ipQcron} valVerde={ipQprog}
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

          {/* COLUNA DIREITA: Projeção + Justificativas/Marcos + Clima + Descrição */}
          <div style={{display:'flex',flexDirection:'column',gap:8,minWidth:0,overflow:'hidden'}}>

            {/* Projeção */}
            <div style={{border:'1px solid #E0E0DC',borderRadius:6,padding:'8px 10px'}}>
              <div style={{fontSize:8,fontWeight:600,color:'#063057',letterSpacing:'0.06em',textTransform:'uppercase',marginBottom:5,borderLeft:'3px solid #063057',paddingLeft:5}}>
                Projeção — Semanas
              </div>
              <table style={{width:'100%',borderCollapse:'collapse',fontSize:9}}>
                <thead>
                  <tr style={{background:'#F5F5F2'}}>
                    {['Semana','Período','QCRON','QPROG','QREAL','% Exec.'].map((h,i) => (
                      <th key={h} style={{padding:'4px 6px',fontSize:8,fontWeight:600,color:'#555',textAlign:i>1?'right':'left',borderBottom:'1px solid #E0E0DC'}}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {semanasTabela.map(s => {
                    const isAtual = s.codigo === semanaParam
                    const isAnt = s.codigo === semanaAntObj?.codigo
                    const isFechada = s.fechada
                    const hasLive = !isFechada && (s.live_qcron  0) > 0
                    const pctSnap = s.snap_qprog > 0  Math.round(s.snap_qreal / s.snap_qprog * 100) : null
                    const pctLive = s.live_pct_exec  0
                    return (
                      <tr key={s.codigo} style={{background:isAtual?'#EBF2FA':'white',fontWeight:isAtual?600:'normal',color:isAtual?'#063057':isAnt?'#555':'#999'}}>
                        <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC'}}>
                          {s.codigo}
                          {isAtual && <span style={{fontSize:6,background:'#185FA5',color:'white',padding:'1px 3px',borderRadius:2,marginLeft:3}}>atual</span>}
                          {isAnt && <span style={{fontSize:6,background:'#D3D1C7',color:'#444',padding:'1px 3px',borderRadius:2,marginLeft:3}}>ant</span>}
                          {isFechada && <span style={{fontSize:6,background:'#E0E0DC',color:'#555',padding:'1px 3px',borderRadius:2,marginLeft:3}}>✓</span>}
                        </td>
                        <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',fontSize:8}}>{fmtPeriodo(s)}</td>
                        <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right'}}>{isFechada?s.snap_qcron:hasLive?s.live_qcron:'—'}</td>
                        <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right'}}>{isFechada?s.snap_qprog:hasLive?(s.live_qprog?'—'):'—'}</td>
                        <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right'}}>{isFechada?s.snap_qreal:hasLive?(s.live_qreal?'—'):'—'}</td>
                        <td style={{padding:'4px 6px',borderBottom:'0.5px solid #E0E0DC',textAlign:'right',fontWeight:(isFechada||hasLive)?600:'normal',color:isFechada&&pctSnap!==null?execColor(pctSnap):hasLive?execColor(pctLive):undefined}}>
                          {isFechada && pctSnap !== null  pctSnap+'%' : hasLive  pctLive+'%' : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Justificativas + Marcos lado a lado */}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              <div style={{border:'1px solid #E0E0DC',borderRadius:6,padding:'8px 10px'}}>
                <div style={{fontSize:8,fontWeight:600,color:'#BA7517',letterSpacing:'0.06em',textTransform:'uppercase',marginBottom:5,borderLeft:'3px solid #BA7517',paddingLeft:5}}>Justificativas de Desvio</div>
                {justificativas.length === 0
                   <p style={{fontSize:9,color:'#999',fontStyle:'italic',margin:0}}>Nenhuma justificativa.</p>
                  : justificativas.map((j,i) => (
                    <div key={i} style={{display:'flex',gap:5,marginBottom:3}}>
                      <span style={{width:5,height:5,borderRadius:'50%',background:'#BA7517',marginTop:3,flexShrink:0,display:'inline-block'}}/>
                      <span style={{fontSize:9,color:'#333'}}>{j}</span>
                    </div>
                  ))}
              </div>
              <div style={{border:'1px solid #E0E0DC',borderRadius:6,padding:'8px 10px'}}>
                <div style={{fontSize:8,fontWeight:600,color:'#3B6D11',letterSpacing:'0.06em',textTransform:'uppercase',marginBottom:5,borderLeft:'3px solid #8dc63f',paddingLeft:5}}>Marcos / Observações</div>
                {marcos.length === 0
                   <p style={{fontSize:9,color:'#999',fontStyle:'italic',margin:0}}>Nenhum marco.</p>
                  : marcos.map((m,i) => (
                    <div key={i} style={{display:'flex',gap:5,marginBottom:3}}>
                      <span style={{width:5,height:5,borderRadius:'50%',background:'#8dc63f',marginTop:3,flexShrink:0,display:'inline-block'}}/>
                      <span style={{fontSize:9,color:'#333'}}>{m}</span>
                    </div>
                  ))}
              </div>
            </div>

            <SecaoClima clima={clima} nota={textos?.nota_clima} />

            {textos?.descricao_resumida && (
              <div style={{border:'1px solid #E0E0DC',borderRadius:6,padding:'8px 10px'}}>
                <div style={{fontSize:8,fontWeight:600,color:'#063057',textTransform:'uppercase',marginBottom:4,borderLeft:'3px solid #063057',paddingLeft:5}}>Descrição Resumida</div>
                <p style={{fontSize:9,color:'#333',margin:0,lineHeight:1.5}}>{textos.descricao_resumida}</p>
              </div>
            )}

          </div>
        </div>

        {/* Rodapé */}
        <div style={{borderTop:'1px solid #E0E0DC',paddingTop:6,display:'flex',justifyContent:'space-between',fontSize:8,color:'#999',marginTop:10}}>
          <span>ETM Engenharia · URFCC — Petrobras</span>
          <span style={{fontWeight:600,color:'#666'}}>Página 2</span>
        </div>

      </div>
    </div>
  )
}
