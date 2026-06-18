import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, RefreshCcw, Save } from 'lucide-react'
import { atualizarAnaliseRevisao, getEventosRevisao } from '../api'

const IMPACTOS = [
  'Sem impacto',
  'Impactou quantitativo',
  'Impactou material',
  'Impactou montagem',
  'Impactou medicao/report',
  'Cancelou item',
  'Adicionou item',
  'Alterou especificacao',
]

const ACOES = [
  'Sem acao necessaria',
  'Atualizar quantitativo',
  'Gerar pedido complementar',
  'Cancelar pedido',
  'Revisar montagem',
  'Revisar report de medicao',
  'Outro',
]

const STATUS = [
  'Pendente analise',
  'Sem impacto',
  'Com impacto',
  'Revisao tratada',
  'Cancelado',
]

const VARIACOES = [
  'Acrescimo',
  'Reducao',
  'Item novo',
  'Item removido',
  'Alteracao de especificacao',
  'A confirmar',
]

const C = {
  wrap: { padding: 24, maxWidth: 1440, margin: '0 auto' },
  h1: { margin: 0, fontSize: 22, fontWeight: 700, color: '#111827' },
  sub: { marginTop: 4, color: '#6b7280', fontSize: 13 },
  toolbar: { display: 'flex', gap: 8, alignItems: 'center', marginTop: 16, flexWrap: 'wrap' },
  input: { height: 34, border: '1px solid #d1d5db', borderRadius: 6, padding: '0 10px', fontSize: 13 },
  select: { height: 34, border: '1px solid #d1d5db', borderRadius: 6, padding: '0 8px', fontSize: 13, background: 'white' },
  btn: { height: 34, border: '1px solid #0f4c81', borderRadius: 6, background: '#0f4c81', color: 'white', padding: '0 12px', display: 'inline-flex', gap: 6, alignItems: 'center', fontSize: 13, cursor: 'pointer' },
  grid: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 16, marginTop: 16, alignItems: 'start' },
  panel: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' },
  side: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 },
  th: { textAlign: 'left', padding: '9px 10px', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #e5e7eb', background: '#f9fafb', whiteSpace: 'nowrap' },
  td: { padding: '9px 10px', fontSize: 12, borderBottom: '1px solid #f3f4f6', verticalAlign: 'top' },
  label: { display: 'block', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', margin: '10px 0 4px' },
  textarea: { width: '100%', minHeight: 74, border: '1px solid #d1d5db', borderRadius: 6, padding: 8, resize: 'vertical', fontSize: 13 },
}

const fmtData = (v) => v ? new Date(v).toLocaleString('pt-BR') : '-'
const badgeColor = (status) => status === 'Pendente analise' ? '#b45309' : status === 'Sem impacto' ? '#166534' : '#0f4c81'

export default function AnaliseRevisoes() {
  const [eventos, setEventos] = useState([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [selecionado, setSelecionado] = useState(null)
  const [form, setForm] = useState({})
  const [carregando, setCarregando] = useState(false)
  const [salvando, setSalvando] = useState(false)

  const carregar = async () => {
    setCarregando(true)
    try {
      const data = await getEventosRevisao({ q: q || undefined, status: status || undefined })
      setEventos(data)
      if (!selecionado && data.length) abrir(data[0])
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => { carregar() }, [])

  const resumo = useMemo(() => ({
    pendentes: eventos.filter(e => e.status_analise === 'Pendente analise').length,
    comAlerta: eventos.filter(e => e.alertas?.length).length,
  }), [eventos])

  const abrir = (ev) => {
    setSelecionado(ev)
    setForm({
      status_analise: ev.status_analise || 'Pendente analise',
      impacto_informado: ev.impacto_informado || 'Sem impacto',
      acao_necessaria: ev.acao_necessaria || 'Sem acao necessaria',
      observacao_impacto: ev.observacao_impacto || '',
      item_controlavel: ev.variacao?.item_controlavel || '',
      quantidade_anterior: ev.variacao?.quantidade_anterior ?? '',
      quantidade_nova: ev.variacao?.quantidade_nova ?? '',
      unidade: ev.variacao?.unidade || '',
      tipo_variacao: ev.variacao?.tipo_variacao || 'A confirmar',
      acao_pedido: '',
      analisado_por: 'usuario',
    })
  }

  const salvar = async () => {
    if (!selecionado) return
    setSalvando(true)
    try {
      await atualizarAnaliseRevisao(selecionado.id, {
        ...form,
        quantidade_anterior: form.quantidade_anterior === '' ? null : Number(form.quantidade_anterior),
        quantidade_nova: form.quantidade_nova === '' ? null : Number(form.quantidade_nova),
      })
      await carregar()
    } catch (e) {
      alert('Erro ao salvar analise: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div style={C.wrap}>
      <h1 style={C.h1}>Analise de Revisoes</h1>
      <div style={C.sub}>
        {eventos.length} registro(s) de impacto · {resumo.pendentes} pendente(s) · {resumo.comAlerta} com alerta(s)
      </div>

      <div style={C.toolbar}>
        <input style={{ ...C.input, width: 260 }} placeholder="Documento" value={q} onChange={e => setQ(e.target.value)} />
        <select style={C.select} value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">Todos os status</option>
          {STATUS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button style={C.btn} onClick={carregar} disabled={carregando}>
          <RefreshCcw size={16} /> {carregando ? 'Atualizando' : 'Atualizar'}
        </button>
      </div>

      <div style={C.grid}>
        <div style={C.panel}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 1180, borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={C.th}>Documento</th>
                  <th style={C.th}>Rev. anterior</th>
                  <th style={C.th}>Rev. nova</th>
                  <th style={C.th}>Deteccao</th>
                  <th style={C.th}>Controle aplicavel</th>
                  <th style={C.th}>Controle afetado</th>
                  <th style={C.th}>Status controle</th>
                  <th style={C.th}>Status analise</th>
                  <th style={C.th}>Impacto</th>
                  <th style={C.th}>Acao</th>
                  <th style={C.th}>Observacao</th>
                </tr>
              </thead>
              <tbody>
                {eventos.map((ev, idx) => (
                  <tr key={`${ev.id}-${ev.codigo_controle_afetado || idx}`} onClick={() => abrir(ev)} style={{ cursor: 'pointer', background: selecionado?.id === ev.id ? '#eff6ff' : 'white' }}>
                    <td style={C.td}><b>{ev.codigo_documento}</b>{ev.alertas?.length > 0 && <AlertTriangle size={14} color="#b45309" style={{ marginLeft: 6, verticalAlign: 'text-bottom' }} />}</td>
                    <td style={C.td}>{ev.revisao_anterior || '-'}</td>
                    <td style={C.td}>{ev.revisao_nova || '-'}</td>
                    <td style={C.td}>{fmtData(ev.data_deteccao)}</td>
                    <td style={C.td}>{ev.controle_aplicavel || '-'}</td>
                    <td style={C.td}>{ev.codigo_controle_afetado || '-'}</td>
                    <td style={C.td}>{ev.status_controle || '-'}</td>
                    <td style={C.td}><span style={{ color: badgeColor(ev.status_analise), fontWeight: 700 }}>{ev.status_analise}</span></td>
                    <td style={C.td}>{ev.impacto_informado || '-'}</td>
                    <td style={C.td}>{ev.acao_necessaria || '-'}</td>
                    <td style={C.td}>{ev.observacao_impacto || '-'}</td>
                  </tr>
                ))}
                {!eventos.length && (
                  <tr><td style={C.td} colSpan={11}>Sem eventos de revisao detectados.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <aside style={C.side}>
          {selecionado ? (
            <>
              <div style={{ fontSize: 12, color: '#6b7280' }}>Evento {selecionado.id_evento_revisao}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#111827', marginTop: 2 }}>{selecionado.codigo_documento}</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>Rev. {selecionado.revisao_anterior || '-'} para {selecionado.revisao_nova}</div>

              {selecionado.alertas?.map(a => (
                <div key={a} style={{ marginTop: 10, padding: 10, border: '1px solid #fde68a', background: '#fffbeb', borderRadius: 6, fontSize: 12, color: '#92400e' }}>
                  {a}
                </div>
              ))}

              {selecionado.pedido && (
                <div style={{ marginTop: 10, padding: 10, border: '1px solid #e5e7eb', borderRadius: 6, fontSize: 12 }}>
                  <b>Pedido:</b> {selecionado.pedido.numero_pedido || '-'} · {selecionado.pedido.status_pedido || '-'} · rev. {selecionado.pedido.revisao_documento_usada || '-'}
                </div>
              )}

              <label style={C.label}>Status da analise</label>
              <select style={{ ...C.select, width: '100%' }} value={form.status_analise || ''} onChange={e => setForm({ ...form, status_analise: e.target.value })}>
                {STATUS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>

              <label style={C.label}>Impacto informado</label>
              <select style={{ ...C.select, width: '100%' }} value={form.impacto_informado || ''} onChange={e => setForm({ ...form, impacto_informado: e.target.value })}>
                {IMPACTOS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>

              <label style={C.label}>Acao tomada</label>
              <select style={{ ...C.select, width: '100%' }} value={form.acao_necessaria || ''} onChange={e => setForm({ ...form, acao_necessaria: e.target.value })}>
                {ACOES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>

              <label style={C.label}>Variacao de quantitativo</label>
              <input style={{ ...C.input, width: '100%', marginBottom: 6 }} placeholder="Item controlavel" value={form.item_controlavel || ''} onChange={e => setForm({ ...form, item_controlavel: e.target.value })} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                <input style={C.input} type="number" placeholder="Qtd anterior" value={form.quantidade_anterior} onChange={e => setForm({ ...form, quantidade_anterior: e.target.value })} />
                <input style={C.input} type="number" placeholder="Qtd nova" value={form.quantidade_nova} onChange={e => setForm({ ...form, quantidade_nova: e.target.value })} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
                <input style={C.input} placeholder="Unidade" value={form.unidade || ''} onChange={e => setForm({ ...form, unidade: e.target.value })} />
                <select style={C.select} value={form.tipo_variacao || ''} onChange={e => setForm({ ...form, tipo_variacao: e.target.value })}>
                  {VARIACOES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <label style={C.label}>Observacao</label>
              <textarea style={C.textarea} value={form.observacao_impacto || ''} onChange={e => setForm({ ...form, observacao_impacto: e.target.value })} />

              <button style={{ ...C.btn, width: '100%', justifyContent: 'center', marginTop: 12 }} onClick={salvar} disabled={salvando}>
                <Save size={16} /> {salvando ? 'Salvando' : 'Salvar analise'}
              </button>
            </>
          ) : (
            <div style={{ color: '#6b7280', fontSize: 13 }}>Selecione um evento para registrar a analise.</div>
          )}
        </aside>
      </div>
    </div>
  )
}
