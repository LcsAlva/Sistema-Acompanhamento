// Cabeçalho ETM — três colunas com borda, repetido em todas as folhas do PDF.
// Extraído de GerarPdf.jsx no esforço de decompor o god component.

import etmLogo from '../../assets/etm_logo.png'
import { fmtDate } from '../../utils/formatters'

export default function EtmHeader({ semanaObj, folha }) {
  const cellBase = {
    border: '1px solid #000',
    padding: '4px 8px',
    verticalAlign: 'middle',
  }
  return (
    <table style={{width:'100%',borderCollapse:'collapse',fontFamily:'system-ui,sans-serif',marginBottom:8}}>
      <tbody>
        <tr>
          {/* Logo */}
          <td style={{...cellBase, width:'15%', textAlign:'center', padding:'6px'}}>
            <img
              src={etmLogo}
              alt="ETM Engenharia"
              style={{display:'block', margin:'0 auto', maxWidth:'100%', maxHeight:60, objectFit:'contain'}}
            />
          </td>

          {/* Título central */}
          <td style={{...cellBase, width:'60%', textAlign:'center'}}>
            <div style={{fontSize:11, fontWeight:700, color:'#000', letterSpacing:'0.02em'}}>
              RECAP - REVAMP - URFCC - CALDEIRA DE CO - EPC
            </div>
            <div style={{fontSize:14, fontWeight:700, color:'#000', marginTop:4, letterSpacing:'0.02em'}}>
              PROGRAMAÇÃO SEMANAL DOS SERVIÇOS
            </div>
          </td>

          {/* Info semana */}
          <td style={{...cellBase, width:'25%', padding:0}}>
            <table style={{width:'100%', borderCollapse:'collapse'}}>
              <tbody>
                <tr>
                  <td style={{borderBottom:'1px solid #000', padding:'3px 8px', fontSize:10, fontWeight:600, textAlign:'center'}}>
                    Semana: {semanaObj?.codigo || '—'}
                  </td>
                </tr>
                <tr>
                  <td style={{borderBottom:'1px solid #000', padding:'3px 8px', fontSize:10, textAlign:'center'}}>
                    Início: {fmtDate(semanaObj?.data_inicio)}
                  </td>
                </tr>
                <tr>
                  <td style={{borderBottom:'1px solid #000', padding:'3px 8px', fontSize:10, textAlign:'center'}}>
                    Fim: {fmtDate(semanaObj?.data_fim)}
                  </td>
                </tr>
                <tr>
                  <td style={{padding:'3px 8px', fontSize:10, fontWeight:600, textAlign:'center'}}>
                    Folha {folha}
                  </td>
                </tr>
              </tbody>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  )
}
