const STATUS_MAP = {
  concluida:  { bg: '#EAF3DE', color: '#3B6D11', dot: '#639922', label: 'Concluído' },
  andamento:  { bg: '#FAEEDA', color: '#854F0B', dot: '#BA7517', label: 'Em Progresso' },
  programada: { bg: '#E6F1FB', color: '#185FA5', dot: '#185FA5', label: 'Não Iniciado' },
  atrasada:   { bg: '#FCEBEB', color: '#A32D2D', dot: '#E24B4A', label: 'Atrasada' },
}

export default function StatusPill({ status, onClick }) {
  const s = STATUS_MAP[status] || STATUS_MAP.programada
  return (
    <span
      onClick={onClick}
      style={{
        display:'inline-flex', alignItems:'center', gap:3,
        fontSize:10, padding:'2px 7px', borderRadius:10,
        fontWeight:500, whiteSpace:'nowrap',
        background:s.bg, color:s.color,
        cursor: onClick  'pointer' : 'default'
      }}
    >
      <span style={{width:5,height:5,borderRadius:'50%',background:s.dot,display:'inline-block'}}/>
      {s.label}
    </span>
  )
}

export function getStatus(prog, mode = 'qreal') {
  if (!prog) return 'programada'

  if (mode === 'planejamento') {
    // Usa status_atividade direto do P6 (status_code) — apenas os 3 valores existentes
    const s = (prog.status_atividade || '').toLowerCase()
    if (s.includes('conclu')) return 'concluida'
    if (s.includes('progresso') || s.includes('progress')) return 'andamento'
    return 'programada'  // "Não Iniciado" e qualquer outro
  }

  // mode === 'qreal': status baseado no lançamento de QREAL
  if (prog.qreal_concluida || prog.pct_qreal === 100) return 'concluida'
  if (prog.pct_qreal > 0) return 'andamento'
  const hoje = new Date().toISOString().split('T')[0]
  if (prog.termino_prog && prog.termino_prog.slice(0, 10) < hoje && (prog.pct_avanco || 0) < 100) return 'atrasada'
  return 'programada'
}
