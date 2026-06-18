import { useCallback, useEffect, useMemo, useState } from 'react'
import { Copy, GitCompare, History, Plus, Save, SlidersHorizontal } from 'lucide-react'
import {
  ajustarEconomicoForecastOperacionalCategoria,
  clonarEconomicoForecastOperacionalVersao,
  compararEconomicoForecastOperacionalVersoes,
  criarEconomicoForecastOperacionalVersao,
  getEconomicoForecastOperacionalVersao,
  getEconomicoForecastOperacionalVersoes,
} from '../api'

const fmtBRL = (v) =>
  (v  0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const fmtDateTime = (v) => v  new Date(v).toLocaleString('pt-BR') : '-'
export default function EconomicoForecastOperacional() {
  const [versoes, setVersoes] = useState([])
  const [detalhe, setDetalhe] = useState(null)
  const [selecionada, setSelecionada] = useState(null)
  const [comparacao, setComparacao] = useState(null)
  const [erro, setErro] = useState(null)
  const [loading, setLoading] = useState(false)
  const [createForm, setCreateForm] = useState({ nome: '', motivo: '', usuario: 'sistema' })
  const [cloneForm, setCloneForm] = useState({ nome: '', motivo: '', usuario: 'sistema' })
  const [ajusteForm, setAjusteForm] = useState({ categoria: '', valor_novo: '', justificativa: '', usuario: 'sistema' })
  const [compareForm, setCompareForm] = useState({ base_id: '', novo_id: '' })

  const carregarVersoes = useCallback(() =>
    getEconomicoForecastOperacionalVersoes()
      .then(data => {
        const rows = data.versoes || []
        setVersoes(rows)
        if (!selecionada && rows[0]) {
          setSelecionada(rows[0].id)
        }
      })
      .catch(e => setErro(e.response?.data?.detail || e.message)), [selecionada])

  useEffect(() => { carregarVersoes() }, [carregarVersoes])

  useEffect(() => {
    if (!selecionada) {
      setDetalhe(null)
      return
    }
    getEconomicoForecastOperacionalVersao(selecionada)
      .then(data => {
        setDetalhe(data)
        setAjusteForm(f => ({ ...f, categoria: f.categoria || data.categorias?.[0]?.categoria || '' }))
      })
      .catch(e => setErro(e.response?.data?.detail || e.message))
  }, [selecionada])

  const criarVersao = async (e) => {
    e.preventDefault()
    setLoading(true)
    setErro(null)
    try {
      const data = await criarEconomicoForecastOperacionalVersao(cleanPayload(createForm))
      await carregarVersoes()
      setSelecionada(data.versao.id)
      setCreateForm({ nome: '', motivo: '', usuario: createForm.usuario || 'sistema' })
    } catch (e) {
      setErro(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const clonarVersao = async (e) => {
    e.preventDefault()
    if (!selecionada) return
    setLoading(true)
    setErro(null)
    try {
      const data = await clonarEconomicoForecastOperacionalVersao(selecionada, cleanPayload(cloneForm))
      await carregarVersoes()
      setSelecionada(data.versao.id)
      setCloneForm({ nome: '', motivo: '', usuario: cloneForm.usuario || 'sistema' })
    } catch (e) {
      setErro(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const ajustarCategoria = async (e) => {
    e.preventDefault()
    if (!selecionada) return
    setLoading(true)
    setErro(null)
    try {
      const data = await ajustarEconomicoForecastOperacionalCategoria(selecionada, {
        categoria: ajusteForm.categoria,
        valor_novo: Number(ajusteForm.valor_novo),
        justificativa: ajusteForm.justificativa,
        usuario: ajusteForm.usuario || 'sistema',
      })
      setDetalhe(data)
      await carregarVersoes()
      setAjusteForm(f => ({ ...f, valor_novo: '', justificativa: '' }))
    } catch (e) {
      setErro(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const compararVersoes = async (e) => {
    e.preventDefault()
    if (!compareForm.base_id || !compareForm.novo_id) return
    setLoading(true)
    setErro(null)
    try {
      setComparacao(await compararEconomicoForecastOperacionalVersoes(compareForm.base_id, compareForm.novo_id))
    } catch (e) {
      setErro(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const componentes = useMemo(() => {
    const map = Object.fromEntries((detalhe?.componentes || []).map(i => [i.indicador, i.valor]))
    return [
      ['Receita Forecast', map.receita],
      ['Custos Diretos', map.custos_diretos],
      ['Custos Indiretos', map.custos_indiretos],
      ['Impostos', map.impostos],
      ['Resultado Forecast', map.resultado],
    ]
  }, [detalhe])

  return (
    <div className="econ-page">
      <section className="econ-hero">
        <div>
          <span className="eyebrow">Gestão Econômica - MVP</span>
          <h2>Forecast Operacional</h2>
          <p>Versões, ajustes por categoria, comparação e histórico sem alterar o forecast oficial importado.</p>
        </div>
      </section>

      {erro && <div className="audit-error">{erro}</div>}

      <section className="analysis-grid">
        <FormCard icon={<Plus size={18} />} title="Criar versão da última importação auditada">
          <form className="forecast-op-form" onSubmit={criarVersao}>
            <input className="input-base" placeholder="Nome da versão" value={createForm.nome} onChange={e => setCreateForm(f => ({ ...f, nome: e.target.value }))} />
            <input className="input-base" placeholder="Motivo" value={createForm.motivo} onChange={e => setCreateForm(f => ({ ...f, motivo: e.target.value }))} />
            <input className="input-base" placeholder="Usuário" value={createForm.usuario} onChange={e => setCreateForm(f => ({ ...f, usuario: e.target.value }))} />
            <button className="btn-primary" disabled={loading}><Plus size={16} /> Criar versão</button>
          </form>
        </FormCard>

        <FormCard icon={<Copy size={18} />} title="Clonar versão selecionada">
          <form className="forecast-op-form" onSubmit={clonarVersao}>
            <input className="input-base" placeholder="Nome da nova versão" value={cloneForm.nome} onChange={e => setCloneForm(f => ({ ...f, nome: e.target.value }))} />
            <input className="input-base" placeholder="Motivo do clone" value={cloneForm.motivo} onChange={e => setCloneForm(f => ({ ...f, motivo: e.target.value }))} />
            <input className="input-base" placeholder="Usuário" value={cloneForm.usuario} onChange={e => setCloneForm(f => ({ ...f, usuario: e.target.value }))} />
            <button className="btn-secondary" disabled={loading || !selecionada}><Copy size={16} /> Clonar</button>
          </form>
        </FormCard>
      </section>

      <section className="econ-table-card">
        <div className="econ-chart-head"><History size={18} /><div><strong>Versões</strong><span>Forecasts operacionais criados a partir da camada auditada</span></div></div>
        <div className="econ-table-wrap">
          <table className="econ-table">
            <thead><tr><th>Versão</th><th>Nome</th><th>Origem</th><th>Status</th><th>Importação</th><th>Resultado Forecast</th><th>Ajustes</th><th>Criado em</th></tr></thead>
            <tbody>
              {versoes.map(v => (
                <tr key={v.id} className={selecionada === v.id  'selected-row' : ''} onClick={() => setSelecionada(v.id)}>
                  <td><strong>{v.codigo}</strong></td>
                  <td>{v.nome}</td>
                  <td>{v.origem}</td>
                  <td>{v.status}</td>
                  <td>{v.importacao?.id || '-'}</td>
                  <td>{fmtBRL(v.resultado_forecast)}</td>
                  <td>{v.ajustes_count}</td>
                  <td>{fmtDateTime(v.criado_em)}</td>
                </tr>
              ))}
              {!versoes.length && <tr><td colSpan="8">Nenhuma versão operacional criada.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {detalhe && (
        <>
          <section className="analysis-kpi-grid five">
            {componentes.map(([label, value]) => <section className="analysis-kpi" key={label}><span>{label}</span><strong>{fmtBRL(value)}</strong></section>)}
          </section>

          <section className="analysis-grid">
            <section className="econ-table-card">
              <div className="econ-chart-head"><SlidersHorizontal size={18} /><div><strong>Ajustar categoria</strong><span>Justificativa obrigatória e trilha de alteração</span></div></div>
              <form className="forecast-op-form" onSubmit={ajustarCategoria}>
                <select className="input-base" value={ajusteForm.categoria} onChange={e => setAjusteForm(f => ({ ...f, categoria: e.target.value }))}>
                  {(detalhe.categorias || []).map(row => <option key={row.categoria} value={row.categoria}>{row.categoria}</option>)}
                </select>
                <input className="input-base" type="number" step="0.01" placeholder="Novo valor forecast" value={ajusteForm.valor_novo} onChange={e => setAjusteForm(f => ({ ...f, valor_novo: e.target.value }))} />
                <textarea className="input-base" rows="3" placeholder="Justificativa obrigatória" value={ajusteForm.justificativa} onChange={e => setAjusteForm(f => ({ ...f, justificativa: e.target.value }))} />
                <input className="input-base" placeholder="Usuário" value={ajusteForm.usuario} onChange={e => setAjusteForm(f => ({ ...f, usuario: e.target.value }))} />
                <button className="btn-primary" disabled={loading || !ajusteForm.categoria || !ajusteForm.justificativa || ajusteForm.valor_novo === ''}><Save size={16} /> Salvar ajuste</button>
              </form>
            </section>

            <section className="econ-table-card">
              <div className="econ-chart-head"><GitCompare size={18} /><div><strong>Comparar versões</strong><span>O que mudou entre forecasts</span></div></div>
              <form className="forecast-op-compare" onSubmit={compararVersoes}>
                <select className="input-base" value={compareForm.base_id} onChange={e => setCompareForm(f => ({ ...f, base_id: e.target.value }))}>
                  <option value="">Versão base</option>
                  {versoes.map(v => <option key={v.id} value={v.id}>{v.codigo} - {v.nome}</option>)}
                </select>
                <select className="input-base" value={compareForm.novo_id} onChange={e => setCompareForm(f => ({ ...f, novo_id: e.target.value }))}>
                  <option value="">Versão nova</option>
                  {versoes.map(v => <option key={v.id} value={v.id}>{v.codigo} - {v.nome}</option>)}
                </select>
                <button className="btn-secondary" disabled={loading || !compareForm.base_id || !compareForm.novo_id}><GitCompare size={16} /> Comparar</button>
              </form>
            </section>
          </section>

          <DataTable
            title="Valores por Categoria"
            subtitle="Base de ajuste do forecast operacional"
            rows={detalhe.categorias || []}
            columns={[
              ['categoria', 'Categoria'],
              ['valor', 'Forecast', fmtBRL],
            ]}
          />

          {comparacao && (
            <DataTable
              title={`Comparação ${comparacao.base.codigo} x ${comparacao.novo.codigo}`}
              subtitle="Diferenças por componente e categoria"
              rows={comparacao.comparacao || []}
              columns={[
                ['categoria', 'Categoria'],
                ['forecast_atual', 'Forecast Atual', fmtBRL],
                ['forecast_novo', 'Forecast Novo', fmtBRL],
                ['diferenca', 'Diferença', fmtBRL],
              ]}
            />
          )}

          <section className="analysis-grid">
            <DataTable
              title="Histórico de Ajustes"
              subtitle="Categoria, valores, justificativa, usuário e data"
              rows={detalhe.ajustes || []}
              columns={[
                ['categoria', 'Categoria'],
                ['valor_anterior', 'Anterior', fmtBRL],
                ['valor_novo', 'Novo', fmtBRL],
                ['diferenca', 'Diferença', fmtBRL],
                ['justificativa', 'Justificativa'],
                ['usuario', 'Usuário'],
                ['criado_em', 'Data/Hora', fmtDateTime],
              ]}
            />
            <DataTable
              title="Trilha da Versão"
              subtitle="Eventos técnicos do forecast operacional"
              rows={detalhe.historico || []}
              columns={[
                ['acao', 'Ação'],
                ['descricao', 'Descrição'],
                ['usuario', 'Usuário'],
                ['criado_em', 'Data/Hora', fmtDateTime],
              ]}
            />
          </section>
        </>
      )}
    </div>
  )
}

function FormCard({ icon, title, children }) {
  return (
    <section className="econ-table-card">
      <div className="econ-chart-head">{icon}<div><strong>{title}</strong></div></div>
      {children}
    </section>
  )
}

function DataTable({ title, subtitle, rows, columns }) {
  return (
    <section className="econ-table-card">
      <div className="econ-chart-head"><div><strong>{title}</strong><span>{subtitle}</span></div></div>
      <div className="econ-table-wrap">
        <table className="econ-table">
          <thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id || `${row.categoria}-${index}`}>
                {columns.map(([key, , format]) => <td key={key} className={key === 'diferenca' && row[key] < 0  'danger' : ''}>{format  format(row[key]) : row[key]}</td>)}
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={columns.length}>Sem registros.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function cleanPayload(form) {
  return Object.fromEntries(Object.entries(form).filter(([, value]) => value !== ''))
}
