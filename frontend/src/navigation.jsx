import {
  CalendarRange,
  Factory,
  FileBarChart,
  FileText,
  Landmark,
  LayoutDashboard,
  Network,
  Receipt,
  Settings,
  Wrench,
} from 'lucide-react'

export function buildNavigation({ codigo, ano, mes }) {
  return [
    {
      id: 'executivo',
      label: 'Dashboard Executivo',
      icon: LayoutDashboard,
      to: '/',
      match: ['/', '/executivo'],
      tabs: [],
    },
    {
      id: 'programacao',
      label: 'Programa\u00e7\u00e3o Semanal',
      icon: CalendarRange,
      to: '/dashboard',
      match: ['/dashboard', '/importar', '/qprog', '/qreal', '/textos'],
      tabs: [
        { label: 'Dashboard', to: '/dashboard', match: '/dashboard' },
        { label: 'Importar', to: '/importar', match: '/importar' },
        { label: 'Montar QPROG', to: `/qprog/${codigo}`, match: '/qprog' },
        { label: 'Lan\u00e7ar QREAL', to: `/qreal/${codigo}`, match: '/qreal' },
        { label: 'Textos', to: `/textos/${codigo}`, match: '/textos' },
        { label: 'Gerar PDF', to: `/pdf/${codigo}`, match: '/pdf' },
      ],
    },
    {
      id: 'engenharia',
      label: 'Engenharia',
      icon: FileText,
      to: '/integracao-ld',
      match: ['/integracao-ld', '/documentos', '/conciliacao-sigem', '/motor-medicao', '/analise-revisoes'],
      tabs: [
        { label: 'Documentos', to: '/integracao-ld', match: ['/integracao-ld', '/documentos'] },
        { label: 'Status SIGEM', to: '/conciliacao-sigem', match: '/conciliacao-sigem' },
        { label: 'Medi\u00e7\u00e3o Engenharia', to: '/motor-medicao', match: '/motor-medicao' },
        { label: 'Novos Documentos', to: '/analise-revisoes', match: '/analise-revisoes' },
        { label: 'Controle', to: '/analise-revisoes?view=controle', match: '/analise-revisoes?view=controle' },
      ],
    },
    {
      id: 'producao',
      label: 'Produ\u00e7\u00e3o',
      icon: Factory,
      to: '/producao',
      match: ['/producao', '/painel'],
      tabs: [
        { label: 'Dashboard', to: '/producao', match: '/producao' },
        { label: 'Curva S', to: '/producao/curva-s', match: '/producao/curva-s' },
        { label: 'Lookahead', to: '/producao/lookahead', match: '/producao/lookahead' },
        { label: 'Disciplinas', to: '/producao/disciplinas', match: '/producao/disciplinas' },
        { label: 'Atividades', to: '/producao/atividades', match: '/producao/atividades' },
        { label: 'Avan\u00e7o da Obra', to: '/painel', match: '/painel' },
      ],
    },
    {
      id: 'suportes',
      label: 'Cat\u00e1logo de Suportes',
      icon: Wrench,
      to: '/suportes',
      match: ['/suportes'],
      tabs: [],
    },
    {
      id: 'medicao',
      label: 'Medi\u00e7\u00e3o',
      icon: Receipt,
      to: '/financeiro',
      match: ['/financeiro', '/medicao', '/previsao', '/pendencias', '/eap/gerar-pdf'],
      tabs: [
        { label: 'Dashboard', to: '/financeiro', match: '/financeiro' },
        { label: 'Medi\u00e7\u00e3o Mensal', to: '/medicao', match: '/medicao' },
        { label: 'Previs\u00e3o Mensal', to: '/previsao', match: '/previsao' },
        { label: 'Pend\u00eancias', to: '/pendencias', match: '/pendencias' },
        { label: 'Gerar PDF EAP', to: '/eap/gerar-pdf', match: '/eap/gerar-pdf' },
      ],
    },
    {
      id: 'economica',
      label: 'Gest\u00e3o Econ\u00f4mica',
      icon: Landmark,
      to: '/gestao-economica/dashboard',
      match: ['/gestao-economica'],
      tabs: [
        { label: 'Dashboard Executivo', to: '/gestao-economica/dashboard', match: '/gestao-economica/dashboard' },
        { label: 'Centro de An\u00e1lise', to: '/gestao-economica/centro-analise', match: '/gestao-economica/centro-analise' },
        { label: 'Receitas', to: '/gestao-economica/receitas', match: '/gestao-economica/receitas' },
        { label: 'Custos', to: '/gestao-economica/custos', match: '/gestao-economica/custos' },
        { label: 'Principais Desvios', to: '/gestao-economica/desvios', match: '/gestao-economica/desvios' },
        { label: 'Forecast', to: '/gestao-economica/forecast', match: '/gestao-economica/forecast' },
        { label: 'Forecast Operacional', to: '/gestao-economica/forecast-operacional', match: '/gestao-economica/forecast-operacional' },
        { label: 'Hist\u00f3rico', to: '/gestao-economica/historico', match: '/gestao-economica/historico' },
        { label: 'Resultado', to: '/gestao-economica/resultado', match: '/gestao-economica/resultado' },
        { label: 'Auditoria', to: '/gestao-economica/auditoria', match: '/gestao-economica/auditoria' },
      ],
    },
    {
      id: 'integrada',
      label: 'Gest\u00e3o Integrada',
      icon: Network,
      to: '/gestao-integrada/auditoria',
      match: ['/gestao-integrada'],
      tabs: [
        { label: 'Auditoria', to: '/gestao-integrada/auditoria', match: '/gestao-integrada/auditoria' },
      ],
    },
    {
      id: 'relatorios',
      label: 'Relat\u00f3rios',
      icon: FileBarChart,
      to: '/relatorios',
      match: ['/relatorios', '/relatorio-fotografico'],
      tabs: [
        { label: 'Relat\u00f3rio Semanal', to: '/relatorios', match: '/relatorios' },
        { label: 'Relat\u00f3rio Fotogr\u00e1fico', to: `/relatorio-fotografico/${ano}/${mes}`, match: '/relatorio-fotografico' },
      ],
    },
    {
      id: 'admin',
      label: 'Administra\u00e7\u00e3o',
      icon: Settings,
      to: '/criterios',
      match: ['/criterios', '/eap/mapear'],
      tabs: [
        { label: 'Crit\u00e9rios de Medi\u00e7\u00e3o', to: '/criterios', match: '/criterios' },
        { label: 'Mapear EAP', to: '/eap/mapear', match: '/eap/mapear' },
      ],
    },
  ]
}

export function pathMatches(match, pathname) {
  if (!match) return false
  if (Array.isArray(match)) return match.some(m => pathMatches(m, pathname))
  if (match === '/') return pathname === '/'
  return pathname === match || pathname.startsWith(match + '/')
}

export function getActiveModule(modules, pathname) {
  return modules.find(module => pathMatches(module.match, pathname)) || modules[0]
}
