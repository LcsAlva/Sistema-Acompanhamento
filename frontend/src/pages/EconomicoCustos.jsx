import { useEffect, useMemo, useState } from 'react'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'
import { FileSearch, Filter, ReceiptText } from 'lucide-react'
import { getEconomicoCustos, getEconomicoLancamentos } from '../api'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)

const fmtBRL = (v) =>
  (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) =>
  `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtDate = (v) => v  new Date(`${v}T12:00:00`).toLocaleDateString('pt-BR') : '-'

function CostKpi({ title, data }) {
  return (
    <section className="econ-kpi-card cost-kpi">
      <span>{title}</span>
      <article><small>Linha Base</small><strong>{fmtBRL(Math.abs(data?.linha_base || 0))}</strong></article>
      <article><small>Forecast</small><strong>{fmtBRL(Math.abs(data?.forecast || 0))}</strong></article>
      <article><small>Realizado</small><strong>{fmtBRL(Math.abs(data?.realizado || 0))}</strong></article>
    </section>
  )
}

function DetailPanel({ categoria }) {
  const [data, setData] = useState(null)
  const [filters, setFilters] = useState({})

  useEffect(() => {
    if (!categoria) return
    getEconomicoLancamentos({ categoria, ...filters, limit: 200 }).then(setData)
  }, [categoria, filters])

  if (!categoria) {
    return (
      <section className="econ-detail-empty">
        <FileSearch size={20} />
        <span>Selecione uma categoria para investigar documentos, fornecedores, contas e valores.</span>
      </section>
    )
  }

  const filtros = data?.filtros || {}

  return (
    <section className="econ-detail">
      <div className="econ-detail-head">
        <div>
          <span className="eyebrow">Drill Down - RAZAO</span>
          <h3>{categoria}</h3>
          <p>Total filtrado: {fmtBRL(data?.total || 0)}</p>
        </div>
        <ReceiptText size={22} />
      </div>

      <div className="econ-filters">
        <label>
          <Filter size={14} />
          <select value={filters.fornecedor || ''} onChange={e => setFilters(f => ({ ...f, fornecedor: e.target.value || undefined }))}>
            <option value="">Todos os fornecedores</option>
            {(filtros.fornecedores || []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          <select value={filters.conta || ''} onChange={e => setFilters(f => ({ ...f, conta: e.target.value || undefined }))}>
            <option value="">Todas as contas</option>
            {(filtros.contas || []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          <input type="date" value={filters.periodo_inicio || ''} onChange={e => setFilters(f => ({ ...f, periodo_inicio: e.target.value || undefined }))} />
        </label>
        <label>
          <input type="date" value={filters.periodo_fim || ''} onChange={e => setFilters(f => ({ ...f, periodo_fim: e.target.value || undefined }))} />
        </label>
      </div>

      <div className="econ-table-wrap">
        <table className="econ-table">
          <thead>
            <tr>
              <th>Documento</th>
              <th>Fornecedor</th>
              <th>Data</th>
              <th>Conta</th>
              <th>Valor</th>
            </tr>
          </thead>
          <tbody>
            {(data?.lancamentos || []).map(row => (
              <tr key={row.id}>
                <td>
                  <strong>{row.documento || '-'}</strong>
                  <span>{row.historico || '-'}</span>
                </td>
                <td>{row.fornecedor || '-'}</td>
                <td>{fmtDate(row.data)}</td>
                <td>
                  <strong>{row.conta || '-'}</strong>
                  <span>{row.conta_descricao || '-'}</span>
                </td>
                <td>{fmtBRL(row.valor)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function EconomicoCustos() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    getEconomicoCustos()
      .then(result => {
        setData(result)
        setSelected(result?.top_custos?.[0]?.categoria || null)
      })
      .catch(e => setErro(e.response?.data?.detail || e.message))
  }, [])

  const distribuicao = useMemo(() => data?.distribuicao || [], [data])
  const chartData = {
    labels: distribuicao.slice(0, 10).map(r => r.categoria),
    datasets: [{
      label: 'Forecast',
      data: distribuicao.slice(0, 10).map(r => r.forecast),
      backgroundColor: '#2563EB',
      borderRadius: 4,
    }],
  }

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando custos...</div></div>

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestao Economica - Fase 1C</span>
          <h2>Custos</h2>
          <p>Investigacao dos custos por categoria com drill down ate os lancamentos do RAZAO.</p>
        </div>
      </section>

      <section className="econ-kpi-grid">
        <CostKpi title="Custos Diretos" data={data.kpis?.diretos} />
        <CostKpi title="Custos Indiretos" data={data.kpis?.indiretos} />
        <CostKpi title="Impostos" data={data.kpis?.impostos} />
        <CostKpi title="Custos Totais" data={data.kpis?.totais} />
      </section>

      <section className="econ-invest-grid">
        <div className="econ-chart-card">
          <div className="econ-chart-head">
            <ReceiptText size={18} />
            <div>
              <strong>Custos por Categoria DRE</strong>
              <span>Ordenado pelo maior forecast</span>
            </div>
          </div>
          <div className="econ-chart">
            <Bar data={chartData} options={{
              responsive: true,
              maintainAspectRatio: false,
              indexAxis: 'y',
              plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtBRL(ctx.parsed.x) } } },
              scales: { x: { ticks: { callback: v => fmtBRL(v).replace('R$', 'R$ ') } }, y: { grid: { display: false } } },
            }} />
          </div>
        </div>

        <div className="econ-table-card">
          <div className="econ-chart-head">
            <FileSearch size={18} />
            <div>
              <strong>Top Custos</strong>
              <span>Clique em uma categoria para investigar</span>
            </div>
          </div>
          <CostTable rows={data.top_custos || []} selected={selected} onSelect={setSelected} />
        </div>
      </section>

      <section className="econ-table-card">
        <div className="econ-chart-head">
          <FileSearch size={18} />
          <div>
            <strong>Top Estouros</strong>
            <span>Maior diferenca absoluta entre Forecast e Linha Base</span>
          </div>
        </div>
        <CostTable rows={data.top_estouros || []} selected={selected} onSelect={setSelected} compact />
      </section>

      <DetailPanel categoria={selected} />
    </div>
  )
}

function CostTable({ rows, selected, onSelect, compact }) {
  return (
    <div className="econ-table-wrap">
      <table className="econ-table">
        <thead>
          <tr>
            <th>Categoria</th>
            {!compact && <th>Previsto</th>}
            <th>Forecast</th>
            {!compact && <th>Realizado</th>}
            <th>Desvio</th>
            <th>Impacto %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.categoria} className={selected === row.categoria  'is-selected' : ''} onClick={() => onSelect(row.categoria)}>
              <td><strong>{row.categoria}</strong></td>
              {!compact && <td>{fmtBRL(row.previsto)}</td>}
              <td>{fmtBRL(row.forecast)}</td>
              {!compact && <td>{fmtBRL(row.realizado)}</td>}
              <td className={row.desvio < 0  'danger' : 'success'}>{fmtBRL(row.desvio)}</td>
              <td>{fmtPct(row.impacto_percentual)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
