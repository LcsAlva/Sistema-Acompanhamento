import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getFotosMedicao,
  uploadFotoMedicao,
  atualizarLegendaFoto,
  deletarFotoMedicao,
  fotoUrl,
  getEapItens,
} from '../api'

const MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

export default function RelatorioFotografico() {
  const params = useParams()
  const navigate = useNavigate()
  const hoje = new Date()
  const [ano, setAno] = useState(params.ano  parseInt(params.ano) : hoje.getFullYear())
  const [mes, setMes] = useState(params.mes  parseInt(params.mes) : hoje.getMonth() + 1)

  const [fotos, setFotos] = useState([])
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)
  const [showUpload, setShowUpload] = useState(false)

  const carregar = useCallback(async (a, m) => {
    setLoading(true)
    setErro(null)
    try {
      const data = await getFotosMedicao(a, m)
      setFotos(data || [])
    } catch (e) {
      setErro('Erro ao carregar fotos: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    carregar(ano, mes)
    navigate(`/relatorio-fotografico/${ano}/${mes}`, { replace: true })
  }, [ano, mes, carregar, navigate])

  function navMes(delta) {
    let nm = mes + delta
    let na = ano
    if (nm < 1) { nm = 12; na-- }
    if (nm > 12) { nm = 1; na++ }
    setAno(na)
    setMes(nm)
  }

  // Agrupa fotos por eap_codigo preservando ordem
  const grupos = useMemo(() => {
    const map = new Map()
    for (const f of fotos) {
      if (!map.has(f.eap_codigo)) {
        map.set(f.eap_codigo, { codigo: f.eap_codigo, descricao: f.eap_descricao || '', fotos: [] })
      }
      map.get(f.eap_codigo).fotos.push(f)
    }
    return Array.from(map.values())
  }, [fotos])

  async function handleEditLegenda(foto) {
    const nova = prompt('Editar legenda da Foto ' + (foto.numero || ''), foto.legenda || '')
    if (nova === null) return
    try {
      await atualizarLegendaFoto(ano, mes, foto.id, nova)
      carregar(ano, mes)
    } catch (e) {
      alert('Erro ao atualizar legenda: ' + (e?.response?.data?.detail || e.message))
    }
  }

  async function handleDelete(foto) {
    if (!confirm(`Excluir Foto ${foto.numero || ''}?`)) return
    try {
      await deletarFotoMedicao(ano, mes, foto.id)
      carregar(ano, mes)
    } catch (e) {
      alert('Erro ao excluir: ' + (e?.response?.data?.detail || e.message))
    }
  }

  return (
    <div style={{ background: '#F2F2F0', minHeight: '100vh', padding: '24px 28px' }} className="rf-root">
      <style>{`
        @media print {
          .rf-noprint { display: none !important; }
          .rf-root { background: white !important; padding: 0 !important; }
          .rf-card { box-shadow: none !important; border: none !important; }
          .rf-photo-actions { display: none !important; }
          aside, nav, .sidebar { display: none !important; }
        }
        .rf-photo-cell:hover .rf-photo-actions { opacity: 1; }
      `}</style>

      {/* Cabeçalho */}
      <div className="rf-card rf-noprint" style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <button onClick={() => navMes(-1)} style={navBtnStyle}>◀</button>
          <div style={{ textAlign: 'center', minWidth: 220 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#063057' }}>
              Relatório Fotográfico — {MESES_PT[mes]} / {ano}
            </div>
            <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
              {fotos.length} foto{fotos.length === 1  '' : 's'} · {grupos.length} item{grupos.length === 1  '' : 's'} EAP
            </div>
          </div>
          <button onClick={() => navMes(1)} style={navBtnStyle}>▶</button>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            <button onClick={() => setShowUpload(true)} style={btnStyle('#2563eb')}>📷 Adicionar Foto</button>
            <button onClick={() => window.print()} style={btnStyle('#063057')}>🖨️ Imprimir</button>
          </div>
        </div>
      </div>

      {/* Cabeçalho de impressão (visível só na impressão) */}
      <div className="rf-print-header" style={{ display: 'none' }}>
        <h1 style={{ color: '#063057', textAlign: 'center', margin: '0 0 16px' }}>
          Relatório Fotográfico — {MESES_PT[mes]} / {ano}
        </h1>
      </div>

      {erro && (
        <div className="rf-noprint" style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 8, padding: '12px 16px', color: '#b91c1c', marginBottom: 16 }}>
          {erro}
        </div>
      )}

      {loading && (
        <div className="rf-noprint" style={{ textAlign: 'center', padding: 40, color: '#888' }}>Carregando...</div>
      )}

      {!loading && fotos.length === 0 && (
        <div className="rf-noprint" style={{ ...cardStyle, textAlign: 'center', color: '#888', padding: 40 }}>
          Nenhuma foto cadastrada para este mês. Clique em "Adicionar Foto" para começar.
        </div>
      )}

      {grupos.map(g => (
        <div key={g.codigo} className="rf-card" style={{ ...cardStyle, pageBreakInside: 'avoid' }}>
          <div style={{
            background: '#063057', color: '#fff', padding: '10px 14px',
            borderRadius: 8, marginBottom: 14, fontWeight: 600, fontSize: 14,
          }}>
            {g.codigo} — {g.descricao}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
            {g.fotos.map(f => (
              <div key={f.id} className="rf-photo-cell" style={{ position: 'relative' }}>
                <img
                  src={fotoUrl(f)}
                  alt={f.legenda || `Foto ${f.numero}`}
                  style={{
                    width: '100%', height: 'auto', display: 'block',
                    borderRadius: 6, border: '1px solid #d1d5db',
                  }}
                />
                <div style={{ marginTop: 6, fontSize: 12, color: '#1a1a1a' }}>
                  <strong>Foto {f.numero}:</strong> {f.legenda || <em style={{ color: '#888' }}>sem legenda</em>}
                </div>
                <div className="rf-photo-actions" style={{
                  position: 'absolute', top: 6, right: 6, display: 'flex', gap: 4,
                  opacity: 0, transition: 'opacity 0.15s',
                }}>
                  <button
                    onClick={() => handleEditLegenda(f)}
                    title="Editar legenda"
                    style={iconBtnStyle}
                  >✏️</button>
                  <button
                    onClick={() => handleDelete(f)}
                    title="Excluir"
                    style={iconBtnStyle}
                  >🗑️</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {showUpload && (
        <UploadFotoModal
          ano={ano}
          mes={mes}
          onClose={() => setShowUpload(false)}
          onUploaded={() => { setShowUpload(false); carregar(ano, mes) }}
        />
      )}
    </div>
  )
}


// Cores WBS progressivas (mesmas do restante do sistema)
const WBS_BG = ['#063057', '#0A4778', '#1260A0', '#1A79C8', '#2E86C1', '#5DADE2']
const WBS_FW = [700, 700, 600, 600, 500, 400]

function UploadFotoModal({ ano, mes, onClose, onUploaded }) {
  const [allItens, setAllItens]   = useState([])
  const [busca, setBusca]         = useState('')
  const [eapSelecionado, setEapSelecionado] = useState(null)
  const [legenda, setLegenda]     = useState('')
  const [file, setFile]           = useState(null)
  const [enviando, setEnviando]   = useState(false)
  const [erro, setErro]           = useState(null)
  const [loadingItens, setLoadingItens] = useState(true)
  const [collapsed, setCollapsed] = useState({}) // { codigo: bool }

  const monthKey = `${ano}-${String(mes).padStart(2, '0')}-01`

  useEffect(() => {
    getEapItens({ limit: 2000 })
      .then(data => {
        const sorted = [...(data || [])].sort((a, b) =>
          a.codigo.localeCompare(b.codigo, undefined, { numeric: true })
        )
        setAllItens(sorted)
      })
      .catch(() => setAllItens([]))
      .finally(() => setLoadingItens(false))
  }, [])

  // Conjunto de códigos que são pais (têm filhos)
  const parentSet = useMemo(() => {
    const s = new Set()
    allItens.forEach(it => { if (it.parent_codigo) s.add(it.parent_codigo) })
    return s
  }, [allItens])

  // Itens com distribuição no mês selecionado (folhas do mês + seus ancestrais)
  const itensDoMes = useMemo(() => {
    const comMes = new Set()
    allItens.forEach(it => {
      const dist = it.dist_mensal || {}
      if (!parentSet.has(it.codigo) && (dist[monthKey] || 0) > 0) {
        comMes.add(it.codigo)
        // adiciona todos os ancestrais
        let parts = it.codigo.split('.')
        while (parts.length > 1) {
          parts.pop()
          comMes.add(parts.join('.'))
        }
      }
    })
    return allItens.filter(it => comMes.has(it.codigo))
  }, [allItens, parentSet, monthKey])

  // Modo busca: filtra folhas que casam + seus ancestrais
  const itensBusca = useMemo(() => {
    if (!busca.trim()) return null
    const q = busca.toLowerCase()
    const matched = new Set()
    itensDoMes.forEach(it => {
      if (
        !parentSet.has(it.codigo) && (
          it.codigo.toLowerCase().includes(q) ||
          (it.descricao || '').toLowerCase().includes(q)
        )
      ) {
        matched.add(it.codigo)
        let parts = it.codigo.split('.')
        while (parts.length > 1) {
          parts.pop()
          matched.add(parts.join('.'))
        }
      }
    })
    return itensDoMes.filter(it => matched.has(it.codigo))
  }, [busca, itensDoMes, parentSet])

  const listaVisivelBase = itensBusca  itensDoMes

  // Verifica se algum ancestral está colapsado
  function isVisible(it) {
    if (busca.trim()) return true // na busca mostra tudo que casou
    let parts = it.codigo.split('.')
    for (let i = 1; i < parts.length; i++) {
      const ancestor = parts.slice(0, i).join('.')
      if (collapsed[ancestor]) return false
    }
    return true
  }

  function toggleCollapse(codigo) {
    setCollapsed(prev => ({ ...prev, [codigo]: !prev[codigo] }))
  }

  const folhasVisiveis = listaVisivelBase.filter(it => !parentSet.has(it.codigo)).length

  async function handleEnviar() {
    if (!eapSelecionado) { setErro('Selecione um item EAP.'); return }
    if (!file) { setErro('Selecione um arquivo de imagem.'); return }
    setEnviando(true)
    setErro(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('eap_codigo', eapSelecionado.codigo)
      fd.append('eap_descricao', eapSelecionado.descricao || '')
      if (legenda) fd.append('legenda', legenda)
      await uploadFotoMedicao(ano, mes, fd)
      onUploaded()
    } catch (e) {
      setErro('Erro ao enviar: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div style={modalOverlay}>
      <div style={{ ...modalBox, maxWidth: 620 }}>
        <h3 style={{ margin: '0 0 4px', color: '#063057', fontSize: 18 }}>Adicionar Foto</h3>
        <p style={{ margin: '0 0 14px', fontSize: 11, color: '#888' }}>
          Mostrando itens com distribuição prevista em {String(mes).padStart(2,'0')}/{ano}
        </p>

        <label style={lblStyle}>Item EAP</label>

        {eapSelecionado  (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: 6,
            padding: '8px 12px', marginBottom: 14,
          }}>
            <div style={{ fontSize: 13 }}>
              <strong style={{ color: '#063057' }}>{eapSelecionado.codigo}</strong>
              <span style={{ color: '#374151' }}> — {eapSelecionado.descricao}</span>
            </div>
            <button
              onClick={() => setEapSelecionado(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#1d4ed8', fontSize: 12, fontWeight: 600 }}
            >
              trocar
            </button>
          </div>
        ) : (
          <>
            <div style={{ position: 'relative', marginBottom: 0 }}>
              <input
                type="text"
                placeholder="🔍  Buscar por código ou descrição…"
                value={busca}
                onChange={e => setBusca(e.target.value)}
                autoFocus
                style={{ ...inputStyle, marginBottom: 0, borderRadius: '6px 6px 0 0' }}
              />
            </div>
            <div style={{
              fontSize: 10, color: '#888', padding: '3px 6px',
              background: '#f9fafb', border: '1px solid #e5e7eb', borderTop: 'none',
            }}>
              {loadingItens  'Carregando…' : `${folhasVisiveis} atividade${folhasVisiveis !== 1  's' : ''} no mês`}
              {busca && ` · filtrado por "${busca}"`}
            </div>
            <div style={{
              maxHeight: 260, overflowY: 'auto',
              border: '1px solid #e5e7eb', borderTop: 'none',
              borderRadius: '0 0 6px 6px', marginBottom: 14,
              background: '#fff',
            }}>
              {loadingItens && (
                <div style={{ padding: 14, color: '#888', fontSize: 12 }}>Carregando itens…</div>
              )}
              {!loadingItens && listaVisivelBase.length === 0 && (
                <div style={{ padding: 14, color: '#888', fontSize: 12 }}>
                  {busca  'Nenhum item encontrado para esta busca.' : 'Nenhum item com distribuição neste mês.'}
                </div>
              )}
              {!loadingItens && listaVisivelBase.map(it => {
                if (!isVisible(it)) return null
                const isPai  = parentSet.has(it.codigo)
                const nivel  = (it.nivel || it.codigo.split('.').length)
                const indent = (nivel - 1) * 14
                const bg     = isPai  WBS_BG[Math.min(nivel - 1, WBS_BG.length - 1)] : 'transparent'
                const fw     = isPai  WBS_FW[Math.min(nivel - 1, WBS_FW.length - 1)] : 400
                const clr    = isPai  '#fff' : '#1a1a1a'
                const isCollapsed = !!collapsed[it.codigo]

                // conta filhos diretos visíveis para saber se tem o que colapsar
                const hasChildren = listaVisivelBase.some(x => x.parent_codigo === it.codigo)

                return (
                  <div
                    key={it.codigo}
                    onClick={isPai
                       (hasChildren  () => toggleCollapse(it.codigo) : undefined)
                      : () => setEapSelecionado(it)
                    }
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: `5px 10px 5px ${isPai  indent + 8 : indent + 10}px`,
                      fontSize: isPai  11 : 12,
                      fontWeight: fw,
                      background: bg,
                      color: clr,
                      cursor: (isPai && hasChildren)  'pointer' : (isPai  'default' : 'pointer'),
                      borderBottom: '1px solid ' + (isPai  'rgba(255,255,255,0.08)' : '#f3f4f6'),
                      userSelect: 'none',
                    }}
                    onMouseEnter={e => { if (!isPai) e.currentTarget.style.background = '#f0f7ff' }}
                    onMouseLeave={e => { if (!isPai) e.currentTarget.style.background = 'transparent' }}
                  >
                    {/* Seta expand/collapse para pais com filhos */}
                    {isPai && (
                      <span style={{
                        fontSize: 10, width: 14, textAlign: 'center', flexShrink: 0,
                        opacity: hasChildren  1 : 0.3,
                        transition: 'transform 0.15s',
                        display: 'inline-block',
                        transform: (!isCollapsed && hasChildren)  'rotate(90deg)' : 'rotate(0deg)',
                      }}>
                        ▶
                      </span>
                    )}
                    <span style={{
                      fontFamily: 'monospace',
                      color: isPai  '#a5c8f0' : '#185FA5',
                      fontSize: 10, whiteSpace: 'nowrap', flexShrink: 0,
                    }}>
                      {it.codigo}
                    </span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                      {it.descricao}
                    </span>
                    {!isPai && (
                      <span style={{ marginLeft: 'auto', fontSize: 9, color: '#bbb', whiteSpace: 'nowrap', flexShrink: 0 }}>
                        ✔ selecionar
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        )}

        <label style={lblStyle}>Legenda (opcional)</label>
        <input
          type="text"
          value={legenda}
          onChange={e => setLegenda(e.target.value)}
          placeholder="Ex: Vista geral da fundação concluída"
          style={inputStyle}
        />

        <label style={lblStyle}>Arquivo de Imagem</label>
        <input
          type="file"
          accept="image/*"
          onChange={e => setFile(e.target.files?.[0] || null)}
          style={{ ...inputStyle, padding: 6 }}
        />
        {file && (
          <div style={{ fontSize: 11, color: '#555', marginTop: -8, marginBottom: 10 }}>
            📎 {file.name} ({(file.size / 1024).toFixed(0)} KB)
          </div>
        )}

        {erro && (
          <div style={{ background: '#fee2e2', color: '#b91c1c', padding: '8px 12px', borderRadius: 6, fontSize: 12, marginBottom: 12 }}>
            {erro}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
          <button onClick={onClose} style={btnStyle('#6b7280')} disabled={enviando}>Cancelar</button>
          <button onClick={handleEnviar} disabled={enviando || !eapSelecionado || !file} style={{
            ...btnStyle(eapSelecionado && file  '#2563eb' : '#9ca3af'),
            cursor: eapSelecionado && file  'pointer' : 'not-allowed',
          }}>
            {enviando  'Enviando…' : 'Adicionar'}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Styles ────────────────────────────────────────────────────────────
const cardStyle = {
  background: '#fff',
  borderRadius: 12,
  border: '0.5px solid #E0E0DC',
  padding: '16px 20px',
  marginBottom: 16,
}

const navBtnStyle = {
  background: '#063057', color: '#fff', border: 'none', borderRadius: 8,
  width: 36, height: 36, fontSize: 16, cursor: 'pointer',
}

function btnStyle(bg) {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 8,
    padding: '9px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
  }
}

const iconBtnStyle = {
  background: 'rgba(0,0,0,0.7)', color: '#fff', border: 'none',
  borderRadius: 6, width: 30, height: 30, cursor: 'pointer', fontSize: 14,
}

const modalOverlay = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}

const modalBox = {
  background: '#fff', borderRadius: 12, padding: 28, width: '90%',
  boxShadow: '0 8px 32px rgba(0,0,0,0.18)', maxHeight: '90vh', overflowY: 'auto',
}

const lblStyle = {
  display: 'block', fontSize: 11, color: '#6b7280', textTransform: 'uppercase',
  letterSpacing: '0.06em', marginBottom: 4, marginTop: 4, fontWeight: 600,
}

const inputStyle = {
  width: '100%', padding: '8px 12px', borderRadius: 6,
  border: '1px solid #d1d5db', fontSize: 13, marginBottom: 12,
  boxSizing: 'border-box',
}
