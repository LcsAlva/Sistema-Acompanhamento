import { useEffect, useState } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler,
} from 'chart.js'
import {
  getMedicaoEngDashboard, getMedicaoEngPorDisciplina, getMedicaoEngEvolucao, getMedicaoEngConfig,
} from '../api'

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler)

const C = {
  wrap: { padding: 24, maxWidth: 1200, margin: '0 auto' },
  h1: { fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 },
  sub: { color: '#6b7280', fontSize: 13, marginTop: 4 },
  card: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, marginTop: 16 },
  th: { textAlign: 'left', padding: '8px 10px', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #e5e7eb' },
  td: { padding: '8px 10px', fontSize: 13, borderBottom: '1px solid #f3f4f6' },
}

const pct = (v) => `${((v || 0) * 100).toFixed(1)}%`

export default function MotorMedicao() {
  const [dash, setDash] = useState(null)
  const [disc, setDisc] = useState([])
  const [evol, setEvol] = useState([])
  const [cfg, setCfg] = useState(null)

  useEffect(() => {
    (async () => {
      const [d, p, e, c] = await Promise.all([
        getMedicaoEngDashboard(), getMedicaoEngPorDisciplina(),
        getMedicaoEngEvolucao(12), getMedicaoEngConfig(),
      ])
      setDash(d); setDisc(p); setEvol(e); setCfg(c)
    })()
  }, [])

  const chartData = {
    labels: evol.map(p => p.semana_fim?.slice(5)),
    datasets: [{
      label: '% Medido (SEM WORKFLOW)',
      data: evol.map(p => +(p.pct_medido * 100).toFixed(1)),
      borderColor: '#1d4ed8', backgroundColor: 'rgba(29,78,216,0.12)',
      fill: true, tension: 0.3, pointRadius: 3,
    }],
  }
  const chartOpts = {
    responsive: true, maintainAspectRatio: false, animation: false,
    scales: { y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } } },
    plugins: { legend: { position: 'top' }, tooltip: { callbacks: { label: c => `${c.parsed.y}%` } } },
  }

  return (
    <div style={C.wrap}>
      <h1 style={C.h1}>Motor de Medição de Engenharia</h1>
      <div style={C.sub}>
        Medição automática a partir da LD/SIGEM: documento <b>SEM WORKFLOW</b> = 100% aceito.
        {cfg && <> Status aptos: <b>{cfg.status_aptos.join(', ')}</b> · peso por <b>{cfg.peso_por}</b>.</>}
      </div>

      {/* Cards */}
      {dash && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginTop: 16 }}>
          <Card label="Documentos Totais" v={dash.documentos_totais} cor="#111827" />
          <Card label="Em Elaboração" v={dash.em_elaboracao} cor="#6b7280" />
          <Card label="Em Análise" v={dash.em_analise} cor="#b45309" />
          <Card label="Sem Workflow" v={dash.sem_workflow} cor="#166534" />
          <Card label="% Medido" v={pct(dash.pct_medido)} cor="#1d4ed8" destaque />
        </div>
      )}
      {dash && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>
          Status oficial por SIGEM: <b>{dash.status_origem_sigem || 0}</b> documento(s). Fallback LD: <b>{dash.status_origem_ld || 0}</b>.
        </div>
      )}

      {/* Evolução */}
      <div style={C.card}>
        <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>Evolução semanal da medição</h3>
        <div style={{ height: 300 }}>
          {evol.length > 0  <Line data={chartData} options={chartOpts} />
            : <div style={{ color: '#9ca3af', fontSize: 13 }}>Sem histórico ainda. Importe LDs ao longo das semanas.</div>}
        </div>
      </div>

      {/* Por disciplina */}
      <div style={C.card}>
        <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>Medição por disciplina</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={C.th}>Disciplina</th><th style={C.th}>Docs</th>
              <th style={C.th}>Medidos</th><th style={C.th}>A4 medido</th>
              <th style={C.th}>A4 total</th><th style={C.th}>Origem SIGEM</th><th style={C.th}>% Medição</th>
            </tr>
          </thead>
          <tbody>
            {disc.map(d => (
              <tr key={d.disciplina}>
                <td style={C.td}><b>{d.disciplina}</b></td>
                <td style={C.td}>{d.docs_totais}</td>
                <td style={C.td}>{d.docs_medidos}</td>
                <td style={C.td}>{d.a4_acumulado  '—'}</td>
                <td style={C.td}>{d.a4_total  '—'}</td>
                <td style={C.td}>{d.status_origem_sigem || 0}</td>
                <td style={C.td}>
                  <BarPct v={d.pct_medicao} />
                </td>
              </tr>
            ))}
            {disc.length === 0 && <tr><td style={C.td} colSpan={7}>Sem documentos importados.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Card({ label, v, cor, destaque }) {
  return (
    <div style={{ background: destaque  '#eff6ff' : 'white', border: `1px solid ${destaque  '#bfdbfe' : '#e5e7eb'}`, borderRadius: 10, padding: 16 }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: cor }}>{v}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function BarPct({ v }) {
  const p = Math.round((v || 0) * 100)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, maxWidth: 140, height: 8, background: '#f3f4f6', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${p}%`, height: '100%', background: '#1d4ed8' }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600 }}>{p}%</span>
    </div>
  )
}
