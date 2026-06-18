import { useEffect, useState } from 'react'
import { CheckCircle2, Upload, XCircle } from 'lucide-react'
import { getEconomicoAuditoria, importarEconomico } from '../api'

const fmtBRL = (v) =>
  (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtPct = (v) =>
  `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`

export default function EconomicoAuditoria() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [importando, setImportando] = useState(false)
  const [erro, setErro] = useState(null)

  const carregar = () => {
    setLoading(true)
    setErro(null)
    getEconomicoAuditoria()
      .then(setData)
      .catch(e => setErro(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { carregar() }, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportando(true)
    setErro(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('usuario', 'sistema')
      const result = await importarEconomico(fd)
      setData({
        importacao: {
          id: result.importacao_id,
          arquivo_original: result.arquivo_original,
          importado_em: result.importado_em,
          status: result.status,
          observacao: `${result.periodos} periodos; ${result.meses_realizados} meses realizados`,
        },
        auditoria: result.auditoria,
        aprovado: result.aprovado,
      })
    } catch (e2) {
      setErro(e2.response?.data?.detail || e2.message)
    } finally {
      setImportando(false)
      e.target.value = ''
    }
  }

  const rows = data?.auditoria || []

  return (
    <div className="audit-page">
      <section className="audit-toolbar">
        <div>
          <span className="eyebrow">{'Gest\u00e3o Econ\u00f4mica - Fase 1A'}</span>
          <h2>Auditoria da planilha</h2>
          <p>Sistema calculado a partir das abas-fonte comparado com o gabarito do Resumo BI.</p>
        </div>
        <label className="btn-primary audit-upload">
          <Upload size={16} />
          <input type="file" accept=".xlsx,.xlsm" onChange={handleUpload} disabled={importando} />
          {importando  'Importando...' : 'Importar planilha'}
        </label>
      </section>

      {erro && <div className="audit-error">{erro}</div>}

      {loading  (
        <div className="card">Carregando auditoria...</div>
      ) : !data?.importacao  (
        <div className="placeholder-panel">
          <div>
            <span className="eyebrow">Sem importacao</span>
            <h2>Nenhuma planilha economica importada</h2>
            <p>Importe a planilha aprovada para executar a auditoria Sistema x Resumo BI.</p>
          </div>
        </div>
      ) : (
        <>
          <div className={`audit-status ${data.aprovado  'is-ok' : 'is-fail'}`}>
            {data.aprovado  <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <div>
              <strong>{data.aprovado  'Auditoria aprovada' : 'Auditoria com divergencias'}</strong>
              <span>
                {data.importacao.arquivo_original} · {data.importacao.observacao || 'importacao economica'}
              </span>
            </div>
          </div>

          <div className="card audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Indicador</th>
                  <th>Sistema</th>
                  <th>Resumo BI</th>
                  <th>Diferenca</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => {
                  const isMargem = row.indicador.toLowerCase().includes('margem')
                  return (
                    <tr key={row.id || row.indicador}>
                      <td>
                        <strong>{row.indicador}</strong>
                        <span>{row.origem_sistema}</span>
                      </td>
                      <td>{isMargem  fmtPct(row.sistema) : fmtBRL(row.sistema)}</td>
                      <td>{isMargem  fmtPct(row.resumo_bi) : fmtBRL(row.resumo_bi)}</td>
                      <td className={Math.abs(row.diferenca || 0) <= 0.01  'ok' : 'fail'}>
                        {isMargem  fmtPct(row.diferenca) : fmtBRL(row.diferenca)}
                      </td>
                      <td>
                        <span className={`audit-pill ${row.aprovado  'ok' : 'fail'}`}>
                          {row.aprovado  'OK' : 'Divergente'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
