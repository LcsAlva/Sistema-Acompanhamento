import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, FileSearch } from 'lucide-react'
import { getEconomicoDesvios, getEconomicoLancamentos } from '../api'

const fmtBRL = (v) =>
  (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) =>
  `${((v  0) * 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtDate = (v) => v  new Date(`${v}T12:00:00`).toLocaleDateString('pt-BR') : '-'

export default function EconomicoDesvios() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)
  const [selected, setSelected] = useState(null)
  const [lancamentos, setLancamentos] = useState(null)

  useEffect(() => {
    getEconomicoDesvios()
      .then(result => {
        setData(result)
        setSelected(result?.ranking?.[0]?.categoria || null)
      })
      .catch(e => setErro(e.response?.data?.detail || e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    getEconomicoLancamentos({ categoria: selected, limit: 200 }).then(setLancamentos)
  }, [selected])

  const ranking = useMemo(() => data?.ranking || [], [data])
  const impacto = data?.impacto || {}
  const perda = (impacto.valor || 0) < 0

  if (erro) return <div className="econ-page"><div className="audit-error">{erro}</div></div>
  if (!data) return <div className="econ-page"><div className="card">Carregando principais desvios...</div></div>

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestao Economica - Fase 1C</span>
          <h2>Principais Desvios</h2>
          <p>Explicacao do impacto financeiro do forecast por categoria e lancamentos relacionados.</p>
        </div>
      </section>

      <section className={`econ-impact ${perda  'is-loss' : 'is-gain'}`}>
        <div className="econ-impact-icon">
          {perda  <ArrowDownRight size={22} /> : <ArrowUpRight size={22} />}
        </div>
        <div>
          <span>Impacto Financeiro</span>
          <h3>{fmtBRL(impacto.valor)} no forecast</h3>
          <p>
            Resultado Linha Base {fmtBRL(impacto.resultado_linha_base)} vs Forecast {fmtBRL(impacto.resultado_forecast)}
            {' '}({fmtPct(impacto.percentual)}).
          </p>
        </div>
        <div className="econ-impact-badge">
          <AlertTriangle size={16} />
          {impacto.tendencia || 'tendencia'}
        </div>
      </section>

      <section className="econ-invest-grid">
        <div className="econ-table-card">
          <div className="econ-chart-head">
            <FileSearch size={18} />
            <div>
              <strong>Ranking de Impactos</strong>
              <span>Maior impacto negativo primeiro</span>
            </div>
          </div>
          <div className="econ-table-wrap">
            <table className="econ-table">
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Impacto Financeiro</th>
                  <th>Impacto %</th>
                  <th>Linha Base</th>
                  <th>Forecast</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map(row => (
                  <tr key={row.categoria} className={selected === row.categoria  'is-selected' : ''} onClick={() => setSelected(row.categoria)}>
                    <td><strong>{row.categoria}</strong></td>
                    <td className={row.impacto_financeiro < 0  'danger' : 'success'}>{fmtBRL(row.impacto_financeiro)}</td>
                    <td>{fmtPct(row.impacto_percentual)}</td>
                    <td>{fmtBRL(row.linha_base)}</td>
                    <td>{fmtBRL(row.forecast)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="econ-table-card">
          <div className="econ-chart-head">
            <FileSearch size={18} />
            <div>
              <strong>Drill Down de Impacto</strong>
              <span>{selected || 'Selecione um desvio'}</span>
            </div>
          </div>
          <div className="econ-table-wrap">
            <table className="econ-table">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Fornecedor</th>
                  <th>Competencia</th>
                  <th>Conta</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {(lancamentos?.lancamentos || []).map(row => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.documento || '-'}</strong>
                      <span>{row.historico || '-'}</span>
                    </td>
                    <td>{row.fornecedor || '-'}</td>
                    <td>{fmtDate(row.data)}</td>
                    <td>
                      <strong>{row.conta || '-'}</strong>
                      <span>{row.categoria_dre || '-'}</span>
                    </td>
                    <td>{fmtBRL(row.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
