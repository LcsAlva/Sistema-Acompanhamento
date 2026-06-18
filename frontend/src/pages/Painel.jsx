import { useEffect, useRef, useState } from 'react'
import { useRef as useInputRef } from 'react'
import { useSemana } from '../context/SemanaContext'
import { getPainel, recalcularPainel, importarXerPainel } from '../api'
import {
  Chart,
  BarElement, BarController,
  LineElement, LineController, PointElement,
  CategoryScale, LinearScale,
  Tooltip, Legend,
} from 'chart.js'
Chart.register(
  BarElement, BarController,
  LineElement, LineController, PointElement,
  CategoryScale, LinearScale,
  Tooltip, Legend
)

// ── Helpers de formatação ─────────────────────────────────────────────────────

const fmt = v => v == null  '—' : `${Number(v).toFixed(2).replace('.', ',')}%`
const fmtDesvio = v => v == null  '—' : `${v >= 0  '+' : ''}${Number(v).toFixed(2).replace('.', ',')}%`
const desvioColor = v => v > 0  '#16a34a' : v < 0  '#dc2626' : '#374151'

// ── Estilos reutilizáveis ─────────────────────────────────────────────────────

const cardStyle = { background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }
const thStyle   = { background: '#063057', color: 'white', padding: '6px 10px', fontSize: 11, fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap' }
const tdStyle   = { padding: '5px 10px', fontSize: 11, textAlign: 'center', borderBottom: '1px solid #f0f0f0' }

// ── Configuração de gráfico misto (barras + linhas) ──────────────────────────

function buildMixedChartConfig(labels, datasets, maxBar, maxLine) {
  return {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        yBar: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: '% Período', font: { size: 10 } },
          max: maxBar,
          ticks: { font: { size: 9 } },
        },
        yLine: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: '% Acumulado', font: { size: 10 } },
          max: maxLine,
          ticks: { font: { size: 9 } },
          grid: { drawOnChartArea: false },
        },
        x: { ticks: { maxRotation: 45, font: { size: 9 } } },
      },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y != null  ctx.parsed.y.toFixed(2) : '—'}%`,
          },
        },
      },
      animation: false,
    },
  }
}

// ── Fatos geradores (estáticos — editados na tela de Textos por enquanto) ─────

const FATOS = [
  {
    fase: 'ENGENHARIA DE DETALHAMENTO',
    desvio_ref: 'ENG. DETALHAMENTO',
    itens: [
      'Atrasos no detalhamento das bombas (Impacto ETM)',
      'Atrasos na emissão da documentação da GVCO onsite e offsite (dependência dos documentos ZEECO/Petrobras)',
      'Atrasos na emissão da documentação de eletrocentro (dependência dos documentos ZEECO/Petrobras)',
      'Atrasos na emissão da documentação do duto flue gas (dependência dos documentos ZEECO/Petrobras)',
      'Atrasos na emissão da documentação do CAG (Impacto ETM)',
      'Atrasos na emissão da documentação de suprimentos (Impacto ETM/Petrobras)',
      'Atrasos no design review (30%) (Impacto ETM)',
      'Atrasos na modelagem 3D (Impacto ETM)',
      'Atrasos em documentos complementares de eletrocentro, CAG e elétrica/envelopes do TGV',
      'Atrasos no as built de documentação de projeto emitida da nova caldeira GVCO (dependência dos documentos ZEECO/Petrobras)',
    ],
    fatos: `1- O atraso na fase de Engenharia decorre do replanejamento consolidado na LD Rev. C, a ser integrada ao cronograma do contrato até 30/03/26, conforme alinhamento com a Fiscalização.
O avanço está sendo impactado principalmente por interfaces dos documentos de subfornecedores da Petrobras (ZEECO e WEG), com documentos que se mantêm com status recusados e/ou com comentários no SIGEM, exigindo reanálise para assegurar a precedência correta da engenharia de detalhamento.

Principais Impactos com Interface de fornecimento Petrobras:
- Dados do inversor de frequência do Blower, onde somente informações dimensionais estimadas foram passadas para a ETM;
- Remessa considerável dos documentos da ZEECO em tramitação, quando originalmente deveriam estar numa fase mais avançada para viabilizar o detalhamento do projeto executivo.

Para ambos os casos, os comentários estão em análise e discussão com a Petrobras/Fiscalização.`,
  },
  {
    fase: 'CONSTRUÇÃO CIVIL',
    desvio_ref: 'CONSTRUÇÃO CIVIL',
    itens: [
      'Demolição e remoção de piso na área do eletrocentro (dependência dos documentos ZEECO/Petrobras)',
      'Nova área de hidratação – revestimentos, tubulação de água fria, louças, instalações elétricas, aterramento e SPDA (Impacto ETM)',
      'Estaqueamento e bases da GVCO (dependência dos documentos ZEECO/Petrobras)',
      'Desmontagem e adequação de estrutura metálica no pipe rack do novo duto de CO (dependência dos documentos ZEECO/Petrobras)',
      'Fabricação e montagem de vigas complementares para adequação do pipe rack existente (dependência dos documentos ZEECO/Petrobras)',
    ],
    fatos: `1- A etapa da C. Civil que representa o atraso da disciplina está associada à etapa de Fundações, Bases e Dormentes, mesmo que iniciada a execução das estacas na área do TGV.

2- Desmontagem da estrutura do Pipe Rack existente impactada pelo atraso dos documentos do duto de CO, que são provenientes também de informações de responsabilidade da ZEECO/Petrobras. Apesar deste tema ter sido superado, o desvio ainda é reflexo deste atraso.`,
  },
  {
    fase: 'ELETROMECÂNICA',
    desvio_ref: 'MONTAGEM ELETROMECÂNICA',
    itens: ['Atraso referente à fabricação parcial do duto de CO (dependência dos documentos ZEECO/Petrobras)'],
    fatos: `1- Esse atraso é decorrente do atraso do detalhamento de engenharia, já justificado acima.`,
  },
  {
    fase: 'COMISSIONAMENTO',
    desvio_ref: 'COMISSIONAMENTO',
    itens: [
      'Atraso referente à emissão dos PACOTES 1, 2, 3 e atraso parcial do PACOTE 4 (Impacto ETM)',
      'Atividade de preservação de bens tagueados e não-tagueados (Impacto ETM)',
      'Atividade de condicionamento, FVs dos itens comissionáveis (Impacto ETM)',
    ],
    fatos: `1- Manual de Comissionamento em análise, após atendimento aos comentários por parte da fiscalização e detalhamento dos pacotes (Em andamento).

2- Equipe para desenvolvimento dos pacotes 1 a 4 previsto para o comissionamento com mobilização prevista para abril/26.

3- O atraso no desenvolvimento dos procedimentos em seus respectivos pacotes não tem gerado impacto em outras etapas do contrato.`,
  },
]

// ── Componente principal ──────────────────────────────────────────────────────

export default function Painel() {
  const { semanaAtual } = useSemana()
  const semanaCode = semanaAtual?.codigo || ''

  const [dados, setDados] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState(null)
  const [recalcLoading, setRecalcLoading] = useState(false)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState(null)
  const fileInputRef = useInputRef(null)

  const geralCanvasRef   = useRef(null)
  const semanalCanvasRef = useRef(null)
  const geralChart       = useRef(null)
  const semanalChart     = useRef(null)

  useEffect(() => {
    if (!semanaCode) return
    setLoading(true)
    setErro(null)
    getPainel(semanaCode)
      .then(d => { setDados(d); setLoading(false) })
      .catch(() => { setErro('Erro ao carregar dados do painel.'); setLoading(false) })
  }, [semanaCode])

  // Gráfico Geral (mensal)
  useEffect(() => {
    if (!geralCanvasRef.current || !dados?.geral?.length) return
    geralChart.current?.destroy()

    const d = dados.geral
    const datasets = [
      { type: 'bar',  label: 'Prev. Período',  data: d.map(x => x.prevSem), backgroundColor: 'rgba(47,117,181,0.7)', yAxisID: 'yBar' },
      { type: 'bar',  label: 'Real Período',   data: d.map(x => x.realSem), backgroundColor: 'rgba(112,173,71,0.7)',  yAxisID: 'yBar' },
      { type: 'line', label: 'Previsto Ac.',   data: d.map(x => x.prevAc),  borderColor: '#2f75b5', backgroundColor: 'transparent', borderWidth: 2.5, pointRadius: 2, tension: 0.1, yAxisID: 'yLine' },
      { type: 'line', label: 'Real Ac.',       data: d.map(x => x.realAc),  borderColor: '#70ad47', backgroundColor: 'transparent', borderWidth: 2.5, pointRadius: 2, tension: 0.1, yAxisID: 'yLine' },
    ]
    const maxBar  = Math.max(15, ...d.map(x => x.prevSem || 0).filter(Boolean)) * 1.2
    const maxLine = 100
    geralChart.current = new Chart(geralCanvasRef.current, buildMixedChartConfig(d.map(x => x.nome), datasets, maxBar, maxLine))
    return () => { geralChart.current?.destroy() }
  }, [dados])

  // Gráfico Semanal
  useEffect(() => {
    if (!semanalCanvasRef.current || !dados?.semanal?.length) return
    semanalChart.current?.destroy()

    const d = dados.semanal
    const semAtualIdx = d.findIndex(x => x.semana === semanaCode)
    const labelColors = d.map((_, i) => i === semAtualIdx  '#f59e0b' : '#374151')

    const datasets = [
      { type: 'bar',  label: 'Prev. Período',  data: d.map(x => x.prev),   backgroundColor: 'rgba(47,117,181,0.7)', yAxisID: 'yBar' },
      { type: 'bar',  label: 'Real Período',   data: d.map(x => x.real),   backgroundColor: 'rgba(112,173,71,0.7)',  yAxisID: 'yBar' },
      { type: 'line', label: 'Previsto Ac.',   data: d.map(x => x.prevAc), borderColor: '#2f75b5', backgroundColor: 'transparent', borderWidth: 2.5, pointRadius: 3, tension: 0.1, yAxisID: 'yLine' },
      { type: 'line', label: 'Real Ac.',       data: d.map(x => x.realAc), borderColor: '#70ad47', backgroundColor: 'transparent', borderWidth: 2.5, pointRadius: 3, tension: 0.1, yAxisID: 'yLine' },
    ]
    const maxBar  = Math.max(2, ...d.map(x => x.prev || 0).filter(Boolean)) * 1.3
    const maxLine = Math.max(20, ...d.map(x => x.prevAc || 0).filter(Boolean)) * 1.1
    const cfg = buildMixedChartConfig(d.map(x => x.nome), datasets, maxBar, maxLine)
    cfg.options.scales.x.ticks.color = labelColors
    semanalChart.current = new Chart(semanalCanvasRef.current, cfg)
    return () => { semanalChart.current?.destroy() }
  }, [dados, semanaCode])

  const handleRecalcular = async () => {
    if (!semanaCode) return
    setRecalcLoading(true)
    try {
      await recalcularPainel(semanaCode)
      const d = await getPainel(semanaCode)
      setDados(d)
    } catch { /* silencioso */ }
    setRecalcLoading(false)
  }

  const handleUploadXer = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !semanaCode) return
    setUploadLoading(true)
    setUploadMsg(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await importarXerPainel(semanaCode, fd)
      setUploadMsg({ tipo: 'ok', texto: `XER importado: ${res.tarefas_atualizadas} tarefas atualizadas.` })
      const d = await getPainel(semanaCode)
      setDados(d)
      setErro(null)
    } catch {
      setUploadMsg({ tipo: 'erro', texto: 'Erro ao importar o XER. Verifique o arquivo.' })
    }
    setUploadLoading(false)
    e.target.value = ''
  }

  if (!semanaCode) return (
    <div style={{ padding: 32, color: '#888' }}>Nenhuma semana selecionada.</div>
  )

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: '#555', fontSize: 14 }}>
      Carregando painel...
    </div>
  )

  if (erro || !dados || !dados.calculado) return (
    <div style={{ padding: 32, maxWidth: 520 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: '#063057', marginBottom: 6 }}>
        PAINEL EXECUTIVO — AVANÇO FÍSICO
      </div>
      <p style={{ fontSize: 13, color: '#555', marginBottom: 20 }}>
        Nenhum dado calculado para <strong>{semanaCode}</strong> ainda. Importe o XER do cronograma P6 para começar.
      </p>
      <div style={{ background: 'white', border: '2px dashed #cbd5e1', borderRadius: 8, padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#063057', marginBottom: 4 }}>Selecione o arquivo XER</div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 16 }}>Cronograma P6 completo (.xer) — todos os dados do painel serão calculados automaticamente</div>
        <input ref={fileInputRef} type="file" accept=".xer" onChange={handleUploadXer} style={{ display: 'none' }} />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadLoading}
          style={{ background: '#063057', color: 'white', border: 'none', borderRadius: 6, padding: '10px 28px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          {uploadLoading  '⏳ Importando...' : '⬆ Selecionar XER'}
        </button>
        {uploadMsg && (
          <div style={{ marginTop: 12, fontSize: 12, color: uploadMsg.tipo === 'ok'  '#166534' : '#991b1b' }}>
            {uploadMsg.texto}
          </div>
        )}
      </div>
    </div>
  )

  const { kpis, fases, comparativo, semanal, semana_ant } = dados

  // Encontra desvio de cada fase para os fatos geradores
  const desvioFase = Object.fromEntries((fases || []).map(f => [f.fase, f.desvio]))

  // Linha do semana atual na tabela semanal
  const semAtualRow = semanal.find(x => x.semana === semanaCode)
  const prevSem = semAtualRow?.prev  null
  const realSem = semAtualRow?.real  null
  const desvioAbsSem = prevSem != null && realSem != null  realSem - prevSem : null
  const desvioRelSem = desvioAbsSem != null && prevSem  (desvioAbsSem / prevSem) * 100 : null
  const desvioRelAc  = kpis.desvio_ac != null && kpis.linha_base  (kpis.desvio_ac / kpis.linha_base) * 100 : null

  return (
    <div style={{ background: '#f8f9fb', minHeight: '100vh' }}>
      <div style={{ padding: '16px 20px' }}>

        {/* ── Título + Upload XER ── */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#063057', letterSpacing: 0.5 }}>
                PAINEL EXECUTIVO — AVANÇO FÍSICO
              </div>
              <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                {semanaCode} · Período encerrado em {semAtualRow?.nome || '—'}
              </div>
            </div>
            <button
              onClick={handleRecalcular}
              disabled={recalcLoading}
              title="Recalcular com os dados do último XER importado"
              style={{ marginLeft: 'auto', background: 'transparent', color: '#063057', border: '1px solid #063057', borderRadius: 6, padding: '6px 14px', fontSize: 11, cursor: 'pointer', opacity: recalcLoading  0.6 : 1 }}
            >
              {recalcLoading  '⟳ Recalculando...' : '⟳ Recalcular'}
            </button>
          </div>

          {/* Área de upload XER */}
          <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 18 }}>📂</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#063057' }}>Importar XER do Avanço Físico</div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>
                Suba o cronograma P6 (.xer) — os dados do painel serão atualizados automaticamente
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xer"
              onChange={handleUploadXer}
              style={{ display: 'none' }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadLoading}
              style={{
                background: '#063057', color: 'white', border: 'none', borderRadius: 6,
                padding: '8px 20px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                opacity: uploadLoading  0.6 : 1, whiteSpace: 'nowrap',
              }}
            >
              {uploadLoading  '⏳ Importando...' : '⬆ Selecionar XER'}
            </button>
            {uploadMsg && (
              <span style={{
                fontSize: 11, padding: '4px 10px', borderRadius: 5,
                background: uploadMsg.tipo === 'ok'  '#dcfce7' : '#fee2e2',
                color: uploadMsg.tipo === 'ok'  '#166534' : '#991b1b',
              }}>
                {uploadMsg.texto}
              </span>
            )}
          </div>
        </div>

        {/* ── KPIs ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 16 }}>
          <KpiCard label="Linha de Base Acumulada" value={fmt(kpis.linha_base)} color="#063057" />
          <KpiCard label={`Previsto Semana (${semAtualRow?.nome || '—'})`} value={fmt(prevSem)} color="#2f75b5" />
          <KpiCard label="Real Acumulado" value={fmt(kpis.real_ac)} color="#70ad47" />
          <KpiCard
            label="Desvio Acumulado"
            value={fmtDesvio(kpis.desvio_ac)}
            color={kpis.desvio_ac != null  desvioColor(kpis.desvio_ac) : '#374151'}
          />
        </div>

        {/* ── Curva S Geral ── */}
        <div style={{ ...cardStyle, marginBottom: 16 }}>
          <SectionHeader>CURVA S GERAL — AVANÇO MENSAL</SectionHeader>
          <div style={{ height: 320 }}>
            <canvas ref={geralCanvasRef} />
          </div>
        </div>

        {/* ── Segunda linha: semanal | fases | comparativo ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px 280px', gap: 12, marginBottom: 16 }}>

          {/* Curva S Semanal + tabela */}
          <div style={cardStyle}>
            <SectionHeader>CURVA S SEMANAL</SectionHeader>
            <div style={{ height: 220 }}>
              <canvas ref={semanalCanvasRef} />
            </div>
            <div style={{ marginTop: 12, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr>
                    {['Semana','Prev.Sem','Real Sem','Prev.Ac.','Real Ac.'].map(h => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {semanal.map(d => {
                    const isAtual = d.semana === semanaCode
                    return (
                      <tr key={d.semana} style={{ background: isAtual  '#fffbeb' : 'white' }}>
                        <td style={{ ...tdStyle, fontWeight: isAtual  700 : 400, color: isAtual  '#f59e0b' : '#1f2f44' }}>
                          {d.nome}
                        </td>
                        <td style={tdStyle}>{fmt(d.prev)}</td>
                        <td style={tdStyle}>{fmt(d.real)}</td>
                        <td style={tdStyle}>{fmt(d.prevAc)}</td>
                        <td style={tdStyle}>{fmt(d.realAc)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {/* Desvio semanal */}
            <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div style={{ border: '1px solid #e2e8f0', background: 'white', padding: '8px 12px', fontSize: 11, color: '#1f2f44' }}>
                <div>
                  <span style={{ fontWeight: 700 }}>Desvio Absoluto:</span>{' '}
                  <span style={{ fontWeight: 800, color: desvioAbsSem != null && desvioAbsSem < 0  '#dc2626' : '#16a34a' }}>
                    {desvioAbsSem != null  fmtDesvio(desvioAbsSem) : '—'}
                  </span>
                </div>
                <div style={{ marginTop: 4 }}>
                  <span style={{ fontWeight: 700 }}>Desvio Relativo:</span>{' '}
                  <span style={{ fontWeight: 800, color: desvioRelSem != null && desvioRelSem < 0  '#dc2626' : '#16a34a' }}>
                    {desvioRelSem != null  `${desvioRelSem >= 0  '+' : ''}${desvioRelSem.toFixed(2).replace('.', ',')}%` : '—'}
                  </span>
                </div>
              </div>
              <div style={{ border: '1px solid #e2e8f0', background: 'white', padding: '8px 12px', fontSize: 11, color: '#1f2f44' }}>
                <div><span style={{ fontWeight: 700 }}>Notas:</span> Curva física conforme cronograma LB 0.</div>
                <div style={{ marginTop: 4 }}>Semana contratual: <span style={{ fontWeight: 700 }}>{semanaCode}</span></div>
              </div>
            </div>
          </div>

          {/* Avanço por Fase */}
          <div style={cardStyle}>
            <SectionHeader>AVANÇO POR FASE</SectionHeader>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: 'left' }}>Fase</th>
                  <th style={thStyle}>Prev.</th>
                  <th style={thStyle}>Real</th>
                  <th style={thStyle}>Desvio</th>
                </tr>
              </thead>
              <tbody>
                {fases.map(f => (
                  <tr key={f.fase} style={{ background: f.total  '#eef5e8' : 'white' }}>
                    <td style={{ ...tdStyle, textAlign: 'left', fontWeight: f.total  700 : 400, fontSize: 10 }}>{f.fase}</td>
                    <td style={{ ...tdStyle, fontWeight: f.total  700 : 400 }}>{fmt(f.prev)}</td>
                    <td style={{ ...tdStyle, fontWeight: f.total  700 : 400 }}>{fmt(f.real)}</td>
                    <td style={{ ...tdStyle, fontWeight: f.total  700 : 400, color: f.desvio != null  desvioColor(f.desvio) : '#374151' }}>
                      {fmtDesvio(f.desvio)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ border: '1px solid #e2e8f0', padding: '6px 10px', fontSize: 11 }}>
                <span style={{ fontWeight: 700 }}>Desvio absoluto acumulado:</span>{' '}
                <span style={{ fontWeight: 800, color: kpis.desvio_ac != null && kpis.desvio_ac < 0  '#dc2626' : '#16a34a' }}>
                  {fmtDesvio(kpis.desvio_ac)}
                </span>
              </div>
              <div style={{ border: '1px solid #e2e8f0', padding: '6px 10px', fontSize: 11 }}>
                <span style={{ fontWeight: 700 }}>Desvio relativo acumulado:</span>{' '}
                <span style={{ fontWeight: 800, color: desvioRelAc != null && desvioRelAc < 0  '#dc2626' : '#16a34a' }}>
                  {desvioRelAc != null  `${desvioRelAc >= 0  '+' : ''}${desvioRelAc.toFixed(2).replace('.', ',')}%` : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Comparativo de Desvio */}
          <div style={cardStyle}>
            <SectionHeader>COMPARATIVO DE DESVIO</SectionHeader>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: 'left' }}>Fase</th>
                  <th style={thStyle}>{semana_ant || 'Sem. Ant.'}</th>
                  <th style={thStyle}>{semanaCode}</th>
                </tr>
              </thead>
              <tbody>
                {comparativo.map(f => (
                  <tr key={f.fase} style={{ background: f.total  '#eef5e8' : 'white' }}>
                    <td style={{ ...tdStyle, textAlign: 'left', fontWeight: f.total  700 : 400, fontSize: 10 }}>{f.fase}</td>
                    <td style={{ ...tdStyle, fontWeight: f.total  700 : 400, color: f.s_ant != null  desvioColor(f.s_ant) : '#374151' }}>
                      {fmtDesvio(f.s_ant)}
                    </td>
                    <td style={{ ...tdStyle, fontWeight: f.total  700 : 400, color: f.s_at != null  desvioColor(f.s_at) : '#374151' }}>
                      {fmtDesvio(f.s_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Página 2 — Fatos Geradores ── */}
        <div style={{ borderTop: '3px solid #063057', margin: '24px 0 16px', paddingTop: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#063057', letterSpacing: 1 }}>
            2.3 — DESVIOS E FATOS GERADORES
          </span>
        </div>

        {FATOS.map(bloco => {
          const desvio = desvioFase[bloco.desvio_ref]  null
          return (
            <div
              key={bloco.fase}
              style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', border: '1px solid #e2e8f0', borderRadius: 6, marginBottom: 10, overflow: 'hidden' }}
            >
              <div style={{ borderRight: '1px solid #e2e8f0', padding: 16, background: 'white' }}>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10, color: '#063057' }}>
                  {bloco.fase}{' '}
                  {desvio != null && (
                    <span style={{ color: desvioColor(desvio) }}>({fmtDesvio(desvio)})</span>
                  )}
                </div>
                <ul style={{ paddingLeft: 18, lineHeight: 1.8, margin: 0 }}>
                  {bloco.itens.map((it, i) => (
                    <li key={i} style={{ fontSize: 12, color: '#374151' }}>{it}</li>
                  ))}
                </ul>
              </div>
              <div style={{ padding: 16, background: '#fafafa' }}>
                <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 8, borderBottom: '1px solid #e2e8f0', paddingBottom: 6, color: '#063057', letterSpacing: 0.5 }}>
                  FATOS GERADORES
                </div>
                <p style={{ fontSize: 12, lineHeight: 1.8, whiteSpace: 'pre-line', color: '#374151', margin: 0 }}>
                  {bloco.fatos}
                </p>
              </div>
            </div>
          )
        })}

      </div>
    </div>
  )
}

// ── Sub-componentes auxiliares ────────────────────────────────────────────────

function KpiCard({ label, value, color }) {
  return (
    <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 6, padding: '12px 16px', textAlign: 'center' }}>
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>
        {value}
      </div>
    </div>
  )
}

function SectionHeader({ children }) {
  return (
    <div style={{ background: '#063057', color: 'white', padding: '7px 12px', fontSize: 12, fontWeight: 700, borderRadius: '4px 4px 0 0', marginBottom: 10, letterSpacing: 0.3 }}>
      {children}
    </div>
  )
}
