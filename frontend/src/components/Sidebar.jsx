import { Link, useLocation } from 'react-router-dom'
import { useSemana } from '../context/SemanaContext'
import { buildNavigation, pathMatches } from '../navigation'

export default function Sidebar() {
  const { semanaAtual } = useSemana()
  const location = useLocation()
  const codigo = semanaAtual?.codigo || ''
  const hoje = new Date()
  const modules = buildNavigation({
    codigo,
    ano: hoje.getFullYear(),
    mes: hoje.getMonth() + 1,
  })

  return (
    <aside className="app-sidebar">
      <Link to="/" className="app-brand" aria-label="ETM Suite">
        <div className="app-brand-mark">ETM</div>
        <div>
          <div className="app-brand-title">ETM Suite</div>
          <div className="app-brand-subtitle">{'Planejamento e Medi\u00e7\u00e3o'}</div>
        </div>
      </Link>

      <nav className="app-sidebar-nav" aria-label="Modulos principais">
        {modules.map(module => {
          const Icon = module.icon
          const active = pathMatches(module.match, location.pathname)
          const className = `app-sidebar-link${active ? ' is-active' : ''}`
          if (module.id === 'suportes') {
            return (
              <a key={module.id} href={module.to} className={className}>
                <Icon size={18} strokeWidth={1.9} />
                <span>{module.label}</span>
              </a>
            )
          }
          return (
            <Link
              key={module.id}
              to={module.to}
              className={className}
            >
              <Icon size={18} strokeWidth={1.9} />
              <span>{module.label}</span>
            </Link>
          )
        })}
      </nav>

      <div className="app-sidebar-footer">
        <span>RECAP EPC</span>
        <strong>Revamp Caldeira CO</strong>
      </div>
    </aside>
  )
}
