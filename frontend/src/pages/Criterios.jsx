import { useEffect, useState } from 'react'
import {
  getCriterios, getCriterioTipos, atualizarCriterio, seedCriterios, avaliarCriterio,
} from '../api'

const C = {
  wrap: { padding: 24, maxWidth: 1200, margin: '0 auto' },
  h1: { fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 },
  sub: { color: '#6b7280', fontSize: 13, marginTop: 4 },
  card: { background: 'white', border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, marginTop: 16 },
  btn: { background: '#1d4ed8', color: 'white', border: 'none', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  btnGhost: { background: 'white', color: '#1d4ed8', border: '1px solid #1d4ed8', borderRadius: 6, padding: '5px 9px', cursor: 'pointer', fontSize: 12 },
  input: { padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13 },
  th: { textAlign: 'left', padding: '8px 10px', fontSize: 11, color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #e5e7eb' },
  td: { padding: '8px 10px', fontSize: 13, borderBottom: '1px solid #f3f4f6' },
}

export default function Criterios() {
  const [criterios, setCriterios] = useState([])
  const [tipos, setTipos] = useState([])
  const [msg, setMsg] = useState('')
  const [aval, setAval] = useState({})  // codigo_eap -> resultado

  const carregar = async () => {
    const [cs, ts] = await Promise.all([getCriterios(), getCriterioTipos()])
    setCriterios(cs); setTipos(ts)
  }
  useEffect(() => { carregar() }, [])

  const seed = async () => {
    const r = await seedCriterios('MANUAL')
    setMsg(`Seed: ${r.criados} critério(s) criado(s), ${r.ja_existentes} já existiam.`)
    await carregar()
  }

  const mudarTipo = async (c, tipo) => {
    await atualizarCriterio(c.codigo_eap, {
      codigo_eap: c.codigo_eap, descricao: c.descricao, tipo_criterio: tipo,
      peso: c.peso, evidencia_obrigatoria: c.evidencia_obrigatoria, ativo: c.ativo,
    })
    await carregar()
  }

  const avaliar = async (c) => {
    const r = await avaliarCriterio(c.codigo_eap)
    setAval(prev => ({ ...prev, [c.codigo_eap]: r }))
  }

  const tipoInfo = (t) => tipos.find(x => x.tipo === t)

  return (
    <div style={C.wrap}>
      <h1 style={C.h1}>Matriz de Critérios de Medição</h1>
      <div style={C.sub}>
        Cada item da EAP possui seu critério. O <b>tipo</b> define a estratégia de medição
        (parametrizável, reutilizável em outros contratos). Critérios com fonte ainda não
        integrada aparecem como <i>pendentes</i>.
      </div>

      <div style={C.card}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button style={C.btn} onClick={seed}>Gerar critérios a partir da EAP</button>
          {msg && <span style={{ fontSize: 13, color: '#166534' }}>{msg}</span>}
          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#6b7280' }}>{criterios.length} critério(s)</span>
        </div>
      </div>

      <div style={C.card}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={C.th}>EAP</th><th style={C.th}>Descrição</th>
              <th style={C.th}>Tipo de critério</th><th style={C.th}>Peso</th>
              <th style={C.th}>Avaliação</th><th style={C.th}></th>
            </tr>
          </thead>
          <tbody>
            {criterios.map(c => {
              const r = aval[c.codigo_eap]
              const info = tipoInfo(c.tipo_criterio)
              return (
                <tr key={c.codigo_eap}>
                  <td style={C.td}><b>{c.codigo_eap}</b></td>
                  <td style={C.td}>{c.descricao}</td>
                  <td style={C.td}>
                    <select style={C.input} value={c.tipo_criterio} onChange={e => mudarTipo(c, e.target.value)}>
                      {tipos.map(t => (
                        <option key={t.tipo} value={t.tipo}>
                          {t.tipo}{t.implementado  '' : ' (pendente)'}
                        </option>
                      ))}
                    </select>
                    {info && !info.implementado &&
                      <div style={{ fontSize: 11, color: '#b45309', marginTop: 2 }}>fonte pendente</div>}
                  </td>
                  <td style={C.td}>{c.peso}</td>
                  <td style={C.td}>
                    {r  (
                      <span style={{ fontSize: 12 }}>
                        {r.manual  <i>manual</i>
                          : r.fonte_pendente  <span style={{ color: '#b45309' }}>pendente</span>
                          : <b>{(r.pct * 100).toFixed(1)}%</b>}
                        {r.evidencias?.length > 0 && <span style={{ color: '#6b7280' }}> · {r.evidencias[0]}</span>}
                      </span>
                    ) : <span style={{ color: '#9ca3af', fontSize: 12 }}>—</span>}
                  </td>
                  <td style={C.td}><button style={C.btnGhost} onClick={() => avaliar(c)}>Avaliar</button></td>
                </tr>
              )
            })}
            {criterios.length === 0 && <tr><td style={C.td} colSpan={6}>Nenhum critério. Gere a partir da EAP acima.</td></tr>}
          </tbody>
        </table>
      </div>

      <div style={C.card}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>Catálogo de tipos</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {tipos.map(t => (
            <div key={t.tipo} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: '8px 12px', minWidth: 220 }}>
              <div style={{ fontWeight: 600, fontSize: 13 }}>
                {t.tipo} {t.implementado
                   <span style={{ color: '#166534', fontSize: 11 }}>● ativo</span>
                  : <span style={{ color: '#b45309', fontSize: 11 }}>● pendente</span>}
              </div>
              <div style={{ fontSize: 12, color: '#6b7280' }}>{t.descricao}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
