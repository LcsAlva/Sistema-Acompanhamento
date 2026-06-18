import { useEffect, useMemo, useState } from 'react'
import {
  CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { ArrowDownRight, ArrowUpRight, CircleDollarSign } from 'lucide-react'
import { getEconomicoReceitas } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

const fmtBRL = (v) => (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) => `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtMes = (iso) => { const [a, m] = iso.split('-'); return `${m}/${a.slice(2)}` }

export default function EconomicoReceitas() {
  const [data, setData] = useState(null)
  const [modo, setModo] = useState('acumulada')
  const [erro, setErro] = useState(null)

  useEffect(() => {
    getEconomicoReceitas().then(setData).catch(e => setErro(e.response?.data?.detail || e.message))
  }, [])

  const serie = useMemo(() => (modo === 'mensal'  data?.curva_mensal : data?.curva_acumulada) || [], [data, modo])
  const chartData = {
    labels: serie.map(r => fmtMes(r.periodo)),
    datasets: [
      { label: 'Linha Base', data: serie.map(r => r.linha_base), borderColor: '#0F172A', backgroundColor: '#0F172A', tension: 0.25 },
      { label: 'Tendência', data: serie.map(r => r.tendencia), borderColor: '#2563EB', backgroundColor: '#2563EB', tension: 0.25 },
      { label: 'Realizada', data: serie.map(r => r.realizada), borderColor: '#16A34A', backgroundColor: '#16A34A', tension: 0.25 },
    ],
  }

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando receitas...</div></div>

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestão Econômica</span>
          <h2>Receitas</h2>
          <p>Visão gerencial da receita por curva, fase e impactos.</p>
        </div>
      </section>

      <section className="analysis-kpi-grid four">
        <Kpi label="Receita Linha Base" value={data.kpis.linha_base} />
        <Kpi label="Receita Tendência" value={data.kpis.tendencia} />
        <Kpi label="Receita Realizada" value={data.kpis.realizada} />
        <Kpi label="Receita a Reconhecer" value={data.kpis.a_reconhecer} />
      </section>

      <section className="econ-chart-card">
        <div className="econ-chart-head split">
          <div className="inline-title"><CircleDollarSign size={18} /><div><strong>Curva de Receita</strong><span>{modo === 'mensal'  'Mensal' : 'Acumulada'}</span></div></div>
          <div className="segmented"><button className={modo === 'mensal'  'active' : ''} onClick={() => setModo('mensal')}>Mensal</button><button className={modo === 'acumulada'  'active' : ''} onClick={() => setModo('acumulada')}>Acumulada</button></div>
        </div>
        <div className="econ-chart"><Line data={chartData} options={chartOptions()} /></div>
      </section>

      <section className="analysis-grid">
        <TableCard title="Receita por Fase" rows={data.fases} columns={[
          ['fase', 'Fase'], ['linha_base', 'Linha Base', 'money'], ['tendencia', 'Tendência', 'money'], ['real', 'Realizada', 'money'], ['participacao_percentual', 'Participação %', 'pct'],
        ]} />
        <TableCard title="Principais Impactos na Receita" rows={data.impactos} columns={[
          ['fase', 'Fase'], ['linha_base', 'Linha Base', 'money'], ['tendencia', 'Tendência', 'money'], ['desvio', 'Desvio', 'money-tone'],
        ]} icon />
      </section>

      <TableCard title="Receita Acumulada" rows={data.curva_acumulada} columns={[
        ['periodo', 'Mês', 'month'], ['linha_base', 'Linha Base', 'money'], ['tendencia', 'Tendência', 'money'], ['realizada', 'Realizada', 'money'], ['desvio', 'Desvio', 'money-tone'],
      ]} />
    </div>
  )
}

function Kpi({ label, value }) {
  return <section className="analysis-kpi"><span>{label}</span><strong>{fmtBRL(value)}</strong></section>
}

function TableCard({ title, rows, columns, icon }) {
  return (
    <section className="econ-table-card">
      <div className="econ-chart-head">{icon  <ArrowUpRight size={18} /> : <CircleDollarSign size={18} />}<div><strong>{title}</strong><span>Dados conciliados pela auditoria</span></div></div>
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
  if (type === 'month') return fmtMes(value)
  return <strong>{value}</strong>
}

function chartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}` } } },
    scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => fmtBRL(v).replace('R$', 'R$ ') } } },
  }
}
