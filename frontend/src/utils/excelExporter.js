// Exportador Excel da Programação Semanal QPROG.
// Extraído de GerarPdf.jsx para reduzir o god component e permitir testes
// unitários da geração de planilhas sem renderizar React.
//
// Uso:
//   import { exportarExcelQprog } from '../utils/excelExporter'
//   exportarExcelQprog({ semanaParam, semanaObj, ... })
//
// O dynamic import de `xlsx-js-style` mantém o bundle inicial leve — a lib
// (~600 KB) só é carregada quando o usuário clica em "Exportar Excel".

import { fmtDate } from './formatters'
import { buildWbsRows } from './wbsTree'

export async function exportarExcelQprog({
  semanaParam,
  semanaObj,
  semanaAntObj,
  semanaAtualIdx,
  indAtual,
  indAnt,
  indProx1,
  indProx2,
  semanaProx1,
  semanaProx2,
  textos,
  qprogData,
  semanas,
}) {
  const mod = await import('xlsx-js-style')
  const XLSX = mod.default

  // ── Constantes de layout ───────────────────────────────────────────────
  // 14 colunas: Item, ID, Nome, Dur, %, Início LB, Término LB,
  //             Início Prog., Término Prog., Disc, Sup, Área, Sem, Obs
  const NC   = 14
  // Larguras: A=item, B=id, C=nome, D=dur, E=%, F-G=LB, H-I=Programado,
  //           J=disc, K=sup, L=area, M=sem, N=obs
  // Notas:
  //  - H/I largas o bastante para "Início Programado" / "Término Programado"
  //    quebrar em duas linhas sem cortar.
  //  - L=22 dá espaço para "Alvenaria, Revestimentos e Divisórias" em 2 linhas.
  const COL_W = [7, 14, 36, 5, 6, 12, 12, 15, 15, 14, 13, 22, 8, 26]
  const COL_H = ['Item','ID Atividade','Nome da Atividade','Dur.','%','Início LB','Término LB','Início Programado','Término Programado','Disciplina','Supervisor','Área','Semana','Observações ETM']

  // ── Helpers genéricos ─────────────────────────────────────────────────
  const mkSheet = (nc) => {
    const rows=[], rst=[], rh=[], mrg=[]
    let R=0
    const pad = (cells) => cells.length<nc  [...cells,...Array(nc-cells.length).fill('')] : cells
    const addRow = (cells,h=14) => { rows.push(pad(cells)); rh.push({hpt:h}); return R++ }
    const sty = (r,c,s) => { if(!rst[r])rst[r]={}; rst[r][c]=s }
    const mrgR = (r1,c1,r2,c2) => mrg.push({s:{r:r1,c:c1},e:{r:r2,c:c2}})
    const build = () => {
      const ws=XLSX.utils.aoa_to_sheet(rows)
      rst.forEach((cols,r)=>{ if(!cols)return; Object.entries(cols).forEach(([c,s])=>{ const ref=XLSX.utils.encode_cell({r,c:+c}); if(!ws[ref])ws[ref]={t:'s',v:''}; ws[ref].s=s }) })
      ws['!merges']=mrg; ws['!rows']=rh
      return ws
    }
    return { addRow, sty, mrgR, build }
  }

  const blk = { style:'thin', color:{rgb:'000000'} }
  const box = { top:blk, bottom:blk, left:blk, right:blk }
  const bdr = { top:{style:'thin',color:{rgb:'BBBBBB'}}, bottom:{style:'thin',color:{rgb:'BBBBBB'}}, left:{style:'thin',color:{rgb:'BBBBBB'}}, right:{style:'thin',color:{rgb:'BBBBBB'}} }
  const cen = (extra={}) => ({ horizontal:'center', vertical:'center', ...extra })
  const lft = (extra={}) => ({ horizontal:'left',   vertical:'center', ...extra })

  // ── Cabeçalho ETM (4 linhas, igual ao PDF) ────────────────────────────
  const addEtmHeader = ({addRow,sty,mrgR}, nc, folha) => {
    // Layout dinâmico: cols 0-1 = logo ETM; cols 2..(nc-4) = título;
    // cols (nc-3)..(nc-1) = bloco direito (Semana / Início / Fim / Folha)
    const RIGHT_START = nc - 3
    const TITLE_END = nc - 4
    const padTo = (cells, n) => cells.length < n  [...cells, ...Array(n - cells.length).fill('')] : cells
    const rightLine = (label) => {
      const arr = Array(nc).fill('')
      arr[RIGHT_START] = label
      return arr
    }
    const h0=addRow(padTo(['ETM\nEngenharia','','RECAP - REVAMP - URFCC - CALDEIRA DE CO - EPC'], nc).map((v,i)=> i===RIGHT_START?`Semana: ${semanaParam}`:v), 16)
    const h1=addRow(padTo(['','','PROGRAMAÇÃO SEMANAL DOS SERVIÇOS'], nc).map((v,i)=> i===RIGHT_START?`Início: ${fmtDate(semanaObj?.data_inicio)}`:v), 24)
    const h2=addRow(rightLine(`Fim: ${fmtDate(semanaObj?.data_fim)}`), 16)
    const h3=addRow(rightLine(`Folha ${folha}`), 16)

    mrgR(h0,0,h3,1)                       // ETM (4 linhas x 2 cols)
    mrgR(h0,2,h0,TITLE_END)                // RECAP
    mrgR(h1,2,h3,TITLE_END)                // PROGRAMAÇÃO
    mrgR(h0,RIGHT_START,h0,nc-1)           // Semana
    mrgR(h1,RIGHT_START,h1,nc-1)           // Início
    mrgR(h2,RIGHT_START,h2,nc-1)           // Fim
    mrgR(h3,RIGHT_START,h3,nc-1)           // Folha

    // Bloco esquerdo (logo ETM): aplica border:box em TODAS as cols do merge
    sty(h0,0,{font:{bold:true,sz:12,color:{rgb:'063057'}},alignment:cen({wrapText:true}),border:box})
    sty(h0,1,{border:box})
    for (let r=1;r<=3;r++) { sty(r,0,{border:box}); sty(r,1,{border:box}) }

    // Bloco central (RECAP / PROGRAMAÇÃO): bordas em todas as cols dos dois merges
    sty(h0,2,{font:{sz:8.5},alignment:cen(),border:{...box,bottom:blk}})
    for (let c=3;c<=TITLE_END;c++) sty(h0,c,{border:{...box,bottom:blk}})
    sty(h1,2,{font:{bold:true,sz:13},alignment:cen(),border:{...box,top:blk}})
    for (let r=1;r<=3;r++) for (let c=3;c<=TITLE_END;c++) sty(r,c,{border:box})
    // refina cantos verticais do título de 3 linhas (col 2 e TITLE_END recebem left/right)
    for (let r=2;r<=3;r++) sty(r,2,{border:{...box}})
    for (let r=1;r<=3;r++) sty(r,TITLE_END,{border:{...box}})

    // Bloco direito — aplica top+bottom em TODAS as cols do merge para
    // que as linhas horizontais cubram a largura inteira (L até N).
    const bR = (row, fontProps) => {
      // Anchor: texto + alinhamento à esquerda + border esquerda
      sty(row, RIGHT_START, {font:fontProps, alignment:lft({indent:1}), border:{top:blk,bottom:blk,left:blk}})
      // Cells do meio
      for (let c = RIGHT_START + 1; c < nc - 1; c++) {
        sty(row, c, {border:{top:blk,bottom:blk}})
      }
      // Última col: border direita
      sty(row, nc - 1, {border:{top:blk,bottom:blk,right:blk}})
    }
    bR(h0, {bold:true, sz:9})
    bR(h1, {sz:9})
    bR(h2, {sz:9})
    bR(h3, {bold:true, sz:9})
  }

  // ── SHEET 1: QPROG ────────────────────────────────────────────────────
  const sh1 = mkSheet(NC)
  const {addRow:aR1, sty:s1, mrgR:m1} = sh1

  addEtmHeader(sh1, NC, '01/02')
  aR1([], 6)

  // hpt=32 acomoda 2 linhas de header (ex.: "Início\nProgramado") com folga.
  const rH = aR1(COL_H, 32)
  for (let c=0;c<NC;c++) s1(rH,c,{fill:{fgColor:{rgb:'063057'}},font:{bold:true,sz:9,color:{rgb:'FFFFFF'}},alignment:cen({wrapText:true}),border:bdr})

  const SEM_LABELS = ['Semana de Referência','Semana +1','Semana +2']
  const SEM_BG     = ['063057','1A5276','1F618D']
  const WBS_CLR    = ['063057','0A4778','1260A0','1A79C8','1A79C8']
  const WBS_SZ     = [9,8.5,8,8,8]
  const WBS_BD     = [true,true,true,false,false]

  // Observação manual (prog.observacoes) tem prioridade sobre o texto
  // automático; a cor de fundo permanece sinalizando o status.
  const getObs = (prog) => {
    const manual = (prog.observacoes || '').trim()
    if(prog.qreal_concluida) return{text: manual || `Concluída na ${prog.semana_original||semanaParam}`, bg:'D4EDDA'}
    const pct=prog.pct_executado?prog.pct_avanco?0
    if(pct>0&&pct<100) return{text: manual || `Em andamento (${pct}%)`, bg:'FFF3CD'}
    if(prog.adiantada) return{text: manual || `Adiantamento — semana original: ${prog.semana_original||'?'}`, bg:'FAEEDA'}
    return{text: manual, bg:null}
  }

  const getSemCod = (iso) => {
    if(!iso||!semanas?.length) return semanaParam
    for(const s of semanas){if(s.data_inicio&&s.data_fim&&iso>=s.data_inicio&&iso<=s.data_fim)return s.codigo}
    return semanaParam
  }

  qprogData.forEach(({semanaObj:sObj,progs},jIdx)=>{
    if(!progs||!progs.length) return
    const label=SEM_LABELS[jIdx]||sObj?.codigo||''
    const period=sObj?`${sObj.codigo}  •  ${fmtDate(sObj.data_inicio)} a ${fmtDate(sObj.data_fim)}`:''
    const isRef=sObj?.codigo===semanaParam
    const bg=SEM_BG[jIdx]||'063057'
    const sR=aR1([`${label.toUpperCase()}    ${period}${isRef?'    ★ REFERÊNCIA':''}`,...Array(NC-1).fill('')],16)
    m1(sR,0,sR,NC-1)
    const goldThick = {style:'medium',color:{rgb:'FFD700'}}
    const fillBg = {fill:{fgColor:{rgb:bg}}}
    s1(sR,0,{...fillBg,
      font:{bold:true,sz:9.5,color:{rgb:'FFFFFF'}},
      alignment:lft(),
      ...(isRef?{border:{top:goldThick,bottom:goldThick,left:goldThick}}:{})})
    if (isRef) {
      // Borda dourada em todas as células do merge para que a moldura
      // se estenda da primeira até a última coluna.
      for (let c = 1; c < NC - 1; c++) {
        s1(sR, c, {...fillBg, border:{top:goldThick, bottom:goldThick}})
      }
      s1(sR, NC - 1, {...fillBg, border:{top:goldThick, bottom:goldThick, right:goldThick}})
    } else {
      // Sem ref: ainda assim aplica fill em todas as cols pra evitar células brancas
      for (let c = 1; c < NC; c++) s1(sR, c, fillBg)
    }
    buildWbsRows(progs, sObj?.codigo || jIdx).forEach(row=>{
      if(row.type==='wbs'){
        const d=row.depth?0,idx=Math.min(d,WBS_CLR.length-1)
        const wR=aR1([row.label,...Array(NC-1).fill('')],14); m1(wR,0,wR,NC-1)
        s1(wR,0,{fill:{fgColor:{rgb:WBS_CLR[idx]}},font:{bold:WBS_BD[idx],sz:WBS_SZ[idx],color:{rgb:'FFFFFF'}},alignment:lft({indent:d+1})})
      } else if(row.type==='ativ'){
        const{prog,item}=row,t=prog.tarefa||{}
        const pct=prog.qreal_concluida?100:(prog.pct_executado?prog.pct_avanco?0)
        const{text:obsText,bg:obsBG}=getObs(prog)
        const semCod=getSemCod(prog.inicio_prog||prog.inicio_qprog)
        // Cols: item, id, nome, dur, pct, inicio_lb, termino_lb,
        //       inicio_pg, termino_pg, disc, sup, area, sem, obs
        const inicioPg  = prog.inicio_real  || prog.inicio_prog  || prog.inicio_qprog  || t.inicio_atual
        const terminoPg = prog.termino_real || prog.termino_prog || prog.termino_qprog || t.termino_atual
        // Altura aumentada para acomodar texto quebrado em Nome/Área/Obs.
        // Estimativa: ~22pt comporta 2 linhas a 8.5pt.
        const aR=aR1([
          item,
          t.activity_id||'—',
          t.nome||'—',
          t.duracao?'—',
          pct>0?pct+'%':'—',
          fmtDate(t.inicio_lb),
          fmtDate(t.termino_lb),
          fmtDate(inicioPg),
          fmtDate(terminoPg),
          t.disciplina||'—',
          t.supervisor||'—',
          t.area_unidade||'—',
          semCod,
          obsText||'',
        ],28)
        const OBS_COL = NC - 1     // 13
        const NOME_COL = 2
        const AREA_COL = 11
        const DISC_COL = 9
        const DATE_COLS = [5,6,7,8]
        const CENTER_COLS = [0, 3, ...DATE_COLS, NC - 2]  // item, dur, datas, semana
        const WRAP_COLS = [NOME_COL, DISC_COL, AREA_COL, OBS_COL]
        for(let c=0;c<NC;c++){
          const s={border:bdr,font:{sz:8.5},alignment:{vertical:'center'}}
          if(c===1)s.font={sz:8,name:'Courier New'}
          if(CENTER_COLS.includes(c))s.alignment={...s.alignment,horizontal:'center'}
          if(WRAP_COLS.includes(c))s.alignment={...s.alignment,wrapText:true}
          if(c===4){s.alignment={...s.alignment,horizontal:'center'};s.font=pct>=100?{sz:8.5,bold:true,color:{rgb:'3B6D11'}}:pct>0?{sz:8.5,color:{rgb:'BA7517'}}:{sz:8.5,color:{rgb:'999999'}}}
          if(c===OBS_COL&&obsBG)s.fill={fgColor:{rgb:obsBG}}
          s1(aR,c,s)
        }
      } else if(row.type==='sub'){
        const{sub,disc}=row,icon=sub.status==='concluida'?'✓':sub.status==='em_andamento'?'⏳':'–'
        // Cols: ↳, '', descrição, '', icon, '', '' (LB),
        //       inicio_qprog, termino_qprog (Programado), disc, '', '', '', ''
        const sR2=aR1([
          '↳','',sub.descricao||'—','',icon,
          '','',                                // LB vazio para sub
          fmtDate(sub.inicio_qprog),
          fmtDate(sub.termino_qprog),
          disc||'','','','','',
        ],13)
        for(let c=0;c<NC;c++){
          const s={fill:{fgColor:{rgb:'F2F4F7'}},font:{italic:true,sz:8,color:{rgb:'666666'}},border:bdr,alignment:{vertical:'center'}}
          if(c===0||c===4||c===7||c===8)s.alignment={...s.alignment,horizontal:'center'}
          if(c===2)s.alignment={...s.alignment,indent:2}
          s1(sR2,c,s)
        }
      }
    })
  })

  const ws1=sh1.build()
  ws1['!cols']=COL_W.map(w=>({wch:w}))

  // ── SHEET 2: INDICADORES ──────────────────────────────────────────────
  const NC2 = 12
  const sh2 = mkSheet(NC2)
  const {addRow:aR2, sty:s2, mrgR:m2} = sh2

  addEtmHeader(sh2, NC2, '02/02')
  aR2([],6)

  // ── Indicadores ICPROG (anterior) e IPROG (3 semanas) ──────────────────
  // Mesmo modelo do Dashboard/PDF: dois rótulos lado a lado e o ACUM% como
  // razão entre eles. Sem pizza/donut no Excel — o leitor enxerga melhor
  // os números diretamente que tentar reproduzir o gráfico.

  const fmtPctBR = (n) => (Number.isFinite(n)  n : 0).toFixed(2).replace('.', ',') + '%'

  const icQprog = indAnt?.qprog  0
  const icQreal = indAnt?.qreal_concluidas  0
  const icPct   = icQprog > 0  icQreal / icQprog * 100 : 0

  const ipQcron = (indAtual?.qcron  0) + (indProx1?.qcron  0) + (indProx2?.qcron  0)
  const ipQprog = (indAtual?.qprog  0) + (indProx1?.qprog  0) + (indProx2?.qprog  0)
  const ipPct   = ipQcron > 0  ipQprog / ipQcron * 100 : 0

  const codProx = [semanaObj, semanaProx1, semanaProx2]
    .filter(Boolean).map(s => s.codigo).join('/')

  /**
   * Bloco de indicador no Excel:
   *   [-------- TÍTULO (azul) --------]
   *   [LABEL_AZUL ][VALOR][LABEL_VERDE][VALOR]      ACUM XX,XX%
   */
  const addIndicador = ({ subtitulo, descricao, lblAzul, valAzul, lblVerde, valVerde, acumLabel, acumPct }) => {
    // Cabeçalho
    const rS=aR2([`${subtitulo} — ${descricao}`,...Array(NC2-1).fill('')],18); m2(rS,0,rS,NC2-1)
    s2(rS,0,{fill:{fgColor:{rgb:'063057'}},font:{bold:true,sz:10,color:{rgb:'FFFFFF'}},alignment:cen()})

    // Linha de rótulos:  [lblAzul (3 cols)] [valAzul (1)] [lblVerde (3)] [valVerde (1)] [ACUM-LBL (2)] [ACUM-PCT (2)]
    const rL=aR2([lblAzul,'','',String(valAzul),lblVerde,'','',String(valVerde),acumLabel,'',fmtPctBR(acumPct),''],22)
    // Merges
    m2(rL,0,rL,2);  m2(rL,4,rL,6);  m2(rL,8,rL,9);  m2(rL,10,rL,11)
    // Estilos: rótulos
    s2(rL,0,{fill:{fgColor:{rgb:'063057'}},font:{bold:true,sz:9,color:{rgb:'FFFFFF'}},alignment:cen(),border:bdr})
    s2(rL,4,{fill:{fgColor:{rgb:'8DC63F'}},font:{bold:true,sz:9,color:{rgb:'FFFFFF'}},alignment:cen(),border:bdr})
    // Valores grandes
    s2(rL,3,{font:{bold:true,sz:16,color:{rgb:'063057'}},alignment:cen(),border:bdr,fill:{fgColor:{rgb:'FFFFFF'}}})
    s2(rL,7,{font:{bold:true,sz:16,color:{rgb:'3B6D11'}},alignment:cen(),border:bdr,fill:{fgColor:{rgb:'FFFFFF'}}})
    // Badge ACUM
    s2(rL,8,{fill:{fgColor:{rgb:'F0F0EC'}},font:{bold:true,sz:9,color:{rgb:'555555'}},alignment:cen(),border:bdr})
    s2(rL,10,{fill:{fgColor:{rgb:'F0F0EC'}},font:{bold:true,sz:13,color:{rgb:'063057'}},alignment:cen(),border:bdr})
  }

  addIndicador({
    subtitulo: `Semana ${semanaAntObj?.codigo || '—'}`,
    descricao: 'QREAL / QPROG',
    lblAzul: 'IC PROGRAMADO', valAzul: icQprog,
    lblVerde: 'IC REAL',      valVerde: icQreal,
    acumLabel: 'ICPROG- ACUM', acumPct: icPct,
  })
  aR2([],5)
  addIndicador({
    subtitulo: `Semanas ${codProx || '—'}`,
    descricao: 'QPROG / QCRON',
    lblAzul: 'IP PREVISTO',   valAzul: ipQcron,
    lblVerde: 'IP PROGRAMADO', valVerde: ipQprog,
    acumLabel: 'IPROG- ACUM',  acumPct: ipPct,
  })
  aR2([],10)

  const rProjSec=aR2(['PROJEÇÃO — SEMANAS',...Array(NC2-1).fill('')],18); m2(rProjSec,0,rProjSec,NC2-1)
  s2(rProjSec,0,{fill:{fgColor:{rgb:'063057'}},font:{bold:true,sz:10,color:{rgb:'FFFFFF'}},alignment:lft({indent:1})})

  const PH=['Semana','','Período','','','','QCRON','QPROG','QREAL','% Exec.','','']
  const rPH=aR2(PH,16)
  ;[[0,1],[2,5],[6,6],[7,7],[8,8],[9,11]].forEach(([c1,c2])=>{
    m2(rPH,c1,rPH,c2)
    s2(rPH,c1,{fill:{fgColor:{rgb:'063057'}},font:{bold:true,sz:9,color:{rgb:'FFFFFF'}},alignment:cen(),border:bdr})
  })

  const semanasTabela2 = semanas.slice(Math.max(0,semanaAtualIdx-1), semanaAtualIdx+3)
  semanasTabela2.forEach(s=>{
    const isAt=s.codigo===semanaParam, isAnt=s.codigo===semanaAntObj?.codigo
    const isFechada=s.fechada, hasLive=!isFechada&&(s.live_qcron?0)>0
    const pctSnap=s.snap_qprog>0?Math.round(s.snap_qreal/s.snap_qprog*100):null
    const pctLive=s.live_pct_exec?0
    const qcron=isFechada?s.snap_qcron:hasLive?s.live_qcron:'—'
    const qprog=isFechada?s.snap_qprog:hasLive?(s.live_qprog?'—'):'—'
    const qreal=isFechada?s.snap_qreal:hasLive?(s.live_qreal?'—'):'—'
    const pctVal=isFechada&&pctSnap!==null?pctSnap+'%':hasLive?pctLive+'%':'—'
    const cod=s.codigo+(isAt?' ★':(isFechada?' ✓':''))
    const periodo=fmtDate(s.data_inicio)+' a '+fmtDate(s.data_fim)
    const rD=aR2([cod,'',periodo,'','','',String(qcron),String(qprog),String(qreal),pctVal,'',''],14)
    const rowFill=isAt?'EBF2FA':isAnt?'F5F5F5':'FFFFFF'
    ;[[0,1],[2,5],[9,11]].forEach(([c1,c2])=>m2(rD,c1,rD,c2))
    for(let c=0;c<NC2;c++){
      const stl={fill:{fgColor:{rgb:rowFill}},font:{sz:9,bold:isAt},border:bdr,alignment:cen()}
      if(c===0||c===2)stl.alignment=lft()
      s2(rD,c,stl)
    }
  })

  aR2([],8)

  // Justificativas e Marcos (texto livre nos campos do relatório)
  const parseLista = (raw) => {
    try { return JSON.parse(raw||'[]').filter(Boolean) } catch { return [] }
  }
  const just = parseLista(textos?.justificativas_atraso)
  const marc = parseLista(textos?.marcos_observacoes)

  const addListaSecao = (titulo, lista, cor) => {
    if(!lista.length) return
    const rS=aR2([titulo,...Array(NC2-1).fill('')],16); m2(rS,0,rS,NC2-1)
    s2(rS,0,{fill:{fgColor:{rgb:cor}},font:{bold:true,sz:10,color:{rgb:'FFFFFF'}},alignment:lft({indent:1})})
    lista.forEach((txt,i)=>{
      const r=aR2([`${i+1}.`,txt,...Array(NC2-2).fill('')],16); m2(r,1,r,NC2-1)
      s2(r,0,{font:{bold:true,sz:9},border:bdr,alignment:cen()})
      s2(r,1,{font:{sz:9},border:bdr,alignment:lft({wrapText:true})})
    })
    aR2([],6)
  }

  addListaSecao('JUSTIFICATIVAS DE DESVIO', just, 'BA7517')
  addListaSecao('MARCOS / OBSERVAÇÕES',     marc, '3B6D11')

  const ws2=sh2.build()
  ws2['!cols']=[{wch:14},{wch:6},{wch:14},{wch:8},{wch:8},{wch:8},{wch:8},{wch:8},{wch:8},{wch:10},{wch:8},{wch:8}]

  const wb=XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws1, 'Página 1 - QPROG')
  XLSX.utils.book_append_sheet(wb, ws2, 'Página 2 - Indicadores')
  XLSX.writeFile(wb, `QPROG_${semanaParam}.xlsx`)
}
