// Utilitários compartilhados de formatação e cálculo.
// Centralizados para eliminar duplicação entre páginas
// (GerarPdf, Dashboard, MontarQprog, LancarQreal, etc.).

/**
 * Formata uma data ISO (YYYY-MM-DD) para DD/MM/YYYY.
 * Retorna '—' quando vazio/nulo.
 */
export function fmtDate(d) {
  if (!d) return '—'
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}

/**
 * Formata o período de uma semana como "DD/MM/YYYY a DD/MM/YYYY".
 * Aceita objeto com { data_inicio, data_fim }.
 */
export function fmtPeriodo(s) {
  if (!s) return ''
  return `${fmtDate(s.data_inicio)} a ${fmtDate(s.data_fim)}`
}

/**
 * Calcula o percentual de execução da semana (concluídas / programado).
 * Aceita o objeto de indicadores retornado pelo backend.
 */
export function execPct(ind) {
  if (!ind || !ind.qprog) return 0
  return Math.round((ind.qreal_concluidas / ind.qprog) * 100)
}

/**
 * Retorna a cor associada ao percentual de execução:
 *  >= 100%  → verde
 *  >= 70%   → laranja
 *  < 70%    → vermelho
 */
export function execColor(pct) {
  if (pct >= 100) return '#3B6D11'
  if (pct >= 70) return '#BA7517'
  return '#A32D2D'
}
