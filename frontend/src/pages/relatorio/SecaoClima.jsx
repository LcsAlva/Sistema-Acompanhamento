// Seção de condições climáticas (Folha 02/02 do relatório).
// Recebe a previsão de 7 dias da Open-Meteo já normalizada.

const WMO_EMOJI = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌦️', 55: '🌧️',
  61: '🌧️', 63: '🌧️', 65: '🌧️',
  80: '🌦️', 81: '🌦️', 82: '⛈️',
  95: '⛈️', 96: '⛈️', 99: '⛈️',
}

const wmoEmoji = (c) => WMO_EMOJI[c] || WMO_EMOJI[Math.floor(c/10)*10] || '🌡️'

const wmoDesc = (c) => {
  if (c === 0) return 'Céu limpo'
  if (c <= 2) return 'Parcial. nublado'
  if (c === 3) return 'Nublado'
  if (c <= 48) return 'Neblina'
  if (c <= 55) return 'Garoa'
  if (c <= 65) return 'Chuva'
  if (c <= 82) return 'Pancadas'
  return 'Tempestade'
}

export default function SecaoClima({ clima, nota }) {
  if (!clima || clima.length === 0) return null
  return (
    <div style={{border:'1px solid #E0E0DC',borderRadius:6,padding:'8px 10px',flex:1}}>
      <div style={{display:'flex',alignItems:'center',marginBottom:6}}>
        <div style={{fontSize:8,fontWeight:600,color:'#063057',letterSpacing:'0.06em',textTransform:'uppercase',borderLeft:'3px solid #063057',paddingLeft:5}}>
          Condições Climáticas
        </div>
        <span style={{marginLeft:'auto',fontSize:7,color:'#999'}}>Open-Meteo · Mauá, SP</span>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',gap:4}}>
        {clima.map(dia => (
          <div key={dia.data} style={{background:'#F5F5F2',borderRadius:4,padding:'4px 3px',textAlign:'center'}}>
            <div style={{fontSize:7,color:'#999',fontWeight:600}}>{dia.dia_semana}</div>
            <div style={{fontSize:7,color:'#555',marginBottom:2}}>{dia.data_fmt}</div>
            <div style={{fontSize:13,lineHeight:1}}>{wmoEmoji(dia.weathercode)}</div>
            <div style={{fontSize:7,color:'#555',margin:'2px 0'}}>{wmoDesc(dia.weathercode)}</div>
            <div style={{fontSize:8,color:'#A32D2D',fontWeight:600}}>{dia.temp_max}°</div>
            <div style={{fontSize:7,color:'#185FA5'}}>{dia.temp_min}°</div>
          </div>
        ))}
      </div>
      {nota && <p style={{fontSize:8,color:'#555',marginTop:5,marginBottom:0,fontStyle:'italic'}}>{nota}</p>}
    </div>
  )
}
