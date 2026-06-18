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
import { Bar } from 'react-chartjs-2'
import { Filter, Search, SlidersHorizontal } from 'lucide-react'
import { getEconomicoCentroAnalise, getEconomicoLancamentos } from '../api'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend)

const fmtBRL = (v) =>
  (v ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) =>
  `${((v ?? 0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtDate = (v) => v ? new Date(`${v}T12:00:00`).toLocaleDateString('pt-BR') : '-'

function AnaliseKpi({ label, value, format = 'money', tone }) {
  return (
    <section className="analysis-kpi">
      <span>{label}</span>
      <strong className={tone || ''}>{format === 'pct' ? fmtPct(value) : fmtBRL(value)}</strong>
    </section>
  )
}

export default function EconomicoCentroAnalise() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)
  const [filters, setFilters] = useState({})
  const [selection, setSelection] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    getEconomicoCentroAnalise(filters)
      .then(setData)
      .catch(e => setErro(e.response?.data?.detail || e.message))
  }, [filters])

  useEffect(() => {
    if (!selection) return
    getEconomicoLancamentos({ ...filters, [selection.tipo]: selection.valor, limit: 200 }).then(setDetail)
  }, [selection, filters])

  const filtros = data?.filtros || {}
  const kpis = data?.kpis || {}
  const pareto = useMemo(() => data?.pareto || [], [data])
  const chartData = {
    labels: pareto.map(r => r.categoria),
    datasets: [
      {
        type: 'bar',
        label: 'Impacto',
        data: pareto.map(r => Math.abs(r.impacto)),
        backgroundColor: '#2563EB',
        borderRadius: 4,
        yAxisID: 'y',
      },
      {
        type: 'line',
        label: 'Acumulado %',
        data: pareto.map(r => (r.acumulado || 0) * 100),
        borderColor: '#0F172A',
        backgroundColor: '#0F172A',
        tension: 0.25,
        yAxisID: 'y1',
      },
    ],
  }

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando centro de analise...</div></div>

  const updateFilter = (key, value) => setFilters(current => ({ ...current, [key]: value || undefined }))
  const clearFilters = () => {
    setFilters({})
    setSelection(null)
    setDetail(null)
  }

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestao Economica - Fase 1D</span>
          <h2>Centro de Analise Economica</h2>
          <p>Investigacao gerencial por categoria, fornecedor, conta e documento com origem nos dados auditados.</p>
        </div>
      </section>

      <section className="analysis-filters">
        <label><Filter size={14} /><input type="date" value={filters.periodo_inicio || ''} onChange={e => updateFilter('periodo_inicio', e.target.value)} /></label>
        <label><input type="date" value={filters.periodo_fim || ''} onChange={e => updateFilter('periodo_fim', e.target.value)} /></label>
        <label>
          <select value={filters.categoria || ''} onChange={e => updateFilter('categoria', e.target.value)}>
            <option value="">Categoria DRE</option>
            {(filtros.categorias || []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          <select value={filters.conta || ''} onChange={e => updateFilter('conta', e.target.value)}>
            <option value="">Conta</option>
            {(filtros.contas || []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          <select value={filters.fornecedor || ''} onChange={e => updateFilter('fornecedor', e.target.value)}>
            <option value="">Fornecedor</option>
            {(filtros.fornecedores || []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          <select value={filters.documento || ''} onChange={e => updateFilter('documento', e.target.value)}>
            <option value="">Documento</option>
            {(filtros.documentos || []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <button type="button" className="analysis-clear" onClick={clearFilters}>Limpar</button>
      </section>

      <section className="analysis-kpi-grid">
        <AnaliseKpi label="Previsto" value={kpis.previsto} />
        <AnaliseKpi label="Forecast" value={kpis.forecast} />
        <AnaliseKpi label="Realizado" value={kpis.realizado} />
        <AnaliseKpi label="Desvio" value={kpis.desvio} tone={kpis.desvio < 0 ? 'danger' : 'success'} />
        <AnaliseKpi label="Impacto %" value={kpis.impacto_percentual} format="pct" />
        <AnaliseKpi label="Participacao %" value={kpis.participacao_percentual} format="pct" />
      </section>

      <section className="analysis-grid">
        <AnalysisTable
          title="Analise por Categoria"
          rows={data.analise_categoria || []}
          columns={[
            ['categoria', 'Categoria'],
            ['previsto', 'Previsto', 'money'],
            ['forecast', 'Forecast', 'money'],
            ['realizado', 'Realizado', 'money'],
            ['desvio', 'Desvio', 'money-tone'],
            ['impacto_percentual', 'Impacto %', 'pct'],
            ['participacao_percentual', 'Participacao %', 'pct'],
          ]}
          onSelect={row => setSelection({ tipo: 'categoria', valor: row.categoria, titulo: row.categoria })}
        />
        <AnalysisTable
          title="Analise por Fornecedor"
          rows={data.analise_fornecedor || []}
          columns={[
            ['fornecedor', 'Fornecedor'],
            ['valor_contratado', 'Contratado', 'money'],
            ['forecast', 'Forecast', 'money'],
            ['realizado', 'Realizado', 'money'],
            ['desvio', 'Desvio', 'money-tone'],
            ['impacto_percentual', 'Impacto %', 'pct'],
          ]}
          onSelect={row => setSelection({ tipo: 'fornecedor', valor: row.fornecedor, titulo: row.fornecedor })}
        />
      </section>

      <section className="analysis-grid">
        <AnalysisTable
          title="Analise por Conta"
          rows={data.analise_conta || []}
          columns={[
            ['conta', 'Conta'],
            ['descricao', 'Descricao'],
            ['previsto', 'Previsto', 'money'],
            ['forecast', 'Forecast', 'money'],
            ['realizado', 'Realizado', 'money'],
            ['desvio', 'Desvio', 'money-tone'],
          ]}
          onSelect={row => setSelection({ tipo: 'conta', valor: row.conta, titulo: `${row.conta} - ${row.descricao}` })}
        />
        <section className="econ-chart-card">
          <div className="econ-chart-head">
            <SlidersHorizontal size={18} />
            <div>
              <strong>Pareto Financeiro</strong>
              <span>Top categorias responsaveis pelo impacto</span>
            </div>
          </div>
          <div className="econ-chart">
            <Bar data={chartData} options={{
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: ctx => ctx.dataset.yAxisID === 'y1'  `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%` : `${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}` } },
              },
              scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 6 } },
                y: { ticks: { callback: v => fmtBRL(v).replace('R$', 'R$ ') } },
                y1: { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { callback: v => `${v}%` } },
              },
            }} />
          </div>
        </section>
      </section>

      <section className="econ-detail">
        <div className="econ-detail-head">
          <div>
            <span className="eyebrow">Drill Down - RAZAO</span>
            <h3>{selection?.titulo || 'Selecione categoria, fornecedor ou conta'}</h3>
            <p>{selection  `Total filtrado: ${fmtBRL(detail?.total || 0)}` : 'Documentos, fornecedores, contas, categoria DRE e valores.'}</p>
          </div>
          <Search size={22} />
        </div>
        <LancamentosTable rows={detail?.lancamentos || []} />
      </section>
    </div>
  )
}

function AnalysisTable({ title, rows, columns, onSelect }) {
  return (
    <section className="econ-table-card">
      <div className="econ-chart-head">
        <Search size={18} />
        <div>
          <strong>{title}</strong>
          <span>Clique em uma linha para detalhar</span>
        </div>
      </div>
      <div className="econ-table-wrap analysis-table-scroll">
        <table className="econ-table">
          <thead>
            <tr>{columns.map(col => <th key={col[0]}>{col[1]}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${title}-${idx}`} onClick={() => onSelect(row)}>
                {columns.map(([key, , type]) => {
                  const value = row[key]
                  const className = type === 'money-tone' ? (value < 0 ? 'danger' : 'success') : ''
                  return (
                    <td key={key} className={className}>
                      {type === 'money' || type === 'money-tone'  fmtBRL(value) : type === 'pct'  fmtPct(value) : <strong>{value || '-'}</strong>}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function LancamentosTable({ rows }) {
  return (
    <div className="econ-table-wrap">
      <table className="econ-table">
        <thead>
          <tr>
            <th>Documento</th>
            <th>Fornecedor</th>
            <th>Data</th>
            <th>Conta</th>
            <th>Categoria DRE</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.id}>
              <td><strong>{row.documento || '-'}</strong><span>{row.historico || '-'}</span></td>
              <td>{row.fornecedor || '-'}</td>
              <td>{fmtDate(row.data)}</td>
              <td><strong>{row.conta || '-'}</strong><span>{row.conta_descricao || '-'}</span></td>
              <td>{row.categoria_dre || '-'}</td>
              <td>{fmtBRL(row.valor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
