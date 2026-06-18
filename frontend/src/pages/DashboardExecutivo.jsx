import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  Factory,
  FileText,
  Landmark,
  Receipt,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSemana } from '../context/SemanaContext'
import { useIndicadores, usePainel } from '../hooks/useApi'
import {
  bmGetTodasPendencias,
  getMedicaoEngDashboard,
  getProgresso211,
  getSigemDivergentes,
} from '../api'
import { execPct } from '../utils/formatters'

const fmtPct = (v) => Number.isFinite(v)  `${v.toFixed(1).replace('.', ',')}%` : '-'

export default function DashboardExecutivo() {
  const { semanaAtual, semanas } = useSemana()
  const [engenharia, setEngenharia] = useState(null)
  const [bm, setBm] = useState(null)
  const [sigem, setSigem] = useState(null)
  const [pendencias, setPendencias] = useState(null)

  const semanaAtualIdx = semanas.findIndex(s => s.codigo === semanaAtual?.codigo)
  const semanaAnterior = semanaAtualIdx > 0  semanas[semanaAtualIdx - 1] : null
  const { data: indicadores } = useIndicadores(semanaAtual?.codigo)
  const { data: indicadoresAnt } = useIndicadores(semanaAnterior?.codigo)
  const { data: painel } = usePainel(semanaAtual?.codigo)

  useEffect(() => {
    let mounted = true
    Promise.allSettled([
      getProgresso211(),
      getMedicaoEngDashboard(),
      getSigemDivergentes(),
      bmGetTodasPendencias(),
    ]).then(results => {
      if (!mounted) return
      const [docsRes, bmRes, sigemRes, pendRes] = results
      if (docsRes.status === 'fulfilled') setEngenharia(docsRes.value)
      if (bmRes.status === 'fulfilled') setBm(bmRes.value)
      if (sigemRes.status === 'fulfilled') setSigem(sigemRes.value)
      if (pendRes.status === 'fulfilled') setPendencias(pendRes.value)
    })
    return () => { mounted = false }
  }, [])

  const programado = indicadores?.qcron > 0  (indicadores.qprog / indicadores.qcron) * 100 : null
  const realizado = indicadoresAnt  execPct(indicadoresAnt) : null
  const avancoFisico = painel?.pct_geral  painel?.percentual_geral  painel?.pct_avanco  null
  const docsAptos = engenharia?.aptos  engenharia?.documentos_aptos  bm?.documentos_aptos  null
  const docsPendentes = engenharia?.pendentes  engenharia?.documentos_pendentes  bm?.documentos_pendentes  null
  const divergencias = Array.isArray(sigem)  sigem.length : sigem?.total  sigem?.divergentes  null
  const pendCriticas = Array.isArray(pendencias)  pendencias.length : pendencias?.total  null

  return (
    <div className="executive-page">
      <section className="executive-hero">
        <div>
          <span className="eyebrow">Dashboard Executivo</span>
          <h2>{'Vis\u00e3o consolidada da obra'}</h2>
          <p>{'Indicadores de planejamento, engenharia, produ\u00e7\u00e3o, medi\u00e7\u00e3o e gest\u00e3o econ\u00f4mica no mesmo ponto de partida.'}</p>
        </div>
        <Link to="/dashboard" className="btn-primary">{'Abrir Programa\u00e7\u00e3o Semanal'}</Link>
      </section>

      <section className="executive-grid">
        <ExecutiveCard
          icon={CalendarRange}
          title="Planejamento"
          to="/dashboard"
          metrics={[
            ['Programado', fmtPct(programado)],
            ['Realizado', realizado != null  `${realizado}%` : '-'],
          ]}
        />
        <ExecutiveCard
          icon={FileText}
          title="Engenharia"
          to="/integracao-ld"
          metrics={[
            ['Documentos Aptos', docsAptos  '-'],
            ['Documentos Pendentes', docsPendentes  '-'],
          ]}
        />
        <ExecutiveCard
          icon={Factory}
          title={'Produ\u00e7\u00e3o'}
          to="/painel"
          metrics={[
            ['Avan\u00e7o F\u00edsico', fmtPct(avancoFisico)],
            ['Semana Atual', semanaAtual?.codigo || '-'],
          ]}
        />
        <ExecutiveCard
          icon={Receipt}
          title={'Medi\u00e7\u00e3o'}
          to="/medicao"
          metrics={[
            ['BM Atual', bm?.bm_atual || bm?.ciclo_atual || '-'],
            ['BM Acumulada', fmtPct(bm?.pct_acumulado  bm?.acumulado_pct)],
          ]}
        />
        <ExecutiveCard
          icon={Landmark}
          title={'Gest\u00e3o Econ\u00f4mica'}
          to="/gestao-economica"
          metrics={[
            ['Or\u00e7ado', '-'],
            ['Realizado', '-'],
          ]}
        />
        <div className="executive-alerts">
          <div className="executive-alerts-title">
            <AlertTriangle size={18} />
            <span>Alertas</span>
          </div>
          <AlertRow label={'Diverg\u00eancias SIGEM'} value={divergencias  '-'} />
          <AlertRow label={'Pend\u00eancias cr\u00edticas'} value={pendCriticas  '-'} />
        </div>
      </section>
    </div>
  )
}

function ExecutiveCard({ icon: Icon, title, metrics, to }) {
  return (
    <Link to={to} className="executive-card">
      <div className="executive-card-head">
        <span className="executive-icon"><Icon size={20} /></span>
        <strong>{title}</strong>
      </div>
      <div className="executive-metrics">
        {metrics.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </Link>
  )
}

function AlertRow({ label, value }) {
  const ok = value === 0
  return (
    <div className="executive-alert-row">
      <div>
        {ok  <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
    </div>
  )
}
