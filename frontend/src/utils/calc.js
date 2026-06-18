// Avaliador de expressões aritméticas simples para campos numéricos.
// Permite que o planejador digite contas no campo de %: "100/3", "50+5",
// "(200/4)*1.5". Aceita vírgula como separador decimal.
//
// Segurança: a regex garante que a string só contém dígitos, operadores
// e parênteses — nenhum identificador é possível, então o Function()
// não consegue chamar nada além de aritmética.

export function evalExpr(raw) {
  if (raw == null) return null
  const s = String(raw).trim().replace(/%/g, '').replace(/,/g, '.')
  if (s === '') return null
  // Só dígitos, ponto, + - * / ( ) e espaço
  if (!/^[\d.+\-*/()\s]+$/.test(s)) return null
  try {
    // eslint-disable-next-line no-new-func
    const v = Function(`"use strict";return(${s})`)()
    return (typeof v === 'number' && isFinite(v))  v : null
  } catch {
    return null
  }
}

// Arredonda para 2 casas decimais apenas para exibicao visual.
export function round2(n) {
  return Math.round((Number(n) || 0) * 100) / 100
}

// Formata um número para exibição em input (até 2 casas, sem zeros à toa).
export function numToInput(n) {
  if (n == null || n === '') return ''
  const v = Number(n)
  if (!isFinite(v)) return ''
  return String(v)
}

/**
 * Limita um percentual ao intervalo [min, max] (padrão 0–100).
 * Usado para auto-ajuste UX: digitar 150 → 100, digitar -5 → 0.
 * Não substitui validação backend — apenas melhora a experiência.
 *
 * @param {number} n   — valor bruto
 * @param {number} lo  — mínimo (padrão 0)
 * @param {number} hi  — máximo (padrão 100)
 * @returns {number}   — valor clampado, sem arredondar casas decimais
 */
export function clampPct(n, lo = 0, hi = 100) {
  const v = Number(n)
  if (!isFinite(v)) return lo
  return Math.min(hi, Math.max(lo, v))
}

/**
 * Retorna true se o número está fora do intervalo percentual permitido.
 */
export function isPctInvalid(n, lo = 0, hi = 100) {
  const v = Number(n)
  if (!isFinite(v)) return true
  return v < lo || v > hi
}
