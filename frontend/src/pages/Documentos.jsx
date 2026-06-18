/**
 * Fase 3 — Lista de Documentos de Engenharia
 * Gerencia a LD (Lista de Documentos) e calcula automaticamente
 * o % de avanço do item EAP 2.1.1 — Documentação Técnica.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  getDocumentos, criarDocumento, atualizarDocumento,
  alterarStatusDocumento, deletarDocumento,
  getProgresso211, importarDocumentosExcel,
} from '../api'

// ── constantes ──────────────────────────────────────────────────────
const STATUS_INFO = {
  EM_ELABORACAO:   { label: 'Em Elaboração',   cor: '#6b7280', bg: '#f3f4f6', fator: 0   },
  EM_ANALISE:      { label: 'Em Análise',      cor: '#1d4ed8', bg: '#dbeafe', fator: 0.6 },
  COM_COMENTARIOS: { label: 'Com Comentários', cor: '#b45309', bg: '#fef3c7', fator: 0.6 },
  SEM_COMENTARIOS: { label: 'Sem Comentários', cor: '#047857', bg: '#d1fae5', fator: 1.0 },
  APROVADO:        { label: 'Aprovado',        cor: '#065f46', bg: '#a7f3d0', fator: 1.0 },
}
const STATUS_ORDEM = Object.keys(STATUS_INFO)
const DISCIPLINAS = ['Civil', 'Mecânico', 'Elétrico', 'Instrumentação', 'Processo', 'Tubulação', 'Estrutural', 'Outros']
const TIPOS_DOC = ['Memorial de Cálculo', 'Desenho', 'Especificação', 'Folha de Dados', 'Diagrama', 'Planta', 'Relatório', 'Outros']

const DOC_VAZIO = {
  codigo: '', titulo: '', disciplina: '', tipo_doc: '',
  revisao_atual: '0', status: 'EM_ELABORACAO',
  emitido_em: '', aprovado_em: '', peso: 1, observacao: '',
}

function fmtData(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('T')[0].split('-')
  return `${d}/${m}/${y}`
}

export default function Documentos() {
  const [docs, setDocs]           = useState([])
  const [progresso, setProgresso] = useState(null)
  const [loading, setLoading]     = useState(false)
  const [erro, setErro]           = useState('')

  // filtros
  const [filtroDisciplina, setFiltroDisciplina] = useState('')
  const [filtroStatus, setFiltroStatus]         = useState('')
  const [filtroQ, setFiltroQ]                   = useState('')

  // modal add/edit
  const [modalAberto, setModalAberto]   = useState(false)
  const [editando, setEditando]         = useState(null)   // null = novo
  const [form, setForm]                 = useState(DOC_VAZIO)
  const [salvando, setSalvando]         = useState(false)

  // modal import
  const [importAberto, setImportAberto] = useState(false)
  const fileRef = useRef()

  // dropdown de status inline
  const [dropdownId, setDropdownId]     = useState(null)

  const carregar = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (filtroDisciplina) params.disciplina = filtroDisciplina
      if (filtroStatus)     params.status = filtroStatus
      if (filtroQ)          params.q = filtroQ
      const [d, p] = await Promise.all([getDocumentos(params), getProgresso211()])
      setDocs(d)
      setProgresso(p)
    } catch {
      setErro('Erro ao carregar documentos.')
    } finally {
      setLoading(false)
    }
  }, [filtroDisciplina, filtroStatus, filtroQ])

  useEffect(() => { carregar() }, [carregar])

  // ── ações ─────────────────────────────────────────────────────────
  function abrirNovo() {
    setEditando(null)
    setForm(DOC_VAZIO)
    setModalAberto(true)
  }

  function abrirEditar(doc) {
    setEditando(doc)
    setForm({
      codigo: doc.codigo,
      titulo: doc.titulo,
      disciplina: doc.disciplina || '',
      tipo_doc: doc.tipo_doc || '',
      revisao_atual: doc.revisao_atual || '',
      status: doc.status,
      emitido_em: doc.emitido_em  doc.emitido_em.split('T')[0] : '',
      aprovado_em: doc.aprovado_em  doc.aprovado_em.split('T')[0] : '',
      peso: doc.peso,
      observacao: doc.observacao || '',
    })
    setModalAberto(true)
  }

  async function salvarForm() {
    if (!form.codigo.trim() || !form.titulo.trim()) {
      alert('Código e Título são obrigatórios.')
      return
    }
    setSalvando(true)
    try {
      const payload = {
        ...form,
        peso: parseFloat(form.peso) || 1,
        emitido_em: form.emitido_em || null,
        aprovado_em: form.aprovado_em || null,
        disciplina: form.disciplina || null,
        tipo_doc: form.tipo_doc || null,
        revisao_atual: form.revisao_atual || null,
        observacao: form.observacao || null,
      }
      if (editando) {
        await atualizarDocumento(editando.id, payload)
      } else {
        await criarDocumento(payload)
      }
      setModalAberto(false)
      await carregar()
    } catch (e) {
      alert(e?.response?.data?.detail || 'Erro ao salvar.')
    } finally {
      setSalvando(false)
    }
  }

  async function excluir(doc) {
    if (!window.confirm(`Excluir "${doc.codigo} — ${doc.titulo}"?`)) return
    await deletarDocumento(doc.id)
    await carregar()
  }

  async function mudarStatus(doc, novoStatus) {
    setDropdownId(null)
    await alterarStatusDocumento(doc.id, novoStatus)
    await carregar()
  }

  async function handleImport(e) {
    const file = e.target.files[0]
    if (!file) return
    const fd = new FormData()
    fd.append('arquivo', file)
    try {
      const r = await importarDocumentosExcel(fd)
      alert(`Importado: ${r.inseridos} inseridos, ${r.atualizados} atualizados.\n${r.erros.length  'Erros:\n' + r.erros.join('\n') : ''}`)
      setImportAberto(false)
      await carregar()
    } catch (ex) {
      alert(ex?.response?.data?.detail || 'Erro na importação.')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  // ── render ────────────────────────────────────────────────────────
  const pct = progresso?.pct  0
  const barColor = pct >= 0.8  '#059669' : pct >= 0.5  '#d97706' : '#1d4ed8'

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1400, margin: '0 auto' }}>

      {/* Cabeçalho */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, color: '#063057', fontWeight: 700 }}>📄 Lista de Documentos</h1>
          <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: 13 }}>
            Engenharia de Detalhamento · EAP 2.1.1 — Documentação Técnica
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => setImportAberto(true)} style={btnSecondary}>
            📥 Importar Excel
          </button>
          <button onClick={abrirNovo} style={btnPrimary}>
            + Novo Documento
          </button>
        </div>
      </div>

      {/* Cards de progresso */}
      {progresso && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
          <CardStat label="Total" valor={progresso.total_docs} cor="#374151" />
          <CardStat label="Em Elaboração" valor={progresso.em_elaboracao} cor={STATUS_INFO.EM_ELABORACAO.cor} />
          <CardStat label="Em Análise" valor={progresso.em_analise} cor={STATUS_INFO.EM_ANALISE.cor} />
          <CardStat label="Com Comentários" valor={progresso.com_comentarios} cor={STATUS_INFO.COM_COMENTARIOS.cor} />
          <CardStat label="Sem Comentários" valor={progresso.sem_comentarios} cor={STATUS_INFO.SEM_COMENTARIOS.cor} />
          <CardStat label="Aprovados" valor={progresso.aprovados} cor={STATUS_INFO.APROVADO.cor} />
        </div>
      )}

      {/* Barra de progresso 2.1.1 */}
      {progresso && (
        <div style={{ background: 'white', borderRadius: 10, padding: '16px 20px', marginBottom: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontWeight: 600, color: '#063057', fontSize: 14 }}>
              Avanço EAP 2.1.1 — Documentação Técnica
            </span>
            <span style={{ fontWeight: 700, fontSize: 18, color: barColor }}>
              {(pct * 100).toFixed(1)}%
            </span>
          </div>
          <div style={{ height: 12, background: '#e5e7eb', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct * 100}%`, background: barColor, borderRadius: 6, transition: 'width 0.4s' }} />
          </div>
          <div style={{ marginTop: 6, fontSize: 11, color: '#6b7280' }}>
            Emissão = 60% · Aprovação = 40% adicional · Peso total: {progresso.peso_total.toFixed(1)}
          </div>
        </div>
      )}

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          placeholder="🔍  Buscar código ou título…"
          value={filtroQ}
          onChange={e => setFiltroQ(e.target.value)}
          style={{ ...inputStyle, flex: 1, minWidth: 200 }}
        />
        <select value={filtroDisciplina} onChange={e => setFiltroDisciplina(e.target.value)} style={inputStyle}>
          <option value="">Todas disciplinas</option>
          {DISCIPLINAS.map(d => <option key={d}>{d}</option>)}
        </select>
        <select value={filtroStatus} onChange={e => setFiltroStatus(e.target.value)} style={inputStyle}>
          <option value="">Todos status</option>
          {STATUS_ORDEM.map(s => <option key={s} value={s}>{STATUS_INFO[s].label}</option>)}
        </select>
        <button onClick={carregar} style={{ ...btnSecondary, padding: '8px 14px' }}>↺</button>
      </div>

      {/* Tabela */}
      {erro && <div style={{ color: '#dc2626', marginBottom: 12 }}>{erro}</div>}
      {loading  (
        <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Carregando…</div>
      ) : (
        <div style={{ background: 'white', borderRadius: 10, boxShadow: '0 1px 4px rgba(0,0,0,0.08)', overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e5e7eb' }}>
                {['Código', 'Título', 'Disciplina', 'Tipo', 'Rev.', 'Peso', 'Status', 'Emitido', 'Aprovado', ''].map(h => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {docs.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>
                    Nenhum documento cadastrado.
                  </td>
                </tr>
              )}
              {docs.map(doc => (
                <tr key={doc.id} style={{ borderBottom: '1px solid #f0f0f0' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                  onMouseLeave={e => e.currentTarget.style.background = 'white'}
                >
                  <td style={{ padding: '9px 12px', fontFamily: 'monospace', fontSize: 12, color: '#374151', whiteSpace: 'nowrap' }}>{doc.codigo}</td>
                  <td style={{ padding: '9px 12px', maxWidth: 280 }}>
                    <div style={{ fontWeight: 500, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {doc.titulo}
                    </div>
                    {doc.observacao && (
                      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{doc.observacao}</div>
                    )}
                  </td>
                  <td style={{ padding: '9px 12px', color: '#6b7280' }}>{doc.disciplina || '—'}</td>
                  <td style={{ padding: '9px 12px', color: '#6b7280', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.tipo_doc || '—'}</td>
                  <td style={{ padding: '9px 12px', textAlign: 'center', color: '#374151', fontWeight: 600 }}>{doc.revisao_atual || '—'}</td>
                  <td style={{ padding: '9px 12px', textAlign: 'center', color: '#6b7280' }}>{doc.peso}</td>
                  <td style={{ padding: '9px 12px', position: 'relative' }}>
                    <button
                      onClick={() => setDropdownId(dropdownId === doc.id  null : doc.id)}
                      style={{
                        background: STATUS_INFO[doc.status]?.bg || '#f3f4f6',
                        color: STATUS_INFO[doc.status]?.cor || '#374151',
                        border: 'none', borderRadius: 12, padding: '3px 10px',
                        fontSize: 11, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
                      }}
                    >
                      {STATUS_INFO[doc.status]?.label || doc.status} ▾
                    </button>
                    {dropdownId === doc.id && (
                      <div style={{
                        position: 'absolute', top: '100%', left: 0, zIndex: 100,
                        background: 'white', borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                        padding: 6, minWidth: 180,
                      }}>
                        {STATUS_ORDEM.map(s => (
                          <button
                            key={s}
                            onClick={() => mudarStatus(doc, s)}
                            style={{
                              display: 'block', width: '100%', textAlign: 'left',
                              padding: '7px 12px', border: 'none', background: s === doc.status  '#f0f4ff' : 'white',
                              cursor: 'pointer', fontSize: 12, borderRadius: 5,
                              color: STATUS_INFO[s].cor, fontWeight: s === doc.status  700 : 400,
                            }}
                          >
                            {s === doc.status  '✓ ' : ''}{STATUS_INFO[s].label}
                          </button>
                        ))}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '9px 12px', color: '#6b7280', whiteSpace: 'nowrap' }}>{fmtData(doc.emitido_em)}</td>
                  <td style={{ padding: '9px 12px', color: '#6b7280', whiteSpace: 'nowrap' }}>{fmtData(doc.aprovado_em)}</td>
                  <td style={{ padding: '9px 12px', whiteSpace: 'nowrap' }}>
                    <button onClick={() => abrirEditar(doc)} style={btnIcone} title="Editar">✏️</button>
                    <button onClick={() => excluir(doc)} style={{ ...btnIcone, marginLeft: 4 }} title="Excluir">🗑️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modal Add/Edit ─────────────────────────────────────────── */}
      {modalAberto && (
        <div style={overlay} onClick={e => e.target === e.currentTarget && setModalAberto(false)}>
          <div style={{ ...modal, width: 560 }}>
            <h3 style={{ margin: '0 0 18px', color: '#063057' }}>
              {editando  '✏️ Editar Documento' : '+ Novo Documento'}
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <LabelInput label="Código *" col="1 / 3">
                <input value={form.codigo} disabled={!!editando}
                  onChange={e => setForm(f => ({ ...f, codigo: e.target.value }))} style={inputStyle} />
              </LabelInput>
              <LabelInput label="Título *" col="1 / 3">
                <input value={form.titulo}
                  onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))} style={inputStyle} />
              </LabelInput>
              <LabelInput label="Disciplina">
                <select value={form.disciplina} onChange={e => setForm(f => ({ ...f, disciplina: e.target.value }))} style={inputStyle}>
                  <option value="">Selecione…</option>
                  {DISCIPLINAS.map(d => <option key={d}>{d}</option>)}
                </select>
              </LabelInput>
              <LabelInput label="Tipo de Documento">
                <select value={form.tipo_doc} onChange={e => setForm(f => ({ ...f, tipo_doc: e.target.value }))} style={inputStyle}>
                  <option value="">Selecione…</option>
                  {TIPOS_DOC.map(t => <option key={t}>{t}</option>)}
                </select>
              </LabelInput>
              <LabelInput label="Revisão Atual">
                <input value={form.revisao_atual}
                  onChange={e => setForm(f => ({ ...f, revisao_atual: e.target.value }))} style={inputStyle} placeholder="0" />
              </LabelInput>
              <LabelInput label="Status">
                <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} style={inputStyle}>
                  {STATUS_ORDEM.map(s => <option key={s} value={s}>{STATUS_INFO[s].label}</option>)}
                </select>
              </LabelInput>
              <LabelInput label="Data Emissão">
                <input type="date" value={form.emitido_em}
                  onChange={e => setForm(f => ({ ...f, emitido_em: e.target.value }))} style={inputStyle} />
              </LabelInput>
              <LabelInput label="Data Aprovação">
                <input type="date" value={form.aprovado_em}
                  onChange={e => setForm(f => ({ ...f, aprovado_em: e.target.value }))} style={inputStyle} />
              </LabelInput>
              <LabelInput label="Peso">
                <input type="number" min={0.1} step={0.1} value={form.peso}
                  onChange={e => setForm(f => ({ ...f, peso: e.target.value }))} style={inputStyle} />
              </LabelInput>
              <LabelInput label="Observação" col="1 / 3">
                <input value={form.observacao}
                  onChange={e => setForm(f => ({ ...f, observacao: e.target.value }))} style={inputStyle} placeholder="Opcional…" />
              </LabelInput>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
              <button onClick={() => setModalAberto(false)} style={btnSecondary}>Cancelar</button>
              <button onClick={salvarForm} disabled={salvando} style={btnPrimary}>
                {salvando  'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Importar Excel ───────────────────────────────────── */}
      {importAberto && (
        <div style={overlay} onClick={e => e.target === e.currentTarget && setImportAberto(false)}>
          <div style={{ ...modal, width: 480 }}>
            <h3 style={{ margin: '0 0 12px', color: '#063057' }}>📥 Importar Documentos via Excel</h3>
            <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 16 }}>
              A planilha deve ter as colunas (linha 1 = cabeçalho):
            </p>
            <table style={{ fontSize: 12, borderCollapse: 'collapse', width: '100%', marginBottom: 16 }}>
              <thead>
                <tr style={{ background: '#f0f4ff' }}>
                  <th style={thStyle}>Coluna</th>
                  <th style={thStyle}>Obrigatória?</th>
                  <th style={thStyle}>Descrição</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['codigo', '✓', 'Código único do documento'],
                  ['titulo', '✓', 'Título / descrição'],
                  ['disciplina', '', 'Civil, Mecânico, etc.'],
                  ['tipo_doc', '', 'Memorial, Desenho, etc.'],
                  ['revisao_atual', '', 'Ex: 0, 1, A'],
                  ['status', '', 'EM_ELABORACAO, EM_ANALISE…'],
                  ['emitido_em', '', 'dd/mm/aaaa'],
                  ['aprovado_em', '', 'dd/mm/aaaa'],
                  ['peso', '', 'Número (padrão 1)'],
                  ['observacao', '', 'Texto livre'],
                ].map(([c, o, d]) => (
                  <tr key={c} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', color: '#1d4ed8' }}>{c}</td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>{o}</td>
                    <td style={{ ...tdStyle, color: '#6b7280' }}>{d}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={{ fontSize: 12, color: '#9ca3af', marginBottom: 12 }}>
              Documentos com o mesmo código serão atualizados; novos serão inseridos.
            </p>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" onChange={handleImport} style={{ display: 'none' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button onClick={() => setImportAberto(false)} style={btnSecondary}>Cancelar</button>
              <button onClick={() => fileRef.current?.click()} style={btnPrimary}>Selecionar Arquivo…</button>
            </div>
          </div>
        </div>
      )}

      {/* Fechar dropdown ao clicar fora */}
      {dropdownId !== null && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 99 }}
          onClick={() => setDropdownId(null)} />
      )}
    </div>
  )
}

// ── sub-components ───────────────────────────────────────────────────
function CardStat({ label, valor, cor }) {
  return (
    <div style={{
      background: 'white', borderRadius: 8, padding: '14px 16px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.07)', borderLeft: `4px solid ${cor}`,
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: cor }}>{valor}</div>
      <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function LabelInput({ label, children, col }) {
  return (
    <div style={{ gridColumn: col, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, color: '#374151', fontWeight: 600 }}>{label}</label>
      {children}
    </div>
  )
}

// ── estilos ─────────────────────────────────────────────────────────
const inputStyle = {
  padding: '8px 10px', borderRadius: 6, border: '1px solid #d1d5db',
  fontSize: 13, width: '100%', boxSizing: 'border-box',
  outline: 'none', color: '#111827',
}
const btnPrimary = {
  background: '#1d4ed8', color: 'white', border: 'none', borderRadius: 7,
  padding: '9px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
}
const btnSecondary = {
  background: 'white', color: '#374151', border: '1px solid #d1d5db',
  borderRadius: 7, padding: '9px 18px', fontSize: 13, fontWeight: 500, cursor: 'pointer',
}
const btnIcone = {
  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', fontSize: 15,
}
const overlay = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
  zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
}
const modal = {
  background: 'white', borderRadius: 12, padding: 28,
  boxShadow: '0 20px 60px rgba(0,0,0,0.25)', maxHeight: '90vh', overflowY: 'auto',
}
const thStyle = { padding: '7px 10px', textAlign: 'left', fontWeight: 600, color: '#374151', fontSize: 12 }
const tdStyle = { padding: '6px 10px', fontSize: 12 }
