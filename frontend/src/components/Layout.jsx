import { Link, Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useSemana } from '../context/SemanaContext'
import { buildNavigation, getActiveModule, pathMatches } from '../navigation'

export default function Layout() {
  const { semanaAtual } = useSemana()
  const location = useLocation()
  const codigo = semanaAtual?.codigo || ''
  const hoje = new Date()
  const modules = buildNavigation({
    codigo,
    ano: hoje.getFullYear(),
    mes: hoje.getMonth() + 1,
  })
  const activeModule = getActiveModule(modules, location.pathname)
  const periodo = semanaAtual
     `${fmtDate(semanaAtual.data_inicio)} a ${fmtDate(semanaAtual.data_fim)}`
    : 'Semana n\u00e3o selecionada'

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <header className="app-header">
          <div>
            <div className="app-header-kicker">ETM Suite</div>
            <h1>{activeModule.label}</h1>
            <p>RECAP EPC - Revamp Caldeira CO</p>
          </div>
          <div className="app-header-meta">
            <span>{codigo || 'Sem semana'}</span>
            <strong>{periodo}</strong>
          </div>
        </header>

        {activeModule.tabs.length > 0 && (
          <nav className="module-tabs" aria-label={`Navegacao de ${activeModule.label}`}>
            {activeModule.tabs.map(tab => {
              if (tab.disabled) {
                return (
                  <span key={tab.label} className="module-tab is-disabled">
                    {tab.label}
                  </span>
                )
              }
              const active = pathMatches(tab.match, location.pathname)
              return (
                <Link
                  key={tab.label}
                  to={tab.to}
                  className={`module-tab${active  ' is-active' : ''}`}
                >
                  {tab.label}
                </Link>
              )
            })}
          </nav>
        )}

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function fmtDate(d) {
  if (!d) return ''
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}
