// Donut SVG de duas fatias proporcionais (sem dependência do Chart.js).
// Usado na Folha 02/02 do relatório para os indicadores ICPROG e IPROG.
//
// As fatias mostram os dois `valor` em `labels` lado a lado (não val/total).
// O ACUM% é calculado externamente e exibido como badge separado.

const fmtPct = (n) =>
  (Number.isFinite(n)  n : 0).toFixed(2).replace('.', ',') + '%'

export default function DonutSvg({
  subtitulo, titulo,
  valAzul, valVerde,
  labels = [],
  acumLabel, acumPct,
}) {
  const size = 80
  const strokeW = 14
  const r = (size - strokeW) / 2
  const cx = size / 2
  const cy = size / 2
  const circ = 2 * Math.PI * r

  const total = (valAzul || 0) + (valVerde || 0)
  const fAzul  = total > 0  (valAzul  || 0) / total : 0
  const fVerde = total > 0  (valVerde || 0) / total : 0
  const dashAzul  = fAzul  * circ
  const dashVerde = fVerde * circ

  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'stretch'}}>
      {/* Cabeçalho azul — semana(s) + descrição */}
      <div style={{
        background:'#063057', color:'white', textAlign:'center',
        fontSize:7.5, fontWeight:600, padding:'3px 4px', borderRadius:3,
        marginBottom:5, lineHeight:1.2,
      }}>
        <div>{subtitulo}</div>
        <div style={{fontSize:6.5,fontWeight:500,opacity:0.85}}>{titulo}</div>
      </div>

      {/* Donut centralizado */}
      <div style={{display:'flex',justifyContent:'center'}}>
        <svg width={size} height={size} style={{transform:'rotate(-90deg)'}}>
          {/* Fatia azul */}
          {fAzul > 0 && (
            <circle
              cx={cx} cy={cy} r={r}
              fill="none" stroke="#063057" strokeWidth={strokeW}
              strokeDasharray={`${dashAzul} ${circ - dashAzul}`}
              strokeDashoffset={0}
            />
          )}
          {/* Fatia verde — começa após a azul */}
          {fVerde > 0 && (
            <circle
              cx={cx} cy={cy} r={r}
              fill="none" stroke="#8dc63f" strokeWidth={strokeW}
              strokeDasharray={`${dashVerde} ${circ - dashVerde}`}
              strokeDashoffset={-dashAzul}
            />
          )}
          {/* Fundo cinza quando ambos os valores são zero */}
          {total === 0 && (
            <circle
              cx={cx} cy={cy} r={r}
              fill="none" stroke="#D3D1C7" strokeWidth={strokeW}
            />
          )}
        </svg>
      </div>

      {/* Legendas com valores */}
      <div style={{display:'flex',justifyContent:'center',gap:8,marginTop:5,flexWrap:'wrap'}}>
        {labels.map(l => (
          <div key={l.titulo} style={{display:'flex',alignItems:'center',gap:4}}>
            <span style={{width:7,height:7,background:l.color,borderRadius:1.5,flexShrink:0,display:'inline-block'}}/>
            <div style={{fontSize:6.5,color:'#333',lineHeight:1.15,textAlign:'left'}}>
              <div style={{fontWeight:600}}>{l.titulo}</div>
              <div style={{fontSize:9,fontWeight:700,color:l.color}}>{l.valor}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Badge ACUM */}
      <div style={{display:'flex',justifyContent:'center',marginTop:6}}>
        <div style={{background:'#F0F0EC',borderRadius:3,padding:'2px 6px'}}>
          <span style={{fontSize:7,color:'#555',fontWeight:600,marginRight:4}}>{acumLabel}</span>
          <span style={{fontSize:9,fontWeight:700,color:'#063057'}}>{fmtPct(acumPct)}</span>
        </div>
      </div>
    </div>
  )
}
