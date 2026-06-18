// Folha 01/02 do relatório — Tabela QPROG completa
// (cabeçalho ETM + tabela de atividades por semana, com WBS, sub-tarefas
// e observações ETM).
//
// Recebe:
//   - semanaParam: string código da semana de referência
//   - semanaObj:   objeto da semana de referência
//   - semanas:     lista completa de semanas (para resolver semana programada)
//   - qprogData:   array { semanaObj, progs[] } da janela S, S+1, S+2
//   - tipo:        'completo' | 'resumida'
//   - folha:       string ex.: '01/02'

import { fmtDate } from '../../utils/formatters'
import { buildWbsRows } from '../../utils/wbsTree'
import EtmHeader from './EtmHeader'

// Mapeia uma data ISO (YYYY-MM-DD) para o código da semana correspondente.
function semanaFromDate(isoDate, semanas) {
  if (!isoDate || !semanas?.length) return null
  for (const s of semanas) {
    if (!s.data_inicio || !s.data_fim) continue
    if (isoDate >= s.data_inicio && isoDate <= s.data_fim) return s.codigo
  }
  return null
}

export default function TabelaQprog({ semanaParam, semanaObj, semanas, qprogData, tipo, folha }) {
  const isCompleto = tipo === 'completo'

  // Observações automáticas + cor de fundo da célula.
  // A observação digitada pelo planejador (prog.observacoes) tem prioridade
  // — quando preenchida, substitui o texto automático mas mantém a cor de
  // fundo associada ao status para sinalização visual.
  function obsCell(prog) {
    const manual = (prog.observacoes || '').trim()
    if (prog.qreal_concluida) {
      const sem = prog.semana_original || semanaParam
      return { text: manual || `Concluída na ${sem}`, bg: '#d4edda' }
    }
    const pct = prog.pct_executado  prog.pct_avanco  0
    if (pct > 0 && pct < 100) {
      return { text: manual || `Em andamento (${pct}%)`, bg: '#fff3cd' }
    }
    if (prog.adiantada) {
      return { text: manual || `Adiantamento — semana original: ${prog.semana_original || '?'}`, bg: '#faeeda' }
    }
    return { text: manual, bg: null }
  }

  function semanaProgramada(prog) {
    const iso = prog.inicio_prog || prog.inicio_qprog
    return semanaFromDate(iso, semanas) || semanaParam
  }

  // Monta rows para cada semana da janela
  const rows = []
  const SEMANA_LABELS = ['Semana de Referência', 'Semana +1', 'Semana +2']
  const SEMANA_BG     = ['#063057', '#1A5276', '#1F618D']

  qprogData.forEach(({ semanaObj: sObj, progs }, janelaIdx) => {
    if (!progs || progs.length === 0) return
    const label = SEMANA_LABELS[janelaIdx] || sObj?.codigo || ''
    const bg = SEMANA_BG[janelaIdx] || '#063057'
    const periodo = sObj  `${sObj.codigo}  •  ${fmtDate(sObj.data_inicio)} a ${fmtDate(sObj.data_fim)}` : ''
    const isRef = sObj?.codigo === semanaParam
    rows.push({ type:'semana', label, periodo, bg, isRef, key:`sem-header-${sObj?.codigo}` })
    buildWbsRows(progs, sObj?.codigo || janelaIdx).forEach(r => rows.push(r))
  })

  // Colunas — largura em pt (paisagem A4, ~26 cm úteis)
  const COLS = isCompleto
     [
        { key: 'item',        label: 'Item',              w: 60,  align: 'center' },
        { key: 'id',          label: 'ID Atividade',      w: 88,  align: 'left'   },
        { key: 'nome',        label: 'Nome da Atividade', w: null, align: 'left'  },
        { key: 'dur',         label: 'Dur.',              w: 28,  align: 'center' },
        { key: 'pct',         label: '%',                 w: 36,  align: 'center' },
        { key: 'inicio_lb',   label: 'Início LB',         w: 52,  align: 'center' },
        { key: 'termino_lb',  label: 'Término LB',        w: 52,  align: 'center' },
        { key: 'inicio_pg',   label: 'Início Programado', w: 58,  align: 'center' },
        { key: 'termino_pg',  label: 'Término Programado',w: 62,  align: 'center' },
        { key: 'disc',        label: 'Disciplina',        w: 60,  align: 'left'   },
        { key: 'sup',         label: 'Supervisor',        w: 56,  align: 'left'   },
        { key: 'area',        label: 'Área',              w: 64,  align: 'left'   },
        { key: 'sem',         label: 'Semana',            w: 40,  align: 'center' },
        { key: 'obs',         label: 'Observações ETM',   w: 100, align: 'left'   },
      ]
    : [
        { key: 'item',        label: 'Item',              w: 60,  align: 'center' },
        { key: 'id',          label: 'ID Atividade',      w: 88,  align: 'left'   },
        { key: 'nome',        label: 'Nome da Atividade', w: null, align: 'left'  },
        { key: 'dur',         label: 'Dur.',              w: 28,  align: 'center' },
        { key: 'inicio_lb',   label: 'Início LB',         w: 52,  align: 'center' },
        { key: 'termino_lb',  label: 'Término LB',        w: 52,  align: 'center' },
        { key: 'inicio_pg',   label: 'Início Programado', w: 58,  align: 'center' },
        { key: 'termino_pg',  label: 'Término Programado',w: 62,  align: 'center' },
        { key: 'disc',        label: 'Disciplina',        w: 60,  align: 'left'   },
        { key: 'sup',         label: 'Supervisor',        w: 56,  align: 'left'   },
        { key: 'area',        label: 'Área',              w: 64,  align: 'left'   },
        { key: 'sem',         label: 'Semana',            w: 40,  align: 'center' },
        { key: 'obs',         label: 'Observações ETM',   w: 100, align: 'left'   },
      ]

  const colSpan = COLS.length
  const cellBase = {
    border: '0.5px solid #bbb',
    padding: '2px 4px',
    fontSize: 7.5,
    verticalAlign: 'middle',
    wordBreak: 'break-word',
    lineHeight: 1.3,
  }

  return (
    <>
      <EtmHeader semanaObj={semanaObj} folha={folha} />

      <table className="qprog-table" style={{width:'100%', borderCollapse:'collapse', tableLayout:'fixed', marginTop:4}}>
        <colgroup>
          {COLS.map(c => <col key={c.key} style={c.w  {width: c.w} : {}} />)}
        </colgroup>
        <thead>
          <tr>
            {COLS.map(c => (
              <th key={c.key} style={{
                ...cellBase, background: '#063057', color: 'white', fontSize: 7,
                fontWeight: 700, textAlign: 'center', whiteSpace: 'pre-line',
                padding: '3px 3px', border: '0.5px solid #063057',
              }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            if (row.type === 'semana') {
              return (
                <tr key={row.key}>
                  <td colSpan={colSpan} style={{
                    ...cellBase, background: row.bg, color: 'white',
                    fontWeight: 700, fontSize: 8.5, padding: '4px 8px',
                    borderTop: row.isRef  '2px solid #FFD700' : undefined,
                    borderBottom: row.isRef  '2px solid #FFD700' : undefined,
                  }}>
                    <span style={{textTransform:'uppercase', letterSpacing:'0.05em'}}>{row.label}</span>
                    {row.periodo && <span style={{marginLeft:12, fontSize:9, fontWeight:400, opacity:0.85}}>{row.periodo}</span>}
                    {row.isRef && <span style={{marginLeft:8, fontSize:8, fontWeight:700, background:'#FFD700', color:'#000', borderRadius:3, padding:'1px 5px'}}>REFERÊNCIA</span>}
                  </td>
                </tr>
              )
            }
            if (row.type === 'wbs') {
              const WBS_COLORS  = ['#063057','#0A4778','#1260A0','#1A79C8','#1A79C8']
              const WBS_SIZES   = [8.5, 8, 7.5, 7.5, 7.5]
              const WBS_WEIGHTS = [700, 600, 600, 500, 500]
              const depth = row.depth  0
              const bg    = WBS_COLORS[Math.min(depth, WBS_COLORS.length - 1)]
              const fs    = WBS_SIZES[Math.min(depth, WBS_SIZES.length - 1)]
              const fw    = WBS_WEIGHTS[Math.min(depth, WBS_WEIGHTS.length - 1)]
              const pl    = 6 + depth * 10
              return (
                <tr key={row.key}>
                  <td colSpan={colSpan} style={{
                    ...cellBase, background: bg, color: 'white',
                    fontWeight: fw, fontSize: fs, padding: `3px 6px 3px ${pl}px`,
                    textTransform: depth === 0  'uppercase' : 'none',
                    letterSpacing: depth === 0  '0.02em' : 'normal',
                  }}>
                    {row.label}
                  </td>
                </tr>
              )
            }
            if (row.type === 'sub') {
              const { sub, disc } = row
              const statusIcon = sub.status === 'concluida'  '✓' : sub.status === 'em_andamento'  '⏳' : '–'
              const statusColor = sub.status === 'concluida'  '#3B6D11' : sub.status === 'em_andamento'  '#BA7517' : '#999'
              const subCell = { ...cellBase, fontSize: 6.5, fontStyle: 'italic', background: '#f2f4f7', borderColor: '#d0d5dd' }
              return (
                <tr key={row.key}>
                  {COLS.map(c => {
                    let content = '', extra = {}
                    if (c.key === 'item') { content = '↳'; extra = { textAlign: 'center', color: '#555', fontStyle: 'normal' } }
                    else if (c.key === 'nome') { content = sub.descricao || '—'; extra = { paddingLeft: 12 } }
                    else if (c.key === 'pct') { content = statusIcon; extra = { textAlign: 'center', color: statusColor, fontStyle: 'normal', fontWeight: 700 } }
                    else if (c.key === 'inicio_pg') { content = fmtDate(sub.inicio_qprog) || '—'; extra = { textAlign: 'center' } }
                    else if (c.key === 'termino_pg') { content = fmtDate(sub.termino_qprog) || '—'; extra = { textAlign: 'center' } }
                    // Sub-tarefas não têm baseline próprio.
                    else if (c.key === 'inicio_lb' || c.key === 'termino_lb') { content = ''; extra = { textAlign: 'center' } }
                    else if (c.key === 'disc') { content = disc || '—' }
                    return <td key={c.key} style={{ ...subCell, textAlign: c.align, ...extra }}>{content}</td>
                  })}
                </tr>
              )
            }

            // Linha de atividade
            const { prog, item, detalhe } = row
            const t = prog.tarefa || {}
            const pct = prog.qreal_concluida  100 : (prog.pct_executado  prog.pct_avanco  0)
            const { text: obsText, bg: obsBg } = obsCell(prog)
            const semProg = semanaProgramada(prog)
            const render = {
              item,
              id: t.activity_id || '—',
              nome: (
                <>
                  <span>{t.nome || '—'}</span>
                  {detalhe && <div style={{fontSize:7, color:'#888', marginTop:1}}>{detalhe}</div>}
                </>
              ),
              dur: t.duracao  '—',
              pct: pct > 0  `${pct}%` : '—',
              // Linha de base — não muda entre importações.
              inicio_lb:  fmtDate(t.inicio_lb),
              termino_lb: fmtDate(t.termino_lb),
              // Programado — data real (manual) tem prioridade sobre cronograma.
              inicio_pg:  fmtDate(prog.inicio_real  || prog.inicio_prog  || prog.inicio_qprog  || t.inicio_atual),
              termino_pg: fmtDate(prog.termino_real || prog.termino_prog || prog.termino_qprog || t.termino_atual),
              disc: t.disciplina || '—',
              sup: t.supervisor || '—',
              area: t.area_unidade || '—',
              sem: semProg,
              obs: obsText || '',
            }

            return (
              <tr key={row.key} style={{background: 'white'}}>
                {COLS.map(c => {
                  const extra = {}
                  if (c.key === 'obs' && obsBg) extra.background = obsBg
                  if (c.key === 'item') { extra.whiteSpace = 'nowrap'; extra.fontSize = 7.5 }
                  if (c.key === 'id')   { extra.fontFamily = 'ui-monospace, Menlo, Consolas, monospace'; extra.fontSize = 8 }
                  if (c.key === 'pct')  {
                    extra.color = pct >= 100  '#3B6D11' : pct > 0  '#BA7517' : '#999'
                    extra.fontWeight = pct >= 100  700 : 'normal'
                  }
                  return <td key={c.key} style={{ ...cellBase, textAlign: c.align, ...extra }}>{render[c.key]}</td>
                })}
              </tr>
            )
          })}

          {rows.length === 0 && (
            <tr>
              <td colSpan={colSpan} style={{...cellBase, textAlign:'center', padding:'20px', color:'#888', fontStyle:'italic'}}>
                Nenhuma atividade programada para esta semana.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div style={{marginTop:8, display:'flex', justifyContent:'space-between', fontSize:8, color:'#666'}}>
        <span>ETM Engenharia · URFCC — Petrobras</span>
        <span style={{fontWeight:600}}>Página 1</span>
      </div>
    </>
  )
}
