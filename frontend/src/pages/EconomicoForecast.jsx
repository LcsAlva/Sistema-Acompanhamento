import { useEffect, useMemo, useState } from 'react'
import {
  BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { AlertTriangle, TrendingUp } from 'lucide-react'
import { getEconomicoForecast } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend)

const fmtBRL = (v) => (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) => `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtMes = (iso) => { const [a, m] = iso.split('-'); return `${m}/${a.slice(2)}` }

export default function EconomicoForecast() {
  const [data, setData] = useState(null)
  const [modo, setModo] = useState('acumulada')
  const [erro, setErro] = useState(null)

  useEffect(() => {
    getEconomicoForecast().then(setData).catch(e => setErro(e.response?.data?.detail || e.message))
  }, [])

  const serie = useMemo(() => (modo === 'mensal'  data?.curva_mensal : data?.curva_acumulada) || [], [data, modo])
  const chartData = {
    labels: serie.map(r => fmtMes(r.periodo)),
    datasets: [
      { label: 'Linha Base', data: serie.map(r => r.linha_base), borderColor: '#0F172A', backgroundColor: '#0F172A', tension: 0.25 },
      { label: 'Forecast', data: serie.map(r => r.forecast), borderColor: '#2563EB', backgroundColor: '#2563EB', tension: 0.25 },
    ],
  }

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando forecast...</div></div>

  const k = data.kpis
  const c = data.componentes

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestão Econômica</span>
          <h2>Forecast</h2>
          <p>Evolução projetada do resultado e explicação dos impactos financeiros.</p>
        </div>
      </section>

      <section className="forecast-executive">
        <article><span>Linha Base</span><strong>{fmtBRL(k.resultado_linha_base)}</strong></article>
        <article><span>Forecast</span><strong>{fmtBRL(k.resultado_forecast)}</strong></article>
        <article className={k.impacto_financeiro < 0  'loss' : 'gain'}><span>Impacto</span><strong>{fmtBRL(k.impacto_financeiro)}</strong><small>{fmtPct(k.impacto_percentual)}</small></article>
      </section>

      <section className="analysis-kpi-grid four">
        <Kpi label="Resultado Linha Base" value={k.resultado_linha_base} />
        <Kpi label="Resultado Forecast" value={k.resultado_forecast} />
        <Kpi label="Impacto Financeiro" value={k.impacto_financeiro} tone={k.impacto_financeiro < 0  'danger' : 'success'} />
        <Kpi label="Impacto %" value={k.impacto_percentual} format="pct" tone={k.impacto_financeiro < 0  'danger' : 'success'} />
      </section>

      <section className="econ-chart-card">
        <div className="econ-chart-head split">
          <div className="inline-title"><TrendingUp size={18} /><div><strong>Evolução do Forecast</strong><span>Linha Base x Forecast</span></div></div>
          <div className="segmented"><button className={modo === 'mensal'  'active' : ''} onClick={() => setModo('mensal')}>Mensal</button><button className={modo === 'acumulada'  'active' : ''} onClick={() => setModo('acumulada')}>Acumulado</button></div>
        </div>
        <div className="econ-chart"><Line data={chartData} options={chartOptions()} /></div>
      </section>

      <section className="analysis-grid">
        <section className="econ-table-card">
          <div className="econ-chart-head"><TrendingUp size={18} /><div><strong>Composição do Forecast</strong><span>Componentes consolidados</span></div></div>
          <div className="forecast-components">
            <article><span>Receita Forecast</span><strong>{fmtBRL(c.receita_forecast)}</strong></article>
            <article><span>Custos Diretos Forecast</span><strong>{fmtBRL(c.custos_diretos_forecast)}</strong></article>
            <article><span>Custos Indiretos Forecast</span><strong>{fmtBRL(c.custos_indiretos_forecast)}</strong></article>
            <article><span>Impostos Forecast</span><strong>{fmtBRL(c.impostos_forecast)}</strong></article>
            <article><span>Resultado Forecast</span><strong>{fmtBRL(c.resultado_forecast)}</strong></article>
          </div>
        </section>
        <section className="econ-table-card">
          <div className="econ-chart-head"><AlertTriangle size={18} /><div><strong>Explicação do Forecast</strong><span>Impactos que explicam a diferença</span></div></div>
          <div className="econ-table-wrap">
            <table className="econ-table">
              <thead><tr><th>Categoria</th><th>Impacto Financeiro</th><th>Participação %</th></tr></thead>
              <tbody>{data.explicacao.map(row => <tr key={row.categoria}><td><strong>{row.categoria}</strong></td><td className={row.impacto_financeiro < 0  'danger' : 'success'}>{fmtBRL(row.impacto_financeiro)}</td><td>{fmtPct(row.impacto_percentual)}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      </section>
    </div>
  )
}

function Kpi({ label, value, format, tone }) {
  return <section className="analysis-kpi"><span>{label}</span><strong className={tone || ''}>{format === 'pct'  fmtPct(value) : fmtBRL(value)}</strong></section>
}

function chartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}` } } },
    scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => fmtBRL(v).replace('R$', 'R$ ') } } },
  }
}
