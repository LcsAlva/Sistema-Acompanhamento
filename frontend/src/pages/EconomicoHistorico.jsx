import { useEffect, useState } from 'react'
import {
  CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { AlertTriangle, History } from 'lucide-react'
import { getEconomicoHistorico } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

const fmtBRL = (v) => (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) => `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtDate = (v) => v  new Date(v).toLocaleString('pt-BR') : '-'

export default function EconomicoHistorico() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    getEconomicoHistorico().then(setData).catch(e => setErro(e.response?.data?.detail || e.message))
  }, [])

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando histórico econômico...</div></div>

  const chartData = {
    labels: data.tendencia_historica.map(r => `#${r.importacao}`),
    datasets: [{ label: 'Resultado Forecast', data: data.tendencia_historica.map(r => r.resultado_forecast), borderColor: '#2563EB', backgroundColor: '#2563EB', tension: 0.25 }],
  }

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestão Econômica</span>
          <h2>Histórico Econômico</h2>
          <p>Evolução da obra ao longo das importações persistidas.</p>
        </div>
      </section>

      {data.validacao.importacoes_incompletas > 0 && (
        <div className="audit-error">
          {data.validacao.importacoes_incompletas} importações necessitam reprocessamento para participação completa no histórico.
        </div>
      )}

      <section className="analysis-kpi-grid three">
        <Kpi label="Importações" value={data.validacao.total_importacoes} />
        <Kpi label="Completas" value={data.validacao.importacoes_completas} />
        <Kpi label="Incompletas" value={data.validacao.importacoes_incompletas} tone={data.validacao.importacoes_incompletas  'danger' : 'success'} />
      </section>

      <section className="econ-chart-card">
        <div className="econ-chart-head"><History size={18} /><div><strong>Tendência Histórica</strong><span>Forecast por importação</span></div></div>
        <div className="econ-chart"><Line data={chartData} options={chartOptions()} /></div>
      </section>

      <Table title="Importações" rows={data.importacoes} columns={[
        ['id', 'ID'], ['data_hora', 'Data/Hora', 'date'], ['usuario', 'Usuário'], ['arquivo', 'Arquivo'], ['status', 'Status'], ['necessita_reprocessamento', 'Reprocessar', 'bool'],
      ]} />

      <Table title="Evolução dos Indicadores" rows={data.evolucao_indicadores} columns={[
        ['id', 'Importação'], ['receita_forecast', 'Receita Forecast', 'money'], ['custos_forecast', 'Custos Forecast', 'money'], ['resultado_forecast', 'Resultado Forecast', 'money-tone'], ['margem_forecast', 'Margem Forecast', 'pct'],
      ]} />

      <Table title="Auditoria Histórica" rows={data.auditoria_historica} columns={[
        ['importacao', 'Importação'], ['receita', 'Receita', 'money'], ['custos', 'Custos', 'money'], ['resultado', 'Resultado', 'money-tone'], ['margem', 'Margem', 'pct'], ['status_auditoria', 'Status Auditoria'], ['maior_diferenca', 'Maior Diferença', 'money'],
      ]} />
    </div>
  )
}

function Kpi({ label, value, tone }) {
  return <section className="analysis-kpi"><span>{label}</span><strong className={tone || ''}>{value}</strong></section>
}

function Table({ title, rows, columns }) {
  return (
    <section className="econ-table-card">
      <div className="econ-chart-head"><History size={18} /><div><strong>{title}</strong><span>Dados persistidos por importação</span></div></div>
      <div className="econ-table-wrap">
        <table className="econ-table">
          <thead><tr>{columns.map(c => <th key={c[0]}>{c[1]}</th>)}</tr></thead>
          <tbody>{rows.map((row, idx) => <tr key={idx}>{columns.map(([key, , type]) => <td key={key} className={type === 'money-tone'  (row[key] < 0  'danger' : 'success') : ''}>{format(row[key], type)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </section>
  )
}

function format(value, type) {
  if (type === 'money' || type === 'money-tone') return fmtBRL(value)
  if (type === 'pct') return fmtPct(value)
  if (type === 'date') return fmtDate(value)
  if (type === 'bool') return value  <span className="risk-chip"><AlertTriangle size={12} />Sim</span> : 'Não'
  return <strong>{value  '-'}</strong>
}

function chartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}` } } },
    scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => fmtBRL(v).replace('R$', 'R$ ') } } },
  }
}
