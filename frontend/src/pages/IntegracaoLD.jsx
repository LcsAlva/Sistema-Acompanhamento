import { useEffect, useState } from 'react'
import {
  uploadLd, getLdDocumentos, getLdHistorico, getLdFiltros,
} from '../api'

const C = {
  wrap: { padding: 24, maxWidth: 1200, margin: '0 auto' },
  h1: { fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 },
  sub: { color: '#6b7280', fontSize: 13, marginTop: 4 },
  card: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, marginTop: 16 },
  btn: { background: '#1d4ed8', color: 'white', border: 'none', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  btnGhost: { background: 'white', color: '#1d4ed8', border: '1px solid #1d4ed8', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', fontSize: 12 },
  input: { padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13 },
  th: { textAlign: 'left', padding: '8px 10px', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #e5e7eb' },
  td: { padding: '8px 10px', fontSize: 13, borderBottom: '1px solid #f3f4f6' },
  badge: (apto) => ({ display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: apto  '#dcfce7' : '#f3f4f6', color: apto  '#166534' : '#374151' }),
}

const isApto = (s) => (s || '').trim().toUpperCase().replace(/\s+/g, ' ') === 'SEM WORKFLOW'

export default function IntegracaoLD() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [erro, setErro] = useState('')
  const [docs, setDocs] = useState([])
  const [filtros, setFiltros] = useState({ disciplinas: [], status: [] })
  const [fDisc, setFDisc] = useState('')
  const [fStatus, setFStatus] = useState('')
  const [q, setQ] = useState('')
  const [histDoc, setHistDoc] = useState(null)
  const [hist, setHist] = useState([])

  const carregar = async () => {
    const params = {}
    if (fDisc) params.disciplina = fDisc
    if (fStatus) params.status = fStatus
    if (q) params.q = q
    const [d, f] = await Promise.all([getLdDocumentos(params), getLdFiltros()])
    setDocs(d)
    setFiltros(f)
  }

  useEffect(() => { carregar() }, [fDisc, fStatus]) // eslint-disable-line

  const enviar = async () => {
    if (!file) return
    setUploading(true); setErro(''); setResultado(null)
    try {
      const fd = new FormData()
      fd.append('arquivo', file)
      const r = await uploadLd(fd)
      setResultado(r)
      await carregar()
    } catch (e) {
      setErro(e.response?.data?.detail || e.message)
    } finally {
      setUploading(false)
    }
  }

  const verHistorico = async (doc) => {
    setHistDoc(doc)
    setHist(await getLdHistorico(doc.id))
  }

  return (
    <div style={C.wrap}>
      <h1 style={C.h1}>Integração LD / SIGEM</h1>
      <div style={C.sub}>Importe a LD recebida da S5. O status <b>SEM WORKFLOW</b> é considerado 100% apto para medição. Cada mudança de status fica registrada no histórico.</div>

      {/* Upload */}
      <div style={C.card}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <input type="file" accept=".xlsx,.xls" onChange={e => setFile(e.target.files[0])} style={C.input} />
          <button style={C.btn} disabled={!file || uploading} onClick={enviar}>
            {uploading  'Importando…' : 'Importar LD'}
          </button>
          {erro && <span style={{ color: '#b91c1c', fontSize: 13 }}>⚠ {erro}</span>}
        </div>
        {resultado && (
          <div style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Stat label="Novos" v={resultado.novos} cor="#1d4ed8" />
              <Stat label="Status alterados" v={resultado.status_alterados} cor="#b45309" />
              <Stat label="Atualizados" v={resultado.atualizados} cor="#374151" />
              <Stat label="Sem mudança" v={resultado.sem_mudanca} cor="#6b7280" />
              <Stat label="Linhas ignoradas" v={resultado.linhas_ignoradas} cor="#6b7280" />
            </div>
            <div style={{ marginTop: 10, fontSize: 12, color: '#6b7280' }}>
              Colunas detectadas: {Object.entries(resultado.colunas_detectadas || {}).map(([k, v]) => `${k}="${v}"`).join('  ·  ') || '—'}
              {' '}| Aba: {resultado.aba} | Cabeçalho na linha {resultado.linha_cabecalho}
            </div>
            {resultado.transicoes?.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 12 }}>
                <b>Transições de status:</b>{' '}
                {resultado.transicoes.slice(0, 30).map((t, i) => (
                  <span key={i} style={{ marginRight: 10 }}>{t.codigo}: {t.de || '—'} → {t.para}</span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filtros + tabela */}
      <div style={C.card}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <select style={C.input} value={fDisc} onChange={e => setFDisc(e.target.value)}>
            <option value="">Todas disciplinas</option>
            {filtros.disciplinas.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <select style={C.input} value={fStatus} onChange={e => setFStatus(e.target.value)}>
            <option value="">Todos status</option>
            {filtros.status.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input style={C.input} placeholder="Buscar código/título…" value={q}
                 onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && carregar()} />
          <button style={C.btnGhost} onClick={carregar}>Filtrar</button>
          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#6b7280' }}>{docs.length} documento(s)</span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={C.th}>Documento</th><th style={C.th}>Título</th>
                <th style={C.th}>Disciplina</th><th style={C.th}>Rev</th>
                <th style={C.th}>Status</th><th style={C.th}>A4</th><th style={C.th}></th>
              </tr>
            </thead>
            <tbody>
              {docs.map(d => (
                <tr key={d.id}>
                  <td style={C.td}><b>{d.codigo_documento}</b></td>
                  <td style={C.td}>{d.titulo}</td>
                  <td style={C.td}>{d.disciplina}</td>
                  <td style={C.td}>{d.revisao}</td>
                  <td style={C.td}><span style={C.badge(isApto(d.status))}>{d.status}</span></td>
                  <td style={C.td}>{d.a4_equivalente}</td>
                  <td style={C.td}><button style={C.btnGhost} onClick={() => verHistorico(d)}>Histórico</button></td>
                </tr>
              ))}
              {docs.length === 0 && <tr><td style={C.td} colSpan={7}>Nenhum documento. Importe uma LD acima.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal histórico */}
      {histDoc && (
        <div onClick={() => setHistDoc(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: 'white', borderRadius: 10, padding: 20, width: 560, maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>Histórico — {histDoc.codigo_documento}</h3>
              <button style={C.btnGhost} onClick={() => setHistDoc(null)}>Fechar</button>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 12 }}>
              <thead><tr><th style={C.th}>Data</th><th style={C.th}>De</th><th style={C.th}>Para</th><th style={C.th}>Arquivo</th></tr></thead>
              <tbody>
                {hist.map(h => (
                  <tr key={h.id}>
                    <td style={C.td}>{h.data_alteracao  new Date(h.data_alteracao).toLocaleString('pt-BR') : '—'}</td>
                    <td style={C.td}>{h.status_anterior || '—'}</td>
                    <td style={C.td}><span style={C.badge(isApto(h.status_novo))}>{h.status_novo}</span></td>
                    <td style={C.td} title={h.arquivo_origem}>{h.arquivo_origem}</td>
                  </tr>
                ))}
                {hist.length === 0 && <tr><td style={C.td} colSpan={4}>Sem transições registradas.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, v, cor }) {
  return (
    <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: '8px 14px', minWidth: 110 }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: cor }}>{v  0}</div>
      <div style={{ fontSize: 11, color: '#6b7280' }}>{label}</div>
    </div>
  )
}
