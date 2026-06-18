import { useEffect, useState } from 'react'
import { getSigemConciliacao, uploadSigem } from '../api'

const C = {
  wrap: { padding: 24, maxWidth: 1200, margin: '0 auto' },
  h1: { fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 },
  sub: { color: '#6b7280', fontSize: 13, marginTop: 4 },
  card: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginTop: 16 },
  btn: { background: '#1d4ed8', color: 'white', border: 'none', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  input: { padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13 },
  th: { textAlign: 'left', padding: '8px 10px', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #e5e7eb' },
  td: { padding: '8px 10px', fontSize: 13, borderBottom: '1px solid #f3f4f6', verticalAlign: 'top' },
  badge: (apto) => ({
    display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 11,
    fontWeight: 600, background: apto ? '#dcfce7' : '#fef3c7', color: apto ? '#166534' : '#92400e',
  }),
}

const isSemWorkflow = (s) => (s || '').trim().toUpperCase().replace(/\s+/g, ' ') === 'SEM WORKFLOW'

export default function ConciliacaoSigem() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [erro, setErro] = useState('')
  const [dados, setDados] = useState(null)

  const carregar = async () => setDados(await getSigemConciliacao())

  useEffect(() => { carregar() }, [])

  const enviar = async () => {
    if (!file) return
    setUploading(true); setErro(''); setResultado(null)
    try {
      const fd = new FormData()
      fd.append('arquivo', file)
      const r = await uploadSigem(fd)
      setResultado(r)
      await carregar()
    } catch (e) {
      setErro(e.response?.data?.detail || e.message)
    } finally {
      setUploading(false)
    }
  }

  const linhas = dados?.divergentes || []

  return (
    <div style={C.wrap}>
      <h1 style={C.h1}>Conciliacao LD x SIGEM</h1>
      <div style={C.sub}>A LD mantem estrutura, disciplina e A4. O SIGEM passa a ser a fonte oficial de status quando existir registro correspondente.</div>

      <div style={C.card}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <input type="file" accept=".xlsx,.xls" onChange={e => setFile(e.target.files[0])} style={C.input} />
          <button style={C.btn} disabled={!file || uploading} onClick={enviar}>
            {uploading ? 'Importando...' : 'Importar SIGEM'}
          </button>
          {erro && <span style={{ color: '#b91c1c', fontSize: 13 }}>{erro}</span>}
        </div>
        {resultado && (
          <div style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Stat label="Novos" v={resultado.novos} cor="#1d4ed8" />
              <Stat label="Status alterados" v={resultado.status_alterados} cor="#b45309" />
              <Stat label="Atualizados" v={resultado.atualizados} cor="#374151" />
              <Stat label="Ignoradas" v={resultado.linhas_ignoradas} cor="#6b7280" />
            </div>
            <div style={{ marginTop: 10, fontSize: 12, color: '#6b7280' }}>
              Aba: {resultado.aba} | Cabecalho linha {resultado.linha_cabecalho}
            </div>
          </div>
        )}
      </div>

      {dados && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12, marginTop: 16 }}>
          <Stat label="Total LD" v={dados.total_ld} cor="#111827" />
          <Stat label="Total SIGEM" v={dados.total_sigem} cor="#1d4ed8" />
          <Stat label="Divergentes" v={dados.documentos_divergentes} cor="#b45309" />
          <Stat label="Documentos aptos" v={dados.documentos_aptos} cor="#166534" />
          <Stat label="SEM WORKFLOW" v={dados.documentos_sem_workflow} cor="#166534" />
        </div>
      )}

      <div style={C.card}>
        <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>Documentos divergentes</h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={C.th}>Documento</th>
                <th style={C.th}>Disciplina</th>
                <th style={C.th}>Status LD</th>
                <th style={C.th}>Status SIGEM</th>
                <th style={C.th}>Diferenca</th>
                <th style={C.th}>Dias</th>
                <th style={C.th}>Ultima Atualizacao</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map(l => (
                <tr key={l.documento}>
                  <td style={C.td}><b>{l.documento}</b></td>
                  <td style={C.td}>{l.disciplina || '-'}</td>
                  <td style={C.td}><span style={C.badge(isSemWorkflow(l.status_ld))}>{l.status_ld || '-'}</span></td>
                  <td style={C.td}><span style={C.badge(isSemWorkflow(l.status_sigem))}>{l.status_sigem || '-'}</span></td>
                  <td style={C.td}>{l.diferenca}</td>
                  <td style={C.td}>{l.dias_divergentes ?? '-'}</td>
                  <td style={C.td}>{l.ultima_atualizacao  new Date(l.ultima_atualizacao).toLocaleString('pt-BR') : '-'}</td>
                </tr>
              ))}
              {linhas.length === 0 && <tr><td style={C.td} colSpan={7}>Nenhuma divergencia encontrada.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, v, cor }) {
  return (
    <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: 8, padding: '10px 14px', minWidth: 110 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: cor }}>{v  0}</div>
      <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{label}</div>
    </div>
  )
}
