import { Factory } from 'lucide-react'

// Stub das abas de Produção ainda não implementadas (entrega Dashboard-first).
export default function ProducaoEmBreve({ titulo, descricao }) {
  return (
    <div className="placeholder-page">
      <div className="placeholder-panel">
        <span className="executive-icon"><Factory size={22} /></span>
        <div>
          <span className="eyebrow">{'Produção'}</span>
          <h2>{titulo}</h2>
          <p>{descricao || 'Aba em construção. Os dados já existem no XER importado e serão detalhados aqui na próxima etapa.'}</p>
        </div>
      </div>
    </div>
  )
}
