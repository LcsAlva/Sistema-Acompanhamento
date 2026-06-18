// Utilitário central para logar erros de chamadas à API.
// Substitui os .catch(() => {}) silenciosos espalhados pelo código,
// preservando o fallback (sem quebrar a tela) mas registrando o
// problema no console para diagnóstico.

/**
 * Loga um erro com contexto e retorna um valor de fallback.
 * Uso: .catch(logError('Dashboard:getIndicadores', null))
 *
 * @param {string} contexto  Identificador curto de onde o erro ocorreu.
 * @param {*} fallback        Valor retornado para não quebrar o .then seguinte.
 */
export function logError(contexto, fallback = null) {
  return (err) => {
    const status = err?.response?.status
    const detalhe = err?.response?.data?.detail || err?.message || err
    // eslint-disable-next-line no-console
    console.error(`[${contexto}]`, status  `HTTP ${status}` : '', detalhe)
    return fallback
  }
}
