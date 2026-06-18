// Achata uma lista de programações em uma sequência ordenada de linhas
// (cabeçalho WBS, atividade e sub-tarefa) para exibição em tabela.
//
// Usado tanto no render HTML (React) quanto na exportação Excel do
// GerarPdf. Antes havia duas implementações equivalentes lado a lado
// (buildFlat e buildWbsRows) — esta função substitui ambas.
//
// Formato retornado:
//   { type: 'wbs',  label, depth, key }
//   { type: 'ativ', prog, item, key }
//   { type: 'sub',  sub, disc, key }
//
// O parâmetro opcional `semKey` é incorporado aos `key` para garantir
// unicidade quando várias semanas são renderizadas na mesma lista.

export function buildWbsRows(progList, semKey = '') {
  const rows = []
  const useWbs = progList.some(p => p.tarefa?.wbs_path?.length > 1)

  const pushAtivComSubs = (prog, item) => {
    rows.push({
      type: 'ativ',
      prog,
      item,
      key: `ativ-${semKey}-${prog.id}`,
    })
    const disc = prog.tarefa?.disciplina || ''
    ;(prog.sub_tarefas || []).forEach((sub, si) => {
      rows.push({
        type: 'sub',
        sub,
        disc,
        key: `sub-${semKey}-${prog.id}-${si}`,
      })
    })
  }

  if (useWbs) {
    const root = { children: new Map(), progs: [] }
    for (const prog of progList) {
      const levels = (prog.tarefa?.wbs_path || []).slice(1)
      let node = root
      for (const lvl of levels) {
        if (!node.children.has(lvl)) {
          node.children.set(lvl, { children: new Map(), progs: [] })
        }
        node = node.children.get(lvl)
      }
      node.progs.push(prog)
    }

    const flatten = (node, depth, prefix) => {
      let idx = 0
      for (const [name, child] of node.children) {
        idx++
        const num = prefix  `${prefix}.${idx}` : `${idx}`
        const label = depth === 0  `${num}. ${name}` : `${num} ${name}`
        rows.push({
          type: 'wbs',
          label,
          depth,
          key: `wbs-${semKey}-${num}-${name}`,
        })
        flatten(child, depth + 1, num)
      }
      node.progs.forEach((prog, pi) => {
        const item = prefix  `${prefix}.${pi + 1}` : `${pi + 1}`
        pushAtivComSubs(prog, item)
      })
    }
    flatten(root, 0, '')
  } else {
    // Fallback: agrupa por disciplina / área quando não há wbs_path
    const grupos = {}
    for (const prog of progList) {
      const n2 = prog.tarefa?.disciplina || 'Sem Disciplina'
      const n3 = prog.tarefa?.area_unidade || 'Sem Área'
      if (!grupos[n2]) grupos[n2] = {}
      if (!grupos[n2][n3]) grupos[n2][n3] = []
      grupos[n2][n3].push(prog)
    }
    Object.entries(grupos).forEach(([n2, sub], di) => {
      rows.push({
        type: 'wbs',
        label: `${di + 1}. ${n2}`,
        depth: 0,
        key: `wbs-${semKey}-n2-${n2}`,
      })
      Object.entries(sub).forEach(([n3, ps], ai) => {
        rows.push({
          type: 'wbs',
          label: `${di + 1}.${ai + 1} ${n3}`,
          depth: 1,
          key: `wbs-${semKey}-n3-${n2}-${n3}`,
        })
        ps.forEach((prog, pi) => {
          pushAtivComSubs(prog, `${di + 1}.${ai + 1}.${pi + 1}`)
        })
      })
    })
  }

  return rows
}
