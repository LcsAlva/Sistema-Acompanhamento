import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getIndicadores, getTextos, getSemana, getQprog, getQcron } from '../api'
import { useSemana } from '../context/SemanaContext'
import { logError } from '../utils/errors'
import { exportarExcelQprog } from '../utils/excelExporter'
import TabelaQprog from './relatorio/TabelaQprog'
import SecaoIndicadores from './relatorio/SecaoIndicadores'

export default function GerarPdf() {
  const { semana: semanaParam } = useParams()
  const navigate = useNavigate()
  const { semanas } = useSemana()
  const [semanaAtualIdx, setSemanaAtualIdx] = useState(-1)
  const [semanaObj, setSemanaObj] = useState(null)
  const [semanaAntObj, setSemanaAntObj] = useState(null)
  const [indAtual, setIndAtual] = useState(null)
  const [indAnt, setIndAnt] = useState(null)
  const [indProx1, setIndProx1] = useState(null)
  const [indProx2, setIndProx2] = useState(null)
  const [textos, setTextos] = useState(null)
  const [clima, setClima] = useState(null)
  const [loading, setLoading] = useState(true)
  // qprogData: array de { semanaObj, progs[] } para as 4 semanas da janela
  const [qprogData, setQprogData] = useState([])
  const [tipo, setTipo] = useState('completo')

  useEffect(() => {
    if (!semanaParam || !semanas.length) return
    const idx = semanas.findIndex(s => s.codigo === semanaParam)
    setSemanaAtualIdx(idx)
    const atual = semanas[idx] || null
    const ant = idx > 0  semanas[idx - 1] : null
    setSemanaObj(atual)
    setSemanaAntObj(ant)

    // Janela de 3 semanas: S, S+1, S+2
    // Todas usam QPROG — apenas atividades manualmente selecionadas na programação
    const janela = [0, 1, 2]
      .map(offset => ({ semanaObj: semanas[idx + offset] }))
      .filter(j => j.semanaObj)

    // Indicadores da janela de 3 semanas (atual + 2 à frente) — usados
    // pelo donut IPROG agregado da Folha 02/02.
    const prox1 = semanas[idx + 1] || null
    const prox2 = semanas[idx + 2] || null

    const promises = [
      getIndicadores(semanaParam).catch(logError('GerarPdf:getIndicadores', null)),
      ant  getIndicadores(ant.codigo).catch(logError('GerarPdf:getIndicadoresAnt', null)) : Promise.resolve(null),
      getTextos(semanaParam).catch(logError('GerarPdf:getTextos', null)),
      prox1  getIndicadores(prox1.codigo).catch(logError('GerarPdf:getIndProx1', null)) : Promise.resolve(null),
      prox2  getIndicadores(prox2.codigo).catch(logError('GerarPdf:getIndProx2', null)) : Promise.resolve(null),
      ...janela.map(({ semanaObj: s }) =>
        getQprog(s.codigo)
          .catch(logError(`GerarPdf:getQprog(${s.codigo})`, []))
          .then(progs => ({ semanaObj: s, progs: progs || [] }))
      ),
    ]
    Promise.all(promises).then(([iAt, iAn, txt, iP1, iP2, ...janelaData]) => {
      setIndAtual(iAt)
      setIndAnt(iAn)
      setIndProx1(iP1)
      setIndProx2(iP2)
      setTextos(txt)
      // Clima vem do campo condicoes_climaticas salvo nos textos
      try {
        const climaSalvo = JSON.parse(txt?.condicoes_climaticas || 'null')
        setClima(Array.isArray(climaSalvo) && !climaSalvo[0]?.erro  climaSalvo : null)
      } catch { setClima(null) }
      setQprogData(janelaData)
      setLoading(false)
    })
  }, [semanaParam, semanas])

  const semanasTabela = semanas.slice(
    Math.max(0, semanaAtualIdx - 1),
    semanaAtualIdx + 3
  )

  const exportarExcel = () => {
    exportarExcelQprog({
      semanaParam, semanaObj, semanaAntObj, semanaAtualIdx,
      indAtual, indAnt, indProx1, indProx2,
      semanaProx1: semanas[semanaAtualIdx + 1] || null,
      semanaProx2: semanas[semanaAtualIdx + 2] || null,
      textos, qprogData, semanas,
    }).catch(e => {
      console.error('Falha ao exportar Excel', e)
      alert('Erro ao gerar Excel — veja o console para detalhes.')
    })
  }

  if (loading) {
    return (
      <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh',fontFamily:'system-ui',color:'#555'}}>
        Carregando dados para o relatório...
      </div>
    )
  }

  return (
    <>
      {/* Toolbar — não aparece na impressão */}
      <div className="no-print" style={{
        position:'fixed', top:0, left:0, right:0, zIndex:100,
        background:'#063057', color:'white', padding:'10px 20px',
        display:'flex', alignItems:'center', gap:12
      }}>
        <span style={{fontWeight:500,fontSize:13}}>Prévia do Relatório — {semanaParam}</span>

        {/* Toggle RESUMIDA / COMPLETO */}
        <div style={{display:'flex',background:'rgba(255,255,255,0.1)',borderRadius:6,overflow:'hidden',border:'0.5px solid rgba(255,255,255,0.25)'}}>
          {['resumida','completo'].map(t => (
            <button
              key={t}
              onClick={() => setTipo(t)}
              style={{
                background: tipo === t  '#8dc63f' : 'transparent',
                color: 'white',
                border: 'none',
                padding: '5px 14px',
                fontSize: 11,
                fontWeight: tipo === t  600 : 400,
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {t}
            </button>
          ))}
        </div>

        <select
          value={semanaParam}
          onChange={e => navigate(`/pdf/${e.target.value}`)}
          style={{fontSize:11,padding:'3px 8px',borderRadius:4,border:'none',color:'#063057',fontWeight:500,minWidth:160}}
        >
          {semanas.map(s => (
            <option key={s.codigo} value={s.codigo}>
              {s.codigo} — {s.data_inicio?.split('-').slice(1).reverse().join('/')} a {s.data_fim?.split('-').slice(1).reverse().join('/')}
            </option>
          ))}
        </select>
        <button
          onClick={() => window.print()}
          style={{background:'#8dc63f',color:'white',border:'none',borderRadius:6,padding:'6px 18px',fontSize:12,fontWeight:500,cursor:'pointer',marginLeft:'auto'}}
        >
          ⬇ Imprimir / Salvar PDF
        </button>
        <button
          onClick={exportarExcel}
          style={{background:'#1d6f42',color:'white',border:'none',borderRadius:6,padding:'6px 18px',fontSize:12,fontWeight:500,cursor:'pointer'}}
        >
          ⬇ Baixar Excel
        </button>
        <button
          onClick={() => navigate('/dashboard')}
          style={{background:'rgba(255,255,255,0.15)',color:'white',border:'0.5px solid rgba(255,255,255,0.3)',borderRadius:6,padding:'6px 14px',fontSize:12,cursor:'pointer'}}
        >
          ← Voltar
        </button>
      </div>

      {/* Folha 01/02 — Programação dos Serviços (paisagem) */}
      <div className="pdf-page pdf-landscape" style={{paddingTop:0}}>
        <div style={{fontFamily:'system-ui,sans-serif',width:'100%',padding:'8px 0',fontSize:10,color:'#111',lineHeight:1.35}}>
          <TabelaQprog
            semanaParam={semanaParam}
            semanaObj={semanaObj}
            semanas={semanas}
            qprogData={qprogData}
            tipo={tipo}
            folha="01/02"
          />
        </div>
      </div>

      {/* Folha 02/02 — Indicadores / Dashboard (apenas no modo COMPLETO) */}
      {tipo === 'completo' && (
        <SecaoIndicadores
          semanaParam={semanaParam}
          semanaObj={semanaObj}
          semanaAntObj={semanaAntObj}
          indAtual={indAtual}
          indAnt={indAnt}
          indProx1={indProx1}
          indProx2={indProx2}
          semanaProx1={semanas[semanaAtualIdx + 1] || null}
          semanaProx2={semanas[semanaAtualIdx + 2] || null}
          textos={textos}
          clima={clima}
          semanasTabela={semanasTabela}
        />
      )}

      <style>{`
        * {
          -webkit-print-color-adjust: exact !important;
          print-color-adjust: exact !important;
          color-adjust: exact !important;
        }
        @media print {
          .no-print { display: none !important; }
          .pdf-page { padding-top: 0 !important; }
          .pdf-page-break { page-break-before: always; }
          body { background: white !important; }
          @page { size: A4 landscape; margin: 0.4cm 0.5cm; }
          /* Faz o cabeçalho da tabela de atividades repetir em cada página impressa */
          .qprog-table thead { display: table-header-group; }
          .qprog-table tfoot { display: table-footer-group; }
          .qprog-table tr { page-break-inside: avoid; }
        }
        @media screen {
          .pdf-page-break { border-top: 3px dashed #ccc; margin-top: 40px; padding-top: 40px; }
          .pdf-landscape { max-width: 1400px; margin: 0 auto; }
        }
      `}</style>
    </>
  )
}
