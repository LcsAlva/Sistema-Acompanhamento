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
import { AlertTriangle, ChartNoAxesColumnIncreasing, CircleDollarSign, Percent, TrendingUp } from 'lucide-react'
import { getEconomicoResultado } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend)

const fmtBRL = (v) => (v ?? 0).toLocaleString('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  maximumFractionDigits: 0,
})
const fmtPct = (v) => `${((v ?? 0) * 100).toLocaleString('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})}%`
const fmtMes = (iso) => {
  const [ano, mes] = iso.split('-')
  return `${mes}/${ano.slice(2)}`
}

export default function EconomicoResultado() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    getEconomicoResultado().then(setData).catch(e => setErro(e.response?.data?.detail || e.message))
  }, [])

  const resultadoSerie = useMemo(() => data?.evolucao_resultado || [], [data])
  const margemSerie = useMemo(() => data?.evolucao_margem || [], [data])
  const formacao = data?.formacao_resultado || {}

  const resultadoChart = {
    labels: resultadoSerie.map(r => fmtMes(r.periodo)),
    datasets: [
      { label: 'Linha Base', data: resultadoSerie.map(r => r.linha_base), borderColor: '#0F172A', backgroundColor: '#0F172A', tension: 0.25 },
      { label: 'Forecast', data: resultadoSerie.map(r => r.forecast), borderColor: '#2563EB', backgroundColor: '#2563EB', tension: 0.25 },
      { label: 'Realizado', data: resultadoSerie.map(r => r.realizado), borderColor: '#16A34A', backgroundColor: '#16A34A', tension: 0.25 },
    ],
  }

  const margemChart = {
    labels: margemSerie.map(r => fmtMes(r.periodo)),
    datasets: [
      { label: 'Linha Base', data: margemSerie.map(r => r.linha_base), borderColor: '#0F172A', backgroundColor: '#0F172A', tension: 0.25 },
      { label: 'Forecast', data: margemSerie.map(r => r.forecast), borderColor: '#2563EB', backgroundColor: '#2563EB', tension: 0.25 },
      { label: 'Realizado', data: margemSerie.map(r => r.realizado), borderColor: '#16A34A', backgroundColor: '#16A34A', tension: 0.25 },
    ],
  }

  const formacaoChart = {
    labels: ['Receita', 'Impostos', 'Custos Diretos', 'Custos Indiretos', 'Resultado'],
    datasets: [{
      label: 'Forecast',
      data: [
        formacao.receita || 0,
        formacao.impostos || 0,
        formacao.custos_diretos || 0,
        formacao.custos_indiretos || 0,
        formacao.resultado || 0,
      ],
      backgroundColor: ['#2563EB', '#F59E0B', '#DC2626', '#EA580C', '#16A34A'],
      borderRadius: 5,
    }],
  }

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando resultado...</div></div>

  if (!data.disponivel) {
    return (
      <div className="econ-page">
        <div className="placeholder-panel">
          <div>
            <span className="eyebrow">Gestao Economica</span>
            <h2>Resultado ainda sem dados calculados</h2>
            <p>Execute a importacao e auditoria da planilha para liberar a analise de resultado.</p>
          </div>
        </div>
      </div>
    )
  }

  const k = data.kpis

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestao Economica - Fase 1F</span>
          <h2>Resultado</h2>
          <p>Analise consolidada do resultado, margem e impactos financeiros da obra.</p>
        </div>
        <div className="econ-source">
          <small>Importacao auditada</small>
          <strong>{data.importacao?.arquivo_original}</strong>
          <span>{data.importacao?.observacao}</span>
        </div>
      </section>

      <section className="analysis-kpi-grid four">
        <Kpi label="Resultado Linha Base" value={k.resultado_linha_base} icon={<CircleDollarSign size={18} />} />
        <Kpi label="Resultado Forecast" value={k.resultado_forecast} icon={<TrendingUp size={18} />} />
        <Kpi label="Resultado Atual" value={k.resultado_atual} tone={k.resultado_atual < 0 ? 'danger' : 'success'} icon={<ChartNoAxesColumnIncreasing size={18} />} />
        <Kpi label="Margem Atual" value={k.margem_atual} format="pct" tone={k.margem_atual < 0 ? 'danger' : 'success'} icon={<Percent size={18} />} />
      </section>

      <section className="econ-chart-card">
        <div className="econ-chart-head">
          <TrendingUp size={18} />
          <div>
            <strong>Evolucao do Resultado</strong>
            <span>Linha Base auditada como referencia; Forecast e Realizado acumulados</span>
          </div>
        </div>
        <div className="econ-chart"><Line data={resultadoChart} options={moneyChartOptions()} /></div>
      </section>

      <section className="analysis-grid">
        <section className="econ-chart-card">
          <div className="econ-chart-head">
            <ChartNoAxesColumnIncreasing size={18} />
            <div>
              <strong>Formacao do Resultado</strong>
              <span>Componentes consolidados do forecast</span>
            </div>
          </div>
          <div className="econ-chart"><Bar data={formacaoChart} options={moneyChartOptions()} /></div>
        </section>

        <section className="econ-chart-card">
          <div className="econ-chart-head">
            <Percent size={18} />
            <div>
              <strong>Evolucao da Margem</strong>
              <span>Linha Base auditada como referencia; Forecast e Realizado acumulados</span>
            </div>
          </div>
          <div className="econ-chart"><Line data={margemChart} options={percentChartOptions()} /></div>
        </section>
      </section>

      <section className="econ-table-card">
        <div className="econ-chart-head">
          <AlertTriangle size={18} />
          <div>
            <strong>Impacto no Resultado</strong>
            <span>Categorias que explicam a variacao do resultado</span>
          </div>
        </div>
        <div className="econ-table-wrap">
          <table className="econ-table">
            <thead>
              <tr>
                <th>Categoria</th>
                <th>Impacto Financeiro</th>
                <th>Participacao %</th>
              </tr>
            </thead>
            <tbody>
              {data.impactos.map(row => (
                <tr key={row.categoria}>
                  <td><strong>{row.categoria}</strong></td>
                  <td className={row.impacto_financeiro < 0 ? 'danger' : 'success'}>{fmtBRL(row.impacto_financeiro)}</td>
                  <td>{fmtPct(row.impacto_percentual)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Kpi({ label, value, format, tone, icon }) {
  return (
    <section className="analysis-kpi">
      <span className="inline-title">{icon}{label}</span>
      <strong className={tone || ''}>{format === 'pct'  fmtPct(value) : fmtBRL(value)}</strong>
    </section>
  )
}

function moneyChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom' },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}` } },
    },
    scales: {
      x: { grid: { display: false } },
      y: { ticks: { callback: v => fmtBRL(v).replace('R$', 'R$ ') } },
    },
  }
}

function percentChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom' },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtPct(ctx.parsed.y)}` } },
    },
    scales: {
      x: { grid: { display: false } },
      y: { ticks: { callback: v => fmtPct(v) } },
    },
  }
}
