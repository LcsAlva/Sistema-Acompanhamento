import { useState } from 'react'
import { exportBmExcel } from '../api'
import { useSemana } from '../context/SemanaContext'

const currentDate = new Date()
const currentYear = currentDate.getFullYear()
const currentMonth = String(currentDate.getMonth() + 1).padStart(2, '0')
const years = Array.from({ length: 5 }, (_, index) => currentYear - 2 + index)
const months = [
  { value: '01', label: 'Janeiro' },
  { value: '02', label: 'Fevereiro' },
  { value: '03', label: 'Março' },
  { value: '04', label: 'Abril' },
  { value: '05', label: 'Maio' },
  { value: '06', label: 'Junho' },
  { value: '07', label: 'Julho' },
  { value: '08', label: 'Agosto' },
  { value: '09', label: 'Setembro' },
  { value: '10', label: 'Outubro' },
  { value: '11', label: 'Novembro' },
  { value: '12', label: 'Dezembro' },
]

const selectStyle = {
  border: '1px solid #d0d5dd',
  borderRadius: 6,
  padding: '7px 8px',
  color: '#101828',
  background: 'white',
  fontSize: 12,
}

const sections = [
  {
    title: 'Programação Semanal',
    items: [
      {
        title: 'PDF Programação Semanal',
        description: 'Relatório semanal com programação, indicadores e textos cadastrados.',
        format: 'PDF',
        available: true,
        actionLabel: 'Gerar PDF',
        needsWeek: true,
      },
    ],
  },
  {
    title: 'Avanço Financeiro',
    items: [
      {
        title: 'PDF Avanço Financeiro',
        description: 'Resumo executivo da curva financeira e indicadores EVM.',
        format: 'PDF',
        available: false,
      },
      {
        title: 'Excel Curva S / EVM',
        description: 'Base exportável da curva S financeira e métricas de valor agregado.',
        format: 'Excel',
        available: false,
      },
      {
        title: 'Excel Medição Mensal',
        description: 'Planilha mensal de medição financeira consolidada.',
        format: 'Excel',
        available: false,
      },
      {
        title: 'Excel Pendências',
        description: 'Lista de pendências financeiras para acompanhamento e tratativa.',
        format: 'Excel',
        available: false,
      },
    ],
  },
  {
    title: 'Medição / BM',
    items: [
      {
        title: 'PDF BM Mensal',
        description: 'Boletim mensal de medição para análise, aprovação e arquivo.',
        format: 'PDF',
        available: false,
      },
      {
        title: 'Excel BM Mensal',
        description: 'Exporta o BM da competência com resumo executivo, medição, pendências, curva S/EVM e auditoria.',
        format: 'Excel',
        available: true,
        actionLabel: 'Baixar Excel',
        type: 'bmExcel',
      },
      {
        title: 'Excel Consolidado',
        description: 'Consolidado de medições e boletins para controle gerencial.',
        format: 'Excel',
        available: false,
      },
    ],
  },
  {
    title: 'Documentos',
    items: [
      {
        title: 'Excel Lista de Documentos',
        description: 'Exportação da carteira de documentos de engenharia.',
        format: 'Excel',
        available: false,
      },
    ],
  },
]

export default function Relatorios() {
  const { semanaAtual } = useSemana()
  const [bmAno, setBmAno] = useState(currentYear)
  const [bmMes, setBmMes] = useState(currentMonth)
  const [bmLoading, setBmLoading] = useState(false)
  const [bmMessage, setBmMessage] = useState('')
  const [bmError, setBmError] = useState('')

  const abrirPdfProgramacao = () => {
    if (!semanaAtual?.codigo) return
    window.open(`/pdf/${semanaAtual.codigo}`, '_blank')
  }

  const baixarExcelBm = async () => {
    setBmLoading(true)
    setBmError('')
    setBmMessage('')

    try {
      const response = await exportBmExcel(bmAno, bmMes)
      const blob = new Blob([response.data], {
        type: response.headers?.['content-type'] || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `BM_${bmAno}_${bmMes}.xlsx`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setBmMessage('Arquivo gerado com sucesso.')
    } catch (error) {
      console.error('Falha ao exportar Excel do BM', error)
      setBmError('Não foi possível gerar o Excel do BM. Verifique se o BM existe para essa competência.')
    } finally {
      setBmLoading(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1240, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <span style={{ fontSize: 22 }}>📄</span>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: '#063057' }}>
            Relatórios e Exportações
          </h1>
        </div>
        <p style={{ margin: 0, color: '#667085', fontSize: 14 }}>
          Central de geração de PDFs e arquivos Excel do sistema.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }}>
        {sections.map(section => (
          <section key={section.title}>
            <h2 style={{ margin: '0 0 12px', color: '#344054', fontSize: 15, fontWeight: 700 }}>
              {section.title}
            </h2>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: 14,
            }}>
              {section.items.map(item => {
                const disabledByWeek = item.needsWeek && !semanaAtual?.codigo
                const isBmExcel = item.type === 'bmExcel'
                const disabled = !item.available || disabledByWeek || (isBmExcel && bmLoading)

                return (
                  <ReportCard
                    key={item.title}
                    item={item}
                    disabled={disabled}
                    disabledMessage={disabledByWeek  'Selecione uma semana para gerar o PDF.' : null}
                    onClick={item.needsWeek  abrirPdfProgramacao : isBmExcel  baixarExcelBm : undefined}
                    loading={isBmExcel && bmLoading}
                    successMessage={isBmExcel  bmMessage : ''}
                    errorMessage={isBmExcel  bmError : ''}
                  >
                    {isBmExcel && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: '#475467', fontSize: 11, fontWeight: 700 }}>
                          Ano
                          <select
                            value={bmAno}
                            onChange={e => setBmAno(Number(e.target.value))}
                            disabled={bmLoading}
                            style={selectStyle}
                          >
                            {years.map(year => (
                              <option key={year} value={year}>{year}</option>
                            ))}
                          </select>
                        </label>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: '#475467', fontSize: 11, fontWeight: 700 }}>
                          Mês
                          <select
                            value={bmMes}
                            onChange={e => setBmMes(e.target.value)}
                            disabled={bmLoading}
                            style={selectStyle}
                          >
                            {months.map(month => (
                              <option key={month.value} value={month.value}>{month.label}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                    )}
                  </ReportCard>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

function ReportCard({ item, disabled, disabledMessage, onClick, loading, successMessage, errorMessage, children }) {
  const statusLabel = item.available  'disponível' : 'em breve'
  const buttonLabel = loading  'Gerando...' : item.available  (item.actionLabel || 'Exportar') : 'Em breve'

  return (
    <article style={{
      background: 'white',
      border: '1px solid #e4e7ec',
      borderRadius: 8,
      padding: 16,
      minHeight: 188,
      boxShadow: '0 1px 2px rgba(16,24,40,0.04)',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
        <div>
          <h3 style={{ margin: 0, color: '#101828', fontSize: 15, fontWeight: 700 }}>
            {item.title}
          </h3>
          <p style={{ margin: '8px 0 0', color: '#667085', fontSize: 12, lineHeight: 1.45 }}>
            {item.description}
          </p>
        </div>
        <span style={{
          borderRadius: 999,
          padding: '3px 8px',
          background: item.format === 'PDF'  '#eef4ff' : '#ecfdf3',
          color: item.format === 'PDF'  '#1849a9' : '#027a48',
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
        }}>
          {item.format}
        </span>
      </div>

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {children}

        {disabledMessage && (
          <div style={{ color: '#b54708', background: '#fffaeb', border: '1px solid #fedf89', borderRadius: 6, padding: '8px 10px', fontSize: 12 }}>
            {disabledMessage}
          </div>
        )}
        {errorMessage && (
          <div style={{ color: '#b42318', background: '#fef3f2', border: '1px solid #fecdca', borderRadius: 6, padding: '8px 10px', fontSize: 12 }}>
            {errorMessage}
          </div>
        )}
        {successMessage && !errorMessage && (
          <div style={{ color: '#027a48', background: '#ecfdf3', border: '1px solid #abefc6', borderRadius: 6, padding: '8px 10px', fontSize: 12 }}>
            {successMessage}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{
            borderRadius: 999,
            padding: '3px 8px',
            background: item.available  '#ecfdf3' : '#f2f4f7',
            color: item.available  '#027a48' : '#667085',
            fontSize: 11,
            fontWeight: 700,
            textTransform: 'uppercase',
          }}>
            {statusLabel}
          </span>

          <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            style={{
              border: 'none',
              borderRadius: 6,
              padding: '8px 14px',
              background: disabled  '#d0d5dd' : '#1d4ed8',
              color: disabled  '#667085' : 'white',
              fontSize: 12,
              fontWeight: 700,
              cursor: disabled  'not-allowed' : 'pointer',
            }}
          >
            {buttonLabel}
          </button>
        </div>
      </div>
    </article>
  )
}
