import { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw, ShieldCheck } from 'lucide-react'
import { getPerformanceAuditoria } from '../api'

const fmtBRL = (v) =>
  (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtPct = (v) =>
  v == null  '-' : `${(v  0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
const fmtMes = (iso) => {
  const [ano, mes] = iso.split('-')
  return `${mes}/${ano.slice(2)}`
}

const labelClassificacao = {
  proporcional: 'Proporcional',
  nao_proporcional: 'Nao proporcional',
  hibrido: 'Hibrido',
}

export default function PerformanceAuditoria() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)
  const [loading, setLoading] = useState(true)

  const carregar = (recalcular = false) => {
    setLoading(true)
    getPerformanceAuditoria(recalcular)
      .then(setData)
      .catch(e => setErro(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    getPerformanceAuditoria(false)
      .then(result => { if (active) setData(result) })
      .catch(e => { if (active) setErro(e.response?.data?.detail || e.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (erro) return <div className="performance-page"><div className="audit-error">{erro}</div></div>
  if (loading) return <div className="performance-page"><div className="card">Carregando auditoria integrada...</div></div>
  if (!data?.disponivel) {
    return (
      <div className="performance-page">
        <div className="placeholder-panel">
          <div>
            <span className="eyebrow">Gestao Integrada - Fase 2A</span>
            <h2>Auditoria indisponivel</h2>
            <p>{data?.motivo || 'Dados insuficientes para auditoria Produção x Econômico.'}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="performance-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestao Integrada - Fase 2A</span>
          <h2>Auditoria Produção x Econômico</h2>
          <p>Validação mensal antes de qualquer dashboard integrado. Granularidade oficial: mês.</p>
        </div>
        <button type="button" className="btn-primary" onClick={() => carregar(true)}>
          <RefreshCw size={16} />
          Recalcular
        </button>
      </section>

      <section className="performance-meta">
        <article>
          <span>Importação econômica</span>
          <strong>{data.importacao?.arquivo_original}</strong>
        </article>
        <article>
          <span>Produção</span>
          <strong>{data.producao?.nome || 'Sem projeto ativo'}</strong>
          <small>{data.producao?.fonte}</small>
        </article>
        <article>
          <span>Modelagem</span>
          <strong>{data.modelagem?.relacao}</strong>
          <small>{data.modelagem?.restricao}</small>
        </article>
      </section>

      <section className="econ-table-card">
        <div className="econ-chart-head">
          <ShieldCheck size={18} />
          <div>
            <strong>Tabela de Validação Mensal</strong>
            <span>Mês, avanço físico e acumulados econômicos auditados</span>
          </div>
        </div>
        <div className="econ-table-wrap">
          <table className="econ-table">
            <thead>
              <tr>
                <th>Mês</th>
                <th>Avanço Físico %</th>
                <th>Receita Acumulada</th>
                <th>Custos Acumulados</th>
                <th>Resultado Acumulado</th>
                <th>Riscos</th>
              </tr>
            </thead>
            <tbody>
              {(data.validacao_mensal || []).map(row => (
                <tr key={row.mes}>
                  <td><strong>{fmtMes(row.mes)}</strong></td>
                  <td>{fmtPct(row.avanco_fisico_pct)}</td>
                  <td>{fmtBRL(row.receita_acumulada)}</td>
                  <td>{fmtBRL(row.custos_acumulados)}</td>
                  <td className={row.resultado_acumulado < 0  'danger' : 'success'}>{fmtBRL(row.resultado_acumulado)}</td>
                  <td>
                    {(row.riscos || []).length  (
                      <span className="risk-chip"><AlertTriangle size={12} />{row.riscos.length}</span>
                    ) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="performance-grid">
        <div className="econ-table-card">
          <div className="econ-chart-head">
            <ShieldCheck size={18} />
            <div>
              <strong>Classificação dos Custos</strong>
              <span>Proporcionalidade frente ao avanço físico</span>
            </div>
          </div>
          <div className="econ-table-wrap">
            <table className="econ-table">
              <thead>
                <tr>
                  <th>Categoria DRE</th>
                  <th>Classificação</th>
                  <th>Comportamento</th>
                  <th>Risco</th>
                </tr>
              </thead>
              <tbody>
                {(data.classificacao_custos || []).map(row => (
                  <tr key={row.categoria_dre}>
                    <td><strong>{row.categoria_dre}</strong></td>
                    <td><span className={`class-chip ${row.classificacao}`}>{labelClassificacao[row.classificacao] || row.classificacao}</span></td>
                    <td>{row.comportamento}</td>
                    <td>{row.risco_interpretacao}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="performance-risks">
          <div className="econ-chart-head">
            <AlertTriangle size={18} />
            <div>
              <strong>Falsas Interpretações</strong>
              <span>Alertas obrigatórios antes do dashboard integrado</span>
            </div>
          </div>
          {(data.riscos_interpretacao || []).map(risco => (
            <article key={risco}>{risco}</article>
          ))}
        </div>
      </section>
    </div>
  )
}
