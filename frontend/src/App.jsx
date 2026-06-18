import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SemanaProvider } from './context/SemanaContext'
import Layout from './components/Layout'
import DashboardExecutivo from './pages/DashboardExecutivo'
import Dashboard from './pages/Dashboard'
import MontarQprog from './pages/MontarQprog'
import LancarQreal from './pages/LancarQreal'
import TextosRelatorio from './pages/TextosRelatorio'
import Importacao from './pages/Importacao'
import GerarPdf from './pages/GerarPdf'
import Painel from './pages/Painel'
import Financeiro from './pages/Financeiro'
import EconomicoDashboard from './pages/EconomicoDashboard'
import EconomicoCentroAnalise from './pages/EconomicoCentroAnalise'
import EconomicoReceitas from './pages/EconomicoReceitas'
import EconomicoCustos from './pages/EconomicoCustos'
import EconomicoDesvios from './pages/EconomicoDesvios'
import EconomicoForecast from './pages/EconomicoForecast'
import EconomicoForecastOperacional from './pages/EconomicoForecastOperacional'
import EconomicoHistorico from './pages/EconomicoHistorico'
import EconomicoResultado from './pages/EconomicoResultado'
import EconomicoAuditoria from './pages/EconomicoAuditoria'
import PerformanceAuditoria from './pages/PerformanceAuditoria'
import MapearEap from './pages/MapearEap'
import PrevisaoMensal from './pages/PrevisaoMensal'
import LancarAvanco from './pages/LancarAvanco'
import Medicao from './pages/Medicao'
import Documentos from './pages/Documentos'
import RelatorioFotografico from './pages/RelatorioFotografico'
import Pendencias from './pages/Pendencias'
import Relatorios from './pages/Relatorios'
import IntegracaoLD from './pages/IntegracaoLD'
import MotorMedicao from './pages/MotorMedicao'
import AnaliseRevisoes from './pages/AnaliseRevisoes'
import Criterios from './pages/Criterios'
import ConciliacaoSigem from './pages/ConciliacaoSigem'
import GerarPdfEap from './pages/GerarPdfEap'
import Producao from './pages/Producao'
import ProducaoEmBreve from './pages/ProducaoEmBreve'

export default function App() {
  return (
    <SemanaProvider>
      <BrowserRouter>
        <Routes>
          {/* Rota sem sidebar — PDF para impressão */}
          <Route path="/pdf/:semana" element={<GerarPdf />} />

          {/* Rotas com sidebar */}
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardExecutivo />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/qprog/:semana" element={<MontarQprog />} />
            <Route path="/qreal/:semana" element={<LancarQreal />} />
            <Route path="/textos/:semana" element={<TextosRelatorio />} />
            <Route path="/importar" element={<Importacao />} />
            <Route path="/painel" element={<Painel />} />
            <Route path="/financeiro" element={<Financeiro />} />
            <Route path="/gestao-economica" element={<Navigate to="/gestao-economica/dashboard" replace />} />
            <Route path="/gestao-economica/dashboard" element={<EconomicoDashboard />} />
            <Route path="/gestao-economica/centro-analise" element={<EconomicoCentroAnalise />} />
            <Route path="/gestao-economica/receitas" element={<EconomicoReceitas />} />
            <Route path="/gestao-economica/custos" element={<EconomicoCustos />} />
            <Route path="/gestao-economica/desvios" element={<EconomicoDesvios />} />
            <Route path="/gestao-economica/forecast" element={<EconomicoForecast />} />
            <Route path="/gestao-economica/forecast-operacional" element={<EconomicoForecastOperacional />} />
            <Route path="/gestao-economica/historico" element={<EconomicoHistorico />} />
            <Route path="/gestao-economica/resultado" element={<EconomicoResultado />} />
            <Route path="/gestao-economica/auditoria" element={<EconomicoAuditoria />} />
            <Route path="/gestao-integrada" element={<Navigate to="/gestao-integrada/auditoria" replace />} />
            <Route path="/gestao-integrada/auditoria" element={<PerformanceAuditoria />} />
            <Route path="/eap/mapear" element={<MapearEap />} />
            <Route path="/eap/gerar-pdf" element={<GerarPdfEap />} />
            {/* Módulo Produção (cronograma XER) */}
            <Route path="/producao" element={<Producao />} />
            <Route path="/producao/curva-s" element={<ProducaoEmBreve titulo="Curva S" descricao="Curva S dedicada com filtros por disciplina, área e WBS — próxima etapa." />} />
            <Route path="/producao/lookahead" element={<ProducaoEmBreve titulo="Lookahead" descricao="Lookahead de 2 e 4 semanas (atividade, início, término, responsável, disciplina, status) — próxima etapa." />} />
            <Route path="/producao/disciplinas" element={<ProducaoEmBreve titulo="Disciplinas" descricao="Visão por disciplina com KPIs, gráficos e atividades — próxima etapa." />} />
            <Route path="/producao/atividades" element={<ProducaoEmBreve titulo="Atividades" descricao="Tabela completa do cronograma com filtros (disciplina, WBS, status, período, crítica, atrasada) — próxima etapa." />} />
            <Route path="/previsao" element={<PrevisaoMensal />} />
            <Route path="/previsao/:ano/:mes" element={<PrevisaoMensal />} />
            <Route path="/avanco" element={<LancarAvanco />} />
            <Route path="/avanco/:ano/:mes" element={<LancarAvanco />} />
            <Route path="/medicao" element={<Medicao />} />
            <Route path="/medicao/:ano/:mes" element={<Medicao />} />
            <Route path="/pendencias" element={<Pendencias />} />
            <Route path="/documentos" element={<Documentos />} />
            <Route path="/relatorios" element={<Relatorios />} />
            <Route path="/relatorio-fotografico/:ano/:mes" element={<RelatorioFotografico />} />
            {/* Fase 2A — Sistema de Medição Petrobras */}
            <Route path="/integracao-ld" element={<IntegracaoLD />} />
            <Route path="/conciliacao-sigem" element={<ConciliacaoSigem />} />
            <Route path="/motor-medicao" element={<MotorMedicao />} />
            <Route path="/analise-revisoes" element={<AnaliseRevisoes />} />
            <Route path="/criterios" element={<Criterios />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SemanaProvider>
  )
}
