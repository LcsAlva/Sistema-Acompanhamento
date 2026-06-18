// Hooks React Query para os endpoints mais consultados.
//
// Centralizar aqui evita que cada página gerencie seu próprio fetch+useState
// e dá cache + dedup automáticos:
// — A Sidebar e o Dashboard pedem `getSemanas` ao mesmo tempo Vira 1 request.
// — Mudei a semana atual `useSemana` vira `setQueryData` em vez de refetch.
//
// Uso:
//   const { data: semanas, isLoading } = useSemanas()
//   const { data: ind } = useIndicadores('S_37')

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSemanas, getSemana, getIndicadores, getQcron, getQprog,
  getTextos, saveTextos, getPainel, getSubTarefas,
} from '../api'

// ── Queries ─────────────────────────────────────────────────────────────

export function useSemanas() {
  return useQuery({
    queryKey: ['semanas'],
    queryFn: getSemanas,
  })
}

export function useSemana(codigo) {
  return useQuery({
    queryKey: ['semanas', codigo],
    queryFn: () => getSemana(codigo),
    enabled: !!codigo,
  })
}

export function useIndicadores(codigo) {
  return useQuery({
    queryKey: ['indicadores', codigo],
    queryFn: () => getIndicadores(codigo),
    enabled: !!codigo,
  })
}

export function useQcron(codigo) {
  return useQuery({
    queryKey: ['qcron', codigo],
    queryFn: () => getQcron(codigo),
    enabled: !!codigo,
  })
}

export function useQprog(codigo) {
  return useQuery({
    queryKey: ['qprog', codigo],
    queryFn: () => getQprog(codigo),
    enabled: !!codigo,
  })
}

export function useTextos(codigo) {
  return useQuery({
    queryKey: ['textos', codigo],
    queryFn: () => getTextos(codigo),
    enabled: !!codigo,
  })
}

export function usePainel(codigo) {
  return useQuery({
    queryKey: ['painel', codigo],
    queryFn: () => getPainel(codigo),
    enabled: !!codigo,
  })
}

export function useSubTarefas(progId) {
  return useQuery({
    queryKey: ['sub-tarefas', progId],
    queryFn: () => getSubTarefas(progId),
    enabled: !!progId,
  })
}

// ── Mutations ────────────────────────────────────────────────────────────

export function useSaveTextos(codigo) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => saveTextos(codigo, data),
    onSuccess: (data) => qc.setQueryData(['textos', codigo], data),
  })
}

// ── Helper ──────────────────────────────────────────────────────────────

/** Invalida todas as queries dependentes de uma semana específica
 *  (ex.: após um import ou edição de programação). */
export function invalidarSemana(qc, codigo) {
  qc.invalidateQueries({ queryKey: ['semanas'] })
  if (codigo) {
    qc.invalidateQueries({ queryKey: ['semanas', codigo] })
    qc.invalidateQueries({ queryKey: ['indicadores', codigo] })
    qc.invalidateQueries({ queryKey: ['qcron', codigo] })
    qc.invalidateQueries({ queryKey: ['qprog', codigo] })
    qc.invalidateQueries({ queryKey: ['painel', codigo] })
  }
}
