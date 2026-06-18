import { useEffect, useRef, useState } from 'react'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { Line, Bar } from 'react-chartjs-2'
import { Factory, Upload, AlertTriangle, Clock, Flag } from 'lucide-react'
import { getProducaoDashboard, importProducaoXer } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler)

const NAVY = '#063057'
const GREEN = '#1f9d57'
const BLUE = '#185FA5'
const RED = '#A32D2D'
const fmt = (v) => Number.isFinite(v) ? `${v.toFixed(1).replace('.', ',')}%` : '–'
const fmtDate = (s) => s ? s.split('-').reverse().join('/') : '–'
const corDesvio = (v) => v >= 0 ? GREEN : RED

export default function Producao() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [importando, setImportando] = useState(false)
  const fileRef = useRef()

  async function carregar() {
    setLoading(true)
    try { setData(await getProducaoDashboard()) }
    finally { setLoading(false) }
  }
  useEffect(() => { carregar() }, [])

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setImportando(true)
    try {
      const fd = new FormData(); fd.append('arquivo', file)
      await importProducaoXer(fd)
      await carregar()
    } catch (err) {
      alert('Erro ao importar XER: ' + (err.response?.data?.detail || err.message))
    } finally {
      setImportando(false); if (fileRef.current) fileRef.current.value = ''
    }
  }

  if (loading) return <div style={{ padding: 24, color: '#777' }}>Carregando…</div>

  if (!data?.tem_dados) {
    return (
      <div className="placeholder-page">
        <div className="placeholder-panel">
          <span className="executive-icon"><Factory size={22} /></span>
          <div>
            <span className="eyebrow">Produção</span>
            <h2>Importe o cronograma (XER)</h2>
            <p>Envie o arquivo .xer do Primavera P6 para montar o painel executivo do cronograma.</p>
            <label className="btn-primary" style={{ cursor: 'pointer', display: 'inline-flex', gap: 8, alignItems: 'center' }}>
              <Upload size={16} /> {importando ? 'Importando…' : 'Importar XER'}
              <input ref={fileRef} type="file" accept=".xer" onChange={handleUpload} style={{ display: 'none' }} disabled={importando} />
            </label>
          </div>
        </div>
      </div>
    )
  }

  const { projeto, kpis, disciplinas, tendencia_semanal, evolucao_mensal, curva_s, criticas, atrasadas, marcos, sinais, aviso_planejado, metodo } = data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Cabeçalho */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, color: '#888' }}>Cronograma · {projeto.nome}</div>
          <div style={{ fontSize: 13, color: NAVY, fontWeight: 600 }}>
            Data date {fmtDate(projeto.data_date)} · {fmtDate(projeto.plan_start)} → {fmtDate(projeto.plan_end)}
          </div>
        </div>
        <label className="btn-primary" style={{ marginLeft: 'auto', cursor: 'pointer', display: 'inline-flex', gap: 8, alignItems: 'center', fontSize: 12 }}>
          <Upload size={14} /> {importando ? 'Importando…' : 'Reimportar XER'}
          <input ref={fileRef} type="file" accept=".xer" onChange={handleUpload} style={{ display: 'none' }} disabled={importando} />
        </label>
      </div>

      {/* Aviso: planejado pela programação atual (sem baseline) */}
      {aviso_planejado && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12,
                      background: '#FFF8E6', border: '1px solid #F0D98C', borderRadius: 8, padding: '10px 14px', color: '#7A5B00' }}>
          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>{aviso_planejado}</span>
        </div>
      )}

      {/* Linha 1 — KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        <KpiAvanco titulo="Avanço Semanal" k={kpis.semana} />
        <KpiAvanco titulo="Avanço Mensal" k={kpis.mes} />
        <KpiAvanco titulo="Avanço Acumulado" k={kpis.acumulado} destaque />
        <KpiSpi spi={kpis.spi} />
        <KpiAtividades c={kpis.atividades} />
      </div>

      {/* Linha 2 — Produção por disciplina */}
      <Bloco titulo="Produção por Disciplina">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 10 }}>
          {disciplinas.map(d => (
            <div key={d.disciplina} style={card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <strong style={{ fontSize: 13, color: NAVY }}>{d.disciplina}</strong>
                <span style={{ fontSize: 10, color: '#999' }}>
                  {metodo?.peso_total  `${(d.peso / metodo.peso_total * 100).toFixed(1)}% peso · ` : ''}{d.atividades} ativ.
                </span>
              </div>
              <div style={{ display: 'flex', gap: 14, marginTop: 8 }}>
                <Mini label="Realizado" valor={fmt(d.realizado)} cor={GREEN} />
                <Mini label="Restante" valor={fmt(d.tendencia)} cor="#888" />
              </div>
              <Barra plan={0} real={d.realizado} />
            </div>
          ))}
        </div>
      </Bloco>

      {/* Linha 3 e 4 — Tendência semanal + Evolução mensal */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 12 }}>
        <Bloco titulo="Tendência Semanal (acumulado)">
          <div style={{ height: 240 }}>
            <Line data={serie(tendencia_semanal, 'data', fmtDate)} options={lineOpts} />
          </div>
        </Bloco>
        <Bloco titulo="Evolução Mensal (acumulado)">
          <div style={{ height: 240 }}>
            <Bar data={serie(evolucao_mensal, 'mes')} options={lineOpts} />
          </div>
        </Bloco>
      </div>

      {/* Linha 5 — Curva S resumida */}
      <Bloco titulo="Curva S — Planejado × Realizado">
        <div style={{ height: 280 }}>
          <Line data={serie(curva_s, 'mes')} options={lineOpts} />
        </div>
      </Bloco>

      {/* Linha 6 — Atividades críticas / atrasadas / marcos */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 12 }}>
        <TabelaAtiv titulo="Atividades Críticas" icon={AlertTriangle} cor={RED} itens={criticas} mostraFloat />
        <TabelaAtiv titulo="Atividades Atrasadas" icon={Clock} cor="#C9821B" itens={atrasadas} />
        <TabelaAtiv titulo="Marcos Próximos" icon={Flag} cor={BLUE} itens={marcos}
                    vazio={`Apenas ${sinais.marcos_no_xer} marco(s) no XER.`} />
      </div>

      {/* Sinais (transparência sobre o que o XER limita) */}
      <div style={{ fontSize: 11, color: '#8a8a8a', background: '#FAFAF8', border: '1px solid #ECECE8', borderRadius: 8, padding: '10px 14px' }}>
        <strong>Notas do cronograma:</strong> ponderação por duração ·
        {' '}{sinais.sem_disciplina} atividades sem disciplina marcada ·
        {' '}responsável preenchido em {sinais.com_responsavel} ·
        {' '}marcos no XER: {sinais.marcos_no_xer} ·
        {' '}sem linha de base separada (planejado = datas-alvo do cronograma).
      </div>
    </div>
  )
}

// ── Subcomponentes ───────────────────────────────────────────────────────────
const card = { background: '#fff', border: '1px solid #ECECE8', borderRadius: 8, padding: 12 }

function Bloco({ titulo, children }) {
  return (
    <div style={{ ...card, padding: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{titulo}</div>
      {children}
    </div>
  )
}

function KpiAvanco({ titulo, k, destaque }) {
  const semPrev = k.planejado == null
  return (
    <div style={{ ...card, borderTop: `3px solid ${destaque ? NAVY : '#D7D7D2'}` }}>
      <div style={{ fontSize: 11, color: '#888', fontWeight: 600 }}>{titulo}</div>
      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
        <Mini label="Previsto" valor={semPrev ? 'BL?' : fmt(k.planejado)} cor={semPrev ? '#bbb' : BLUE} grande />
        <Mini label="Realizado" valor={fmt(k.realizado)} cor={GREEN} grande />
        {k.tendencia != null && <Mini label="Restante" valor={fmt(k.tendencia)} cor="#888" grande />}
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
        Desvio <strong style={{ color: k.desvio == null ? '#bbb' : corDesvio(k.desvio) }}>{k.desvio == null ? 'aguardando BL' : fmt(k.desvio)}</strong>
      </div>
    </div>
  )
}

function KpiSpi({ spi }) {
  const mapa = {
    adiantado: { txt: 'Adiantado', cor: GREEN },
    dentro_esperado: { txt: 'Dentro do esperado', cor: '#C9821B' },
    atrasado: { txt: 'Atrasado', cor: RED },
    indisponivel: { txt: 'Aguardando BL', cor: '#999' },
    indefinido: { txt: '—', cor: '#999' },
  }
  const m = mapa[spi?.classificacao] || mapa.indefinido
  return (
    <div style={{ ...card, borderTop: `3px solid ${m.cor}` }}>
      <div style={{ fontSize: 11, color: '#888', fontWeight: 600 }}>Eficiência (SPI)</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: m.cor, marginTop: 4 }}>
        {spi?.valor != null  `${spi.valor.toFixed(1).replace('.', ',')}%` : '–'}
      </div>
      <div style={{ fontSize: 11, color: m.cor, fontWeight: 600 }}>{m.txt}</div>
      <div style={{ fontSize: 10, color: '#aaa', marginTop: 4 }}>Realizado ÷ Planejado</div>
    </div>
  )
}

function KpiAtividades({ c }) {
  return (
    <div style={{ ...card, borderTop: '3px solid #D7D7D2' }}>
      <div style={{ fontSize: 11, color: '#888', fontWeight: 600 }}>Atividades</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: NAVY, marginTop: 4 }}>{c.total}</div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11 }}>
        <span style={{ color: GREEN }}>● {c.concluidas} concl.</span>
        <span style={{ color: BLUE }}>● {c.em_andamento} em and.</span>
        <span style={{ color: '#999' }}>● {c.nao_iniciadas} n/ inic.</span>
      </div>
    </div>
  )
}

function Mini({ label, valor, cor, grande }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#999' }}>{label}</div>
      <div style={{ fontSize: grande  18 : 13, fontWeight: 700, color: cor }}>{valor}</div>
    </div>
  )
}

function Barra({ plan, real }) {
  return (
    <div style={{ marginTop: 8, height: 6, background: '#EEE', borderRadius: 3, position: 'relative' }}>
      <div style={{ position: 'absolute', height: '100%', width: `${Math.min(100, plan)}%`, background: BLUE, opacity: 0.35, borderRadius: 3 }} />
      <div style={{ position: 'absolute', height: '100%', width: `${Math.min(100, real)}%`, background: GREEN, borderRadius: 3 }} />
    </div>
  )
}

function TabelaAtiv({ titulo, icon: Icon, cor, itens, mostraFloat, vazio }) {
  return (
    <div style={{ ...card, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Icon size={16} color={cor} />
        <strong style={{ fontSize: 12, color: NAVY, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{titulo}</strong>
      </div>
      {itens.length === 0 ? (
        <div style={{ fontSize: 12, color: '#999', fontStyle: 'italic' }}>{vazio || 'Nenhuma atividade.'}</div>
      ) : (
        <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: '#999', textAlign: 'left' }}>
              <th style={{ padding: '2px 4px' }}>Atividade</th>
              <th style={{ padding: '2px 4px' }}>Disc.</th>
              <th style={{ padding: '2px 4px' }}>Término</th>
              <th style={{ padding: '2px 4px', textAlign: 'right' }}>{mostraFloat ? 'Folga' : '%'}</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((a, i) => (
              <tr key={i} style={{ borderTop: '1px solid #F0F0EC' }}>
                <td style={{ padding: '3px 4px' }} title={a.nome}>
                  <div style={{ fontWeight: 600, color: NAVY }}>{a.task_code}</div>
                  <div style={{ color: '#888', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.nome}</div>
                </td>
                <td style={{ padding: '3px 4px', color: '#666' }}>{a.disciplina || '–'}</td>
                <td style={{ padding: '3px 4px', color: '#666' }}>{fmtDate(a.target_end)}</td>
                <td style={{ padding: '3px 4px', textAlign: 'right', fontWeight: 600 }}>
                  {mostraFloat ? (a.float_dias != null ? `${a.float_dias}d` : '–') : fmt(a.phys_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

// ── Helpers de gráfico ───────────────────────────────────────────────────────
function serie(arr, labelKey, labelFmt) {
  return {
    labels: arr.map(p => labelFmt  labelFmt(p[labelKey]) : p[labelKey]),
    datasets: [
      { label: 'Planejado', data: arr.map(p => p.planejado), borderColor: BLUE, backgroundColor: 'rgba(24,95,165,0.15)', tension: 0.3, fill: true, pointRadius: 2 },
      { label: 'Realizado', data: arr.map(p => p.realizado), borderColor: GREEN, backgroundColor: 'rgba(31,157,87,0.15)', tension: 0.3, fill: true, pointRadius: 2 },
    ],
  }
}

const lineOpts = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { labels: { font: { size: 11 }, boxWidth: 12 } } },
  scales: {
    y: { ticks: { callback: v => `${v}%`, font: { size: 10 } } },
    x: { ticks: { font: { size: 9 }, maxRotation: 45, autoSkip: true, maxTicksLimit: 14 } },
  },
}
