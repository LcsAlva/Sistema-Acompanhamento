import { createContext, useContext, useState, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSemanas } from '../hooks/useApi'

const SemanaContext = createContext(null)

const sortSemanas = (data) =>
  [...data].sort((a, b) => {
    const n = (s) => parseInt(s.codigo.replace('S_', '')) || 0
    return n(a) - n(b)
  })

const escolherSemanaAtual = (sorted) => {
  if (!sorted.length) return null
  const hoje = new Date().toISOString().split('T')[0]
  return sorted.find((s) => s.data_inicio <= hoje && s.data_fim >= hoje)
      || sorted[sorted.length - 1]
}

export function SemanaProvider({ children }) {
  const qc = useQueryClient()
  const { data, isLoading } = useSemanas()
  const [override, setOverride] = useState(null)

  const semanas = useMemo(() => sortSemanas(data || []), [data])
  const auto = useMemo(() => escolherSemanaAtual(semanas), [semanas])
  const semanaAtual = override || auto

  // refetchSemanas é mantido para compatibilidade com o código antigo
  // (Importacao, fechar/reabrir semana). Encapsula o invalidate do RQ.
  const refetchSemanas = () => qc.invalidateQueries({ queryKey: ['semanas'] })

  return (
    <SemanaContext.Provider value={{
      semanas,
      semanaAtual,
      setSemanaAtual: setOverride,
      loading: isLoading,
      refetchSemanas,
    }}>
      {children}
    </SemanaContext.Provider>
  )
}

export const useSemana = () => useContext(SemanaContext)
