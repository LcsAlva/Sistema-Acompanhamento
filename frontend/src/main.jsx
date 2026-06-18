import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App'

// Cliente React Query com defaults conservadores para o ambiente de obra:
// — staleTime alto reduz refetch quando o usuário navega entre páginas
// — retry com backoff curto melhora UX em rede WiFi instável da obra
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,         // 30s — semanas e tarefas mudam pouco
      gcTime: 5 * 60_000,        // 5 min em cache antes de descartar
      retry: 2,
      retryDelay: (i) => Math.min(1000 * 2 ** i, 5000),
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)
