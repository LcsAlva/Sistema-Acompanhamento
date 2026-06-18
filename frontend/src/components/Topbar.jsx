import { Link } from 'react-router-dom'
import { useSemana } from '../context/SemanaContext'

export default function Topbar() {
  const { semanaAtual } = useSemana()
  const codigo = semanaAtual?.codigo || 'Sem semana'
  const periodo = semanaAtual
     `${fmtDate(semanaAtual.data_inicio)} a ${fmtDate(semanaAtual.data_fim)}`
    : 'Semana n\u00e3o selecionada'

  return (
    <div className="app-header">
      <div>
        <div className="app-header-kicker">ETM Suite</div>
        <Link to="/" style={{ textDecoration: 'none' }}>
          <h1>{'Planejamento e Medi\u00e7\u00e3o'}</h1>
        </Link>
        <p>RECAP EPC - Revamp Caldeira CO</p>
      </div>
      <div className="app-header-meta">
        <span>{codigo}</span>
        <strong>{periodo}</strong>
      </div>
    </div>
  )
}

function fmtDate(d) {
  if (!d) return ''
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}
