import { useEffect, useMemo, useState } from 'react'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CircleDollarSign, TrendingUp } from 'lucide-react'
import { getEconomicoDashboard } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend)

const fmtBRL = (v) =>
  (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) =>
  `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtMes = (iso) => {
  const [ano, mes] = iso.split('-')
  return `${mes}/${ano.slice(2)}`
}

function KpiGroup({ title, items }) {
  return (
    <section className="econ-kpi-card">
      <span>{title}</span>
      <div>
        {items.map(item => (
          <article key={item.label}>
            <small>{item.label}</small>
            <strong className={item.tone || ''}>
              {item.format === 'pct'  fmtPct(item.value) : fmtBRL(item.abs  Math.abs(item.value) : item.value)}
            </strong>
          </article>
        ))}
      </div>
    </section>
  )
}

export default function EconomicoDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    getEconomicoDashboard()
      .then(setData)
      .catch(e => setErro(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [])

  const curva = useMemo(() => data?.curva_receita_custos || [], [data])
  const labels = useMemo(() => curva.map(p => fmtMes(p.periodo)), [curva])
  const impacto = data?.impacto_financeiro || {}
  const perda = (impacto.valor || 0) < 0

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 } },
      y: { ticks: { callback: value => fmtBRL(value).replace('R$', 'R$ ') } },
    },
  }

  const receitaCustosData = {
    labels,
    datasets: [
      {
        label: 'Receita prevista',
        data: curva.map(p => p.receita_prevista),
        borderColor: '#2563EB',
        backgroundColor: '#2563EB',
        tension: 0.25,
      },
      {
        label: 'Receita realizada',
        data: curva.map(p => p.receita_realizada),
        borderColor: '#16A34A',
        backgroundColor: '#16A34A',
        tension: 0.25,
      },
      {
        label: 'Custos previstos',
        data: curva.map(p => p.custos_previstos),
        borderColor: '#EA580C',
        backgroundColor: '#EA580C',
        tension: 0.25,
      },
      {
        label: 'Custos realizados',
        data: curva.map(p => p.custos_realizados),
        borderColor: '#DC2626',
        backgroundColor: '#DC2626',
        tension: 0.25,
      },
    ],
  }

  const resultadoData = {
    labels,
    datasets: [
      {
        label: 'Resultado previsto',
        data: curva.map(p => p.resultado_previsto),
        backgroundColor: '#93C5FD',
        borderRadius: 4,
      },
      {
        label: 'Resultado realizado',
        data: curva.map(p => p.resultado_realizado),
        backgroundColor: '#0F172A',
        borderRadius: 4,
      },
    ],
  }

  if (loading) return <div className="econ-page"><div className="card">Carregando dashboard economico...</div></div>

  if (erro) {
    return (
      <div className="econ-page">
        <div className="audit-error">{erro}</div>
      </div>
    )
  }

  if (!data?.disponivel) {
    return (
      <div className="econ-page">
        <div className="placeholder-panel">
          <div>
            <span className="eyebrow">Gestao Economica</span>
            <h2>Dashboard ainda sem dados calculados</h2>
            <p>Execute a importacao e auditoria da planilha para liberar a visao executiva.</p>
          </div>
        </div>
      </div>
    )
  }

  const { kpis } = data

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestao Economica - Fase 1B</span>
          <h2>Dashboard Executivo</h2>
          <p>Visao consolidada calculada a partir das tabelas validadas na auditoria.</p>
        </div>
        <div className="econ-source">
          <small>Importacao</small>
          <strong>{data.importacao?.arquivo_original}</strong>
          <span>{data.importacao?.observacao}</span>
        </div>
      </section>

      <section className="econ-kpi-grid">
        <KpiGroup title="Receita" items={[
          { label: 'Linha Base', value: kpis.receita.linha_base },
          { label: 'Realizada', value: kpis.receita.realizada },
          { label: 'Tendencia', value: kpis.receita.tendencia },
        ]} />
        <KpiGroup title="Custos" items={[
          { label: 'Diretos', value: kpis.custos.diretos, abs: true },
          { label: 'Indiretos', value: kpis.custos.indiretos, abs: true },
          { label: 'Impostos', value: kpis.custos.impostos, abs: true },
        ]} />
        <KpiGroup title="Resultado" items={[
          { label: 'Linha Base', value: kpis.resultado.linha_base },
          { label: 'Forecast', value: kpis.resultado.forecast },
          { label: 'Atual', value: kpis.resultado.atual, tone: kpis.resultado.atual < 0  'danger' : 'success' },
        ]} />
        <KpiGroup title="Margem" items={[
          { label: 'Prevista', value: kpis.margem.prevista, format: 'pct' },
          { label: 'Forecast', value: kpis.margem.forecast, format: 'pct' },
          { label: 'Atual', value: kpis.margem.atual, format: 'pct', tone: kpis.margem.atual < 0  'danger' : 'success' },
        ]} />
      </section>

      <section className={`econ-impact ${perda  'is-loss' : 'is-gain'}`}>
        <div className="econ-impact-icon">
          {perda  <ArrowDownRight size={22} /> : <ArrowUpRight size={22} />}
        </div>
        <div>
          <span>Impacto financeiro</span>
          <h3>{perda  'Perda projetada' : 'Ganho projetado'} de {fmtBRL(Math.abs(impacto.valor))}</h3>
          <p>
            Resultado Linha Base {fmtBRL(impacto.resultado_linha_base)} vs Forecast {fmtBRL(impacto.resultado_forecast)}
            {' '}({fmtPct(impacto.percentual)}).
          </p>
        </div>
        <div className="econ-impact-badge">
          {perda  <AlertTriangle size={16} /> : <TrendingUp size={16} />}
          {fmtPct(impacto.percentual)}
        </div>
      </section>

      <section className="econ-chart-grid">
        <div className="econ-chart-card">
          <div className="econ-chart-head">
            <CircleDollarSign size={18} />
            <div>
              <strong>Receita x Custos por mes</strong>
              <span>Previsto e realizado</span>
            </div>
          </div>
          <div className="econ-chart">
            <Line data={receitaCustosData} options={chartOptions} />
          </div>
        </div>

        <div className="econ-chart-card">
          <div className="econ-chart-head">
            <TrendingUp size={18} />
            <div>
              <strong>Resultado por mes</strong>
              <span>Previsto e realizado</span>
            </div>
          </div>
          <div className="econ-chart">
            <Bar data={resultadoData} options={chartOptions} />
          </div>
        </div>
      </section>
    </div>
  )
}
