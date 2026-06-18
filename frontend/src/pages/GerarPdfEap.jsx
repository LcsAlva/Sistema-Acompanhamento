import { useState } from 'react'

// ── Página dedicada: Gerar PDF da EAP (padrão Petrobras) ──────────────────────
// Extraída do antigo modal do dashboard Financeiro. Form + pré-visualização
// inline; usa o endpoint /api/eap/gerar-pdf.
export default function GerarPdfEap() {
  const [gerando, setGerando]         = useState(false)
  const [previewUrl, setPreviewUrl]   = useState(null)   // blob URL para o iframe
  const [nomeArquivo, setNomeArquivo] = useState('')

  const hoje = new Date()
  const [revisao, setRevisao]         = useState('H')
  const [dataDoc, setDataDoc]         = useState(
    `${String(hoje.getDate()).padStart(2,'0')}/${String(hoje.getMonth()+1).padStart(2,'0')}/${hoje.getFullYear()}`
  )
  const [execucao, setExecucao]       = useState('Diego Souza')
  const [verificacao, setVerificacao] = useState('Lucas Barros')
  const [aprovacao, setAprovacao]     = useState('Eduardo Carnaúba')

  function buildParams() {
    return new URLSearchParams({ revisao, data_doc: dataDoc, execucao, verificacao, aprovacao })
  }

  async function handleVisualizar() {
    setGerando(true)
    try {
      const resp = await fetch(`/api/eap/gerar-pdf?${buildParams()}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(err.detail || resp.statusText)
      }
      const blob = await resp.blob()
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      const url  = URL.createObjectURL(blob)
      setNomeArquivo(`ET-5275.00-2000-911-E6G-002=${revisao}.pdf`)
      setPreviewUrl(url)
    } catch (e) {
      alert('Erro ao gerar PDF: ' + e.message)
    } finally {
      setGerando(false)
    }
  }

  function handleBaixar() {
    if (!previewUrl) return
    const a = document.createElement('a')
    a.href = previewUrl
    a.download = nomeArquivo
    a.click()
  }

  return (
    <div className="min-h-screen p-4" style={{ background: '#F2F2F0' }}>
      <div className="flex items-center gap-3 mb-3">
        <h1 style={{ fontSize: 18, fontWeight: 600, color: '#063057' }}>Gerar PDF da EAP</h1>
        <span style={{ fontSize: 11, color: '#777' }}>Padrão Petrobras</span>
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {/* ── Formulário ── */}
        <div className="card" style={{ width: 420, background: '#fff', borderRadius: 8, padding: 16,
                                       boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          <div style={{ background: '#A32D2D', color: '#fff', margin: '-16px -16px 14px',
                        padding: '12px 16px', borderRadius: '8px 8px 0 0', fontWeight: 700, fontSize: 14 }}>
            📄 Dados do Documento
          </div>
          <p style={{ fontSize: 11, color: '#666', marginTop: 0 }}>
            Preencha os dados e clique em <strong>Visualizar</strong> para conferir o PDF antes de baixar.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              ['Revisão', revisao, setRevisao, 80],
              ['Data do documento (DD/MM/AAAA)', dataDoc, setDataDoc, 160],
              ['Execução', execucao, setExecucao, 250],
              ['Verificação', verificacao, setVerificacao, 250],
              ['Aprovação', aprovacao, setAprovacao, 250],
            ].map(([lbl, val, setter, w]) => (
              <label key={lbl} style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 165, color: '#444', flexShrink: 0 }}>{lbl}:</span>
                <input type="text" value={val} onChange={e => setter(e.target.value)}
                  style={{ width: w, padding: '4px 8px', border: '1px solid #D0D0CC', borderRadius: 4, fontSize: 11 }}
                />
              </label>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
            {previewUrl && (
              <button onClick={handleBaixar}
                style={{ background: '#fff', color: '#A32D2D', padding: '6px 18px', borderRadius: 5,
                         border: '1px solid #A32D2D', fontWeight: 700, fontSize: 12, cursor: 'pointer' }}>
                ⬇ Baixar PDF
              </button>
            )}
            <button onClick={handleVisualizar} disabled={gerando}
              style={{ background: '#A32D2D', color: '#fff', padding: '6px 20px', borderRadius: 5, border: 'none',
                       fontWeight: 700, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              {gerando
                 <><span style={{ display: 'inline-block', width: 12, height: 12, border: '2px solid #fff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />Gerando…</>
                : '👁 Visualizar PDF'}
            </button>
          </div>
        </div>

        {/* ── Pré-visualização ── */}
        <div style={{ flex: 1, minWidth: 360 }}>
          {previewUrl  (
            <div style={{ background: '#fff', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
              <div style={{ background: '#A32D2D', color: '#fff', padding: '8px 14px', fontSize: 12, fontWeight: 700 }}>
                Pré-visualização — {nomeArquivo}
              </div>
              <iframe src={previewUrl} title="Pré-visualização EAP PDF"
                style={{ width: '100%', height: '75vh', border: 'none', background: '#525659' }} />
            </div>
          ) : (
            <div style={{ border: '2px dashed #D0D0CC', borderRadius: 8, padding: '60px 20px',
                          textAlign: 'center', color: '#999', fontSize: 13 }}>
              A pré-visualização do PDF aparecerá aqui.
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
