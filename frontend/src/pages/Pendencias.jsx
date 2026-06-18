/**
 * Página de Gerenciamento de Pendências
 *
 * Exibe todas as pendências ativas geradas nos BMs fechados.
 * Permite redistribuir pendências para meses futuros.
 */
import { useState, useEffect, useCallback } from 'react'
import { bmGetTodasPendencias, bmRedistribuirPendencia } from '../api'

const MESES_PT = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
  'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

function fmtR(v) {
  if (v == null) return '—'
  return 'R$ ' + (v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(v) {
  if (v == null) return '—'
  return (+v).toFixed(2) + '%'
}

const STATUS_BADGE = {
  ativa:                 { label: 'Ativa',           bg: '#fef3c7', cor: '#92400e' },
  redistribuida_parcial: { label: 'Redistrib. Parcial', bg: '#dbeafe', cor: '#1e40af' },
  redistribuida_total:   { label: 'Redistribuída',   bg: '#dcfce7', cor: '#166534' },
  cancelada:             { label: 'Cancelada',        bg: '#f3f4f6', cor: '#6b7280' },
}

export default function Pendencias() {
  const [pendencias, setPendencias] = useState([])
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState(null)
  const [redistribModal, setRedistribModal] = useState(null) // pendência selecionada

  const carregar = useCallback(async () => {
    setLoading(true)
    setErro(null)
    try {
      const data = await bmGetTodasPendencias()
      setPendencias(data)
    } catch (e) {
      setErro('Erro ao carregar pendências: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { carregar() }, [carregar])

  const totalGap = pendencias.reduce((s, p) => s + (p.valor_gap || 0), 0)
  const totalSaldo = pendencias.reduce((s, p) => s + (p.valor_saldo || 0), 0)

  // Agrupa por mês de origem
  const porMes = pendencias.reduce((acc, p) => {
    const key = `${p.ano_origem}/${String(p.mes_origem).padStart(2, '0')}`
    if (!acc[key]) acc[key] = []
    acc[key].push(p)
    return acc
  }, {})

  return (
    <div style={{ background: '#F2F2F0', minHeight: '100vh', padding: '24px 28px' }}>
      {/* Cabeçalho */}
      <div style={{ background: '#fff', borderRadius: 12, border: '0.5px solid #E0E0DC', padding: '16px 20px', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#063057' }}>Pendências de Medição</div>
            <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
              Itens previstos e não medidos em BMs fechados
            </div>
          </div>
          <button
            onClick={carregar}
            style={{ marginLeft: 'auto', background: '#063057', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
          >
            ↺ Atualizar
          </button>
        </div>
      </div>

      {/* Resumo */}
      {!loading && pendencias.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
          <ResumoCard label="Total de Pendências" valor={pendencias.length.toString()} cor="#92400e" bg="#fef3c7" />
          <ResumoCard label="Valor Total Gap" valor={fmtR(totalGap)} cor="#92400e" bg="#fef3c7" />
          <ResumoCard label="Saldo a Redistribuir" valor={fmtR(totalSaldo)} cor="#1e40af" bg="#dbeafe" />
        </div>
      )}

      {erro && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 8, padding: '12px 16px', color: '#b91c1c', marginBottom: 16 }}>
          {erro}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>Carregando...</div>
      )}

      {!loading && pendencias.length === 0 && (
        <div style={{ background: '#fff', borderRadius: 12, border: '0.5px solid #E0E0DC', padding: '48px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#166534' }}>Nenhuma pendência ativa</div>
          <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>
            Todas as previsões foram integralmente medidas nos BMs fechados.
          </div>
        </div>
      )}

      {/* Lista agrupada por mês de origem */}
      {!loading && Object.entries(porMes).sort((a, b) => b[0].localeCompare(a[0])).map(([mesKey, itens]) => (
        <div key={mesKey} style={{ background: '#fff', borderRadius: 12, border: '0.5px solid #E0E0DC', marginBottom: 16, overflow: 'hidden' }}>
          {/* Cabeçalho do grupo */}
          <div style={{ background: '#063057', color: '#fff', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>BM {mesKey}</span>
            <span style={{ fontSize: 12, opacity: 0.8 }}>
              {itens[0]?.numero_bm || ''} · {itens.length} pendência{itens.length > 1  's' : ''}
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 600 }}>
              {fmtR(itens.reduce((s, p) => s + (p.valor_saldo || 0), 0))} a redistribuir
            </span>
          </div>

          {/* Tabela de itens */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: '#f8fafc' }}>
                  {['Código', 'Descrição', 'Previsto', 'Realizado', 'Gap %', 'Gap R$', 'Saldo R$', 'Status', ''].map((h, i) => (
                    <th key={h + i} style={{
                      padding: '8px 10px', textAlign: i <= 1  'left' : 'right',
                      fontSize: 11, fontWeight: 600, color: '#6b7280',
                      textTransform: 'uppercase', letterSpacing: '0.04em',
                      borderBottom: '1px solid #e5e7eb',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {itens.map((p, idx) => {
                  const badge = STATUS_BADGE[p.status] || STATUS_BADGE.ativa
                  const podeRedistribuir = p.status === 'ativa' || p.status === 'redistribuida_parcial'
                  return (
                    <tr key={p.id} style={{ background: idx % 2 === 0  '#fff' : '#fafaf8', borderBottom: '1px solid #f0f0ee' }}>
                      <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11, color: '#374151' }}>{p.eap_codigo}</td>
                      <td style={{ padding: '8px 10px', maxWidth: 300, color: '#1a1a1a' }}>
                        <div style={{ fontWeight: 500 }}>{p.eap_descricao}</div>
                        {p.redistribuicoes?.length > 0 && (
                          <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
                            Redistribuído p/ {p.redistribuicoes.map(r => r.destino).join(', ')}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', color: '#185FA5' }}>{fmtPct(p.pct_previsto)}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', color: '#3B6D11' }}>{fmtPct(p.pct_realizado)}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', color: '#b45309', fontWeight: 600 }}>{fmtPct(p.pct_gap)}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', color: '#b45309' }}>{fmtR(p.valor_gap)}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', color: '#1e40af', fontWeight: 600 }}>{fmtR(p.valor_saldo)}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                        <span style={{ background: badge.bg, color: badge.cor, borderRadius: 12, padding: '2px 8px', fontSize: 10, fontWeight: 600 }}>
                          {badge.label}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                        {podeRedistribuir && (
                          <button
                            onClick={() => setRedistribModal(p)}
                            style={{ background: '#1e40af', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 10px', fontSize: 11, cursor: 'pointer' }}
                          >
                            Redistribuir
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {/* Modal de redistribuição */}
      {redistribModal && (
        <RedistribuirModal
          pendencia={redistribModal}
          onClose={() => setRedistribModal(null)}
          onSuccess={() => {
            setRedistribModal(null)
            carregar()
          }}
        />
      )}
    </div>
  )
}

function ResumoCard({ label, valor, cor, bg }) {
  return (
    <div style={{ background: bg || '#fff', borderRadius: 12, border: '0.5px solid #E0E0DC', padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: cor }}>{valor}</div>
    </div>
  )
}

function RedistribuirModal({ pendencia: p, onClose, onSuccess }) {
  const hoje = new Date()
  const [destAno, setDestAno] = useState(hoje.getMonth() === 11  hoje.getFullYear() + 1 : hoje.getFullYear())
  const [destMes, setDestMes] = useState(hoje.getMonth() === 11  1 : hoje.getMonth() + 2)
  const [pctFrac, setPctFrac] = useState(100)   // % DO GAP a redistribuir (0-100)
  const [obs, setObs] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState(null)

  const saldoDisp = p.pct_saldo  // em 0-100
  const valorRedistribuir = (p.valor_saldo || 0) * (pctFrac / 100)

  async function handleConfirmar() {
    if (pctFrac <= 0) { setErro('Percentual deve ser maior que zero.'); return }
    if (pctFrac > 100.01) { setErro('Percentual não pode exceder o saldo disponível.'); return }
    setSalvando(true)
    setErro(null)
    try {
      // pct_redistribuir: fração do gap (0-1), onde 1 = redistribuir tudo
      await bmRedistribuirPendencia(
        p.id, destAno, destMes,
        pctFrac / 100,
        'usuario', obs || null
      )
      onSuccess()
    } catch (e) {
      setErro(e?.response?.data?.detail || e.message)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{ background: '#fff', borderRadius: 12, padding: 28, maxWidth: 480, width: '92%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
        <h3 style={{ margin: '0 0 4px', color: '#063057', fontSize: 17 }}>Redistribuir Pendência</h3>
        <div style={{ fontSize: 13, color: '#555', marginBottom: 20 }}>
          <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{p.eap_codigo}</span> — {p.eap_descricao}
        </div>

        {/* Resumo da pendência */}
        <div style={{ background: '#fef3c7', borderRadius: 8, padding: '10px 14px', marginBottom: 20, fontSize: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            <span style={{ color: '#6b7280' }}>Gap original:</span>
            <span style={{ fontWeight: 600, color: '#b45309' }}>{fmtPct(p.pct_gap)} · {fmtR(p.valor_gap)}</span>
            <span style={{ color: '#6b7280' }}>Saldo disponível:</span>
            <span style={{ fontWeight: 600, color: '#1e40af' }}>{fmtPct(p.pct_saldo)} · {fmtR(p.valor_saldo)}</span>
          </div>
        </div>

        {/* Mês destino */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
            Redistribuir para o mês:
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              value={destMes}
              onChange={e => setDestMes(+e.target.value)}
              style={{ flex: 1, padding: '8px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13 }}
            >
              {MESES_PT.slice(1).map((m, i) => (
                <option key={i + 1} value={i + 1}>{m}</option>
              ))}
            </select>
            <input
              type="number"
              value={destAno}
              onChange={e => setDestAno(+e.target.value)}
              min={2024}
              max={2035}
              style={{ width: 90, padding: '8px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13 }}
            />
          </div>
        </div>

        {/* % a redistribuir */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
            Quanto redistribuir (% do saldo disponível):
          </label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="number"
              value={pctFrac}
              onChange={e => setPctFrac(Math.min(100, Math.max(0, +e.target.value)))}
              min={0}
              max={100}
              style={{ width: 100, padding: '8px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13 }}
            />
            <span style={{ fontSize: 12, color: '#6b7280' }}>% → {fmtR(valorRedistribuir)}</span>
            <button
              onClick={() => setPctFrac(100)}
              style={{ marginLeft: 'auto', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 6, padding: '4px 10px', fontSize: 11, cursor: 'pointer' }}
            >
              Tudo
            </button>
          </div>
        </div>

        {/* Observação */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 }}>
            Observação (opcional):
          </label>
          <input
            type="text"
            value={obs}
            onChange={e => setObs(e.target.value)}
            placeholder="Motivo da redistribuição"
            style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, boxSizing: 'border-box' }}
          />
        </div>

        {erro && (
          <div style={{ background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '8px 12px', fontSize: 12, marginBottom: 12 }}>
            {erro}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{ background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db', borderRadius: 8, padding: '9px 18px', fontSize: 13, cursor: 'pointer' }}
          >
            Cancelar
          </button>
          <button
            onClick={handleConfirmar}
            disabled={salvando}
            style={{ background: '#1e40af', color: '#fff', border: 'none', borderRadius: 8, padding: '9px 20px', fontSize: 13, fontWeight: 600, cursor: salvando  'not-allowed' : 'pointer', opacity: salvando  0.7 : 1 }}
          >
            {salvando  'Redistribuindo...' : 'Confirmar'}
          </button>
        </div>
      </div>
    </div>
  )
}
