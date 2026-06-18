# Sprint Tecnica A - Consolidacao Arquitetural

Data: 2026-06-03

Escopo: sem funcionalidades novas, sem telas novas e sem alteracao de regra de negocio. A unica alteracao estrutural executada foi a estabilizacao da arvore Alembic.

## 1. Migrations

### Diagnostico inicial

`alembic_version` possuia dois heads ativos:

| Head | Ramo |
|---|---|
| `b7c8d9e10305` | Producao XER |
| `p2a3b4c5d605` | Economico / Performance |

Arvore resumida:

```text
9c7d947b4dbc
└ 7a9676a11c9a
  └ d42b7e5a8ef8
    └ 075cfb9d4358
      └ c3a1b2d4e501
        └ d9e8f7a6b502
          └ e0f1a2b3c604
            └ f1a2b3c4d705
              └ a1b2c3d4e506
                └ c3d4e5f60201
                  └ e4f5a6b7c802
                    ├ f5a6b7c80103 -> a6b7c8d90204 -> b7c8d9e10305
                    └ f1a2b3c4d503 -> f1c2d3e4f504 -> p2a3b4c5d605
```

### Merge criado

| Campo | Valor |
|---|---|
| Migration | `20260603_0001_merge_producao_economico_heads.py` |
| Revision | `m1a2b3c4d606` |
| Down revisions | `b7c8d9e10305`, `p2a3b4c5d605` |
| Tipo | Merge vazio, sem DDL |

### Ajuste de idempotencia

A baseline `9c7d947b4dbc` cria o schema a partir do `Base.metadata` atual. Por isso, em banco limpo, migrations posteriores tentavam recriar tabelas/colunas ja existentes. Foram adicionadas guardas idempotentes em migrations aditivas antigas para permitir `upgrade head` completo sem duplicidade.

### Resultado final

| Validacao | Resultado |
|---|---|
| `python -m alembic heads` | `m1a2b3c4d606 (head)` |
| Banco existente | `alembic_version = m1a2b3c4d606` |
| Banco limpo temporario | `upgrade head` concluido |
| Banco limpo temporario | 46 tabelas criadas |

## 2. Mapeamento de Tabelas

| Tabela | Status | Uso atual | Destino |
|---|---|---|---|
| `tarefas` | Canonica | Programacao semanal / cronograma | Manter |
| `semanas` | Canonica | Calendario e ciclo semanal | Manter |
| `programacao_semanal` | Canonica | QCRON/QPROG/QREAL | Manter |
| `sub_tarefas` | Vazia operacional | Subtarefas de programacao | Manter |
| `relatorio_semana` | Vazia | Textos do relatorio semanal | Manter |
| `imports` | Canonica | Historico de importacoes semanais | Manter |
| `painel_snapshot` | Canonica | Painel de avanco fisico semanal | Manter |
| `painel_fase_semana` | Canonica | Avanco por fase/semana | Manter |
| `eap_item` | Canonica | EAP financeira/medicao | Manter |
| `tarefa_eap_link` | Vazia operacional | Mapeamento tarefa-EAP | Manter |
| `eap_previsao_mensal` | Canonica legada | Previsao mensal da medicao | Manter ate consolidar BM |
| `eap_avanco_semanal` | Vazia operacional | Avanco semanal EAP | Manter |
| `ciclo_medicao` | Legada | Compatibilidade BM antigo | Migrar |
| `lancamento_medicao` | Legada | Lancamentos BM antigo | Migrar |
| `bm_ciclo` | Canonica | Ciclo BM novo | Manter |
| `bm_snapshot_previsao` | Canonica | Snapshot imutavel de previsao | Manter |
| `bm_lancamento` | Canonica | Lancamentos BM novo | Manter |
| `bm_versao` | Canonica | Versionamento BM | Manter |
| `bm_consolidado` | Canonica | Consolidado financeiro BM | Manter |
| `bm_pendencia` | Canonica | Pendencias BM | Manter |
| `bm_pendencia_redistrib` | Canonica | Redistribuicoes de pendencias | Manter |
| `bm_log` | Canonica | Auditoria BM | Manter |
| `competencia_financeira` | Canonica | Governanca mensal | Manter |
| `competencia_log` | Canonica | Auditoria de competencia | Manter |
| `criterios_medicao` | Canonica | Criterios de medicao | Manter |
| `documento_engenharia` | Vazia / sobreposta | CRUD antigo de documentos | Remover futuramente apos consolidar LD |
| `ld_documentos` | Canonica | Lista de documentos LD | Manter |
| `ld_historico_status` | Canonica | Historico LD | Manter |
| `sigem_documentos` | Canonica | Status SIGEM oficial | Manter |
| `sigem_historico_status` | Canonica | Historico SIGEM | Manter |
| `prod_projeto` | Canonica | Importacoes XER producao | Manter |
| `prod_wbs` | Canonica | WBS producao | Manter |
| `prod_atividade` | Canonica | Atividades producao | Manter |
| `economico_importacao` | Canonica | Importacoes economicas | Manter |
| `economico_valor` | Canonica / historica | Valores normalizados Fase 1A | Manter |
| `economico_auditoria` | Canonica | Auditoria Sistema x Resumo BI | Manter |
| `economico_resumo_calculado` | Canonica | Camada calculada auditada | Manter |
| `economico_lancamento_razao` | Canonica | Drilldown RAZAO | Manter |
| `economico_relatorio_oc` | Canonica | OCs / fornecedores | Manter |
| `economico_analise_dre` | Canonica | DRE / desvios | Manter |
| `economico_conta_despesa` | Canonica | Dicionario de contas | Manter |
| `performance_custo_classificacao` | Parcial | Classificacao custos integrada | Manter aguardando baseline |
| `performance_auditoria_mes` | Parcial | Auditoria Producao x Economico | Manter aguardando baseline |
| `foto_medicao` | Canonica | Relatorio fotografico / medicao | Manter |
| `relatorio_fotografico_meta` | Vazia | Metadados relatorio fotografico | Manter |
| `usuarios` | Vazia | Futuro usuario/auditoria | Remover futuramente ou implementar governanca |

## 3. Auditoria de Endpoints

### Programacao Semanal

| Endpoint | Router | Tela que utiliza | Status |
|---|---|---|---|
| `/api/semanas/` GET/POST | `semanas` | Dashboard, Importacao, QPROG | Ativo |
| `/api/semanas/{codigo}` GET/PUT/DELETE | `semanas` | Importacao, QREAL, QPROG | Ativo |
| `/api/semanas/{codigo}/qcron` | `semanas` | Dashboard, QPROG, PDF | Ativo |
| `/api/semanas/{codigo}/qprog` | `semanas` | QPROG, QREAL, PDF | Ativo |
| `/api/semanas/{codigo}/indicadores` | `semanas` | Dashboard, PDF | Ativo |
| `/api/semanas/{codigo}/programacoes` PATCH | `semanas` | QPROG | Ativo |
| `/api/semanas/{codigo}/programacoes/{prog_id}` PATCH | `semanas` | QPROG/QREAL | Ativo |
| `/api/semanas/{codigo}/fechar` | `semanas` | QREAL | Ativo |
| `/api/semanas/{codigo}/reabrir` | `semanas` | Sem uso direto | Interno |
| `/api/semanas/{codigo}/adiantar` | `semanas` | QPROG | Ativo |
| `/api/imports/` GET/DELETE | `imports` | Importacao | Ativo |
| `/api/imports/xlsx` | `imports` | Importacao | Ativo |
| `/api/imports/xer` | `imports` | Importacao | Ativo |
| `/api/imports/semanas` | `imports` | Importacao | Ativo |
| `/api/tarefas/` | `tarefas` | Mapear EAP, QPROG | Ativo |
| `/api/programacoes/{prog_id}/sub-tarefas` | `sub_tarefas` | QPROG | Ativo |
| `/api/relatorio/{semana}` GET/POST | `relatorio` | Textos, PDF | Ativo |

### Medicao / EAP / BM

| Endpoint | Router | Tela que utiliza | Status |
|---|---|---|---|
| `/api/eap/importar` | `eap` | Mapear EAP/admin | Ativo |
| `/api/eap/itens` | `eap` | Previsao, Medicao, Mapear EAP | Ativo |
| `/api/eap/links` GET/POST/DELETE | `eap` | Mapear EAP | Ativo |
| `/api/eap/auto-mapear` | `eap` | Mapear EAP | Ativo |
| `/api/eap/previsao/{ano}/{mes}` GET/POST | `eap` | Previsao Mensal, Avanco | Ativo |
| `/api/eap/previsao/{ano}/{mes}/puxar-p6` | `eap` | Previsao Mensal | Ativo |
| `/api/eap/previsao/{ano}/{mes}/adiantar` | `eap` | Previsao Mensal | Ativo |
| `/api/eap/previsao/{ano}/{mes}/pendencias` | `eap` | Pendencias/legado | Legado |
| `/api/eap/avanco/{semana_codigo}` GET | `eap` | Avanco | Ativo |
| `/api/eap/avanco` POST | `eap` | Avanco | Ativo |
| `/api/eap/ciclos/*` | `eap` | Fluxo legado/compatibilidade | Legado |
| `/api/eap/gerar-pdf` | `eap` | Gerar PDF EAP | Ativo |
| `/api/bm/*` | `bm` | Medicao, Financeiro, Pendencias | Ativo |
| `/api/bm/migrar-legado` | `bm` | Sem tela direta | Interno |
| `/api/export/bm/{ano}/{mes}/excel` | `export` | Relatorios | Ativo |
| `/api/medicao/{ano}/{mes}/fotos/*` | `fotos` | Medicao/Relatorio Fotografico | Ativo |

### Engenharia

| Endpoint | Router | Tela que utiliza | Status |
|---|---|---|---|
| `/api/ld/upload` | `ld` | Integracao LD | Ativo |
| `/api/ld/documentos` | `ld` | Integracao LD | Ativo |
| `/api/ld/documentos/{id}/historico` | `ld` | Integracao LD | Ativo |
| `/api/ld/filtros` | `ld` | Integracao LD | Ativo |
| `/api/sigem/upload` | `sigem` | Conciliacao SIGEM | Ativo |
| `/api/sigem/conciliacao` | `sigem` | Conciliacao SIGEM | Ativo |
| `/api/sigem/documentos-divergentes` | `sigem` | Dashboard Executivo | Ativo |
| `/api/sigem/documentos` | `sigem` | Sem uso direto atual | Interno |
| `/api/sigem/sem-workflow` | `sigem` | Sem uso direto atual | Interno |
| `/api/sigem/filtros` | `sigem` | Sem uso direto atual | Interno |
| `/api/documentos/*` | `documentos` | Documentos | Ativo / sobreposto |
| `/api/medicao-eng/*` | `medicao_engenharia` | Motor Medicao / Dashboard Executivo | Ativo |
| `/api/criterios/*` | `criterios` | Criterios | Ativo |

### Producao e Gestao Integrada

| Endpoint | Router | Tela que utiliza | Status |
|---|---|---|---|
| `/api/producao/import-xer` | `producao` | Producao | Ativo |
| `/api/producao/dashboard` | `producao` | Producao | Ativo |
| `/api/producao/status` | `producao` | Sem uso direto | Interno |
| `/api/painel/{semana}` | `painel` | Avanco da Obra | Ativo |
| `/api/painel/{semana}/recalcular` | `painel` | Avanco da Obra | Ativo |
| `/api/painel/{semana}/importar` | `painel` | Avanco da Obra | Ativo |
| `/api/performance/auditoria` | `performance` | Gestao Integrada Auditoria | Bloqueado funcionalmente |

### Gestao Economica

| Endpoint | Router | Tela que utiliza | Status |
|---|---|---|---|
| `/api/economico/importar` | `economico` | Auditoria Economica | Ativo |
| `/api/economico/importacoes` | `economico` | Sem uso direto atual | Interno |
| `/api/economico/auditoria` | `economico` | Auditoria | Ativo |
| `/api/economico/auditoria-receitas` | `economico` | Sem tela direta | Interno |
| `/api/economico/dashboard` | `economico` | Dashboard Executivo | Ativo |
| `/api/economico/receitas` | `economico` | Receitas | Ativo |
| `/api/economico/custos` | `economico` | Custos | Ativo |
| `/api/economico/desvios` | `economico` | Principais Desvios | Ativo |
| `/api/economico/centro-analise` | `economico` | Centro de Analise | Ativo |
| `/api/economico/forecast` | `economico` | Forecast | Ativo |
| `/api/economico/historico` | `economico` | Historico | Ativo |
| `/api/economico/resultado` | `economico` | Resultado | Ativo |
| `/api/economico/lancamentos` | `economico` | Drilldowns | Ativo |

## 4. Auditoria de Importadores

| Importador | Origem | Destino | Tabelas impactadas | Risco |
|---|---|---|---|---|
| XER Programacao | Primavera/XER para semanal | Programacao Semanal | `tarefas`, `programacao_semanal`, `imports` | Pode divergir da interpretacao de Producao |
| XER Painel | Primavera/XER por semana | Avanco da Obra | `painel_snapshot`, `painel_fase_semana` | Interpretacao fisica propria |
| XER Producao | Primavera/XER completo | Producao | `prod_projeto`, `prod_wbs`, `prod_atividade` | Falta baseline BL Units oficial |
| LD | Excel LD | Engenharia | `ld_documentos`, `ld_historico_status` | Sobreposicao com documentos antigos |
| SIGEM | Excel/CSV SIGEM | Engenharia | `sigem_documentos`, `sigem_historico_status` | Deve seguir como fonte oficial de status |
| Economico | XLSX Gestao Economica | Gestao Economica | `economico_*`, `performance_*` | Concentrado em service grande |
| EAP | Excel EAP | Medicao/EAP | `eap_item`, `tarefa_eap_link` | Base critica para BM e medicao |
| Documentos | Excel manual | Engenharia antiga | `documento_engenharia` | Sobreposto com LD |

## 5. Frontend - Paginas Grandes

| Pagina | Linhas | Responsabilidades | Plano de modularizacao |
|---|---:|---|---|
| `MontarQprog.jsx` | 1107 | QPROG, filtros, tabela, sub-tarefas, adiantamento, bulk update | Extrair filtros, tabela, modal subtarefa, hooks de programacao |
| `PrevisaoMensal.jsx` | 1104 | Previsao EAP, arvore, adiantamentos, pendencias, filtros | Extrair arvore EAP, editor percentual, painel pendencias, hook de ciclo |
| `Medicao.jsx` | 1016 | BM, status lifecycle, fotos, lancamentos, PDF, consolidacao | Extrair workflow BM, tabela lancamentos, fotos, modais, hooks BM |
| `Importacao.jsx` | 686 | Importacao XER/XLSX/semanas, CRUD semanas | Separar importadores e CRUD calendario |
| `Painel.jsx` | 563 | Dashboard fisico, recalculo, importacao XER | Extrair cards/graficos/importador |
| `RelatorioFotografico.jsx` | 531 | Fotos, filtros, legendas, relatorio | Extrair galeria e modal |
| `Documentos.jsx` | 500 | CRUD e importacao documentos | Separar form, tabela, importador |

## 6. Services Grandes

| Service | Linhas | Blocos candidatos a extracao |
|---|---:|---|
| `economico_service.py` | 1789 | Importacao Excel, engenharia reversa, persistencia normalizada, auditoria, dashboard, receitas, custos, desvios, centro de analise, forecast, resultado, historico, drilldown |
| `bm_service.py` | 1609 | Previsao, abertura BM, snapshot, lancamentos, status lifecycle, fechamento, consolidacao, pendencias, dashboard, versoes, logs, PDF helpers, legado |
| `export_service.py` | 826 | Excel BM, abas, formatos, auditoria export |
| `competencia_service.py` | 361 | Estado mensal, auditoria, locks |
| `producao_service.py` | 267 | Importacao XER, dashboard, agregacoes |
| `performance_service.py` | 260 | Classificacao custos, auditoria integrada |

## 7. Debitos Tecnicos Priorizados

### Critico

1. Migrations divergentes corrigidas nesta sprint; manter disciplina para nao bifurcar novamente.
2. Baseline Alembic dependente de `Base.metadata` atual; mitigada por idempotencia, mas deve ser reavaliada numa futura consolidacao.
3. Coexistencia BM novo e legado pode causar divergencia se o espelhamento for quebrado.
4. Gestao Integrada ainda bloqueada por baseline oficial de Producao.

### Alto

1. `economico_service.py` e `bm_service.py` concentrando regras demais.
2. Tres interpretacoes XER coexistindo sem contrato formal unico.
3. Tabelas de engenharia sobrepostas (`documento_engenharia`, `ld_documentos`, `sigem_documentos`).
4. Lint frontend falha com 20 erros.
5. Paginas React acima de 1000 linhas dificultam evolucao segura.

### Medio

1. Bundle frontend com chunks acima de 500 kB.
2. Funcoes de API exportadas sem uso direto.
3. Tabelas vazias sem politica de vida util.
4. Warnings de teste/backend acumulados.

## 8. Estado dos Modulos

| Modulo | Status | Observacao |
|---|---|---|
| Programacao Semanal | Operacional | Funcional, mas frontend muito concentrado |
| Engenharia | Operacional / Parcial | LD e SIGEM ativos; documentos antigos sobrepostos |
| Producao | Parcial | XER ativo, mas baseline oficial pendente |
| Medicao | Operacional | BM novo robusto; legado ainda acoplado |
| Gestao Economica | Operacional | Numeros auditados; service precisa separacao |
| Gestao Integrada | Bloqueado | Aguardar baseline Producao |

## 9. Top 10 Riscos Tecnicos

1. Regressao em migrations por baseline dinamica.
2. Divergencia BM novo x legado.
3. Interpretacoes conflitantes do XER.
4. Integracao fisico-financeira sem baseline.
5. Services economico/BM grandes demais.
6. Frontend dificil de testar por paginas monoliticas.
7. Lint quebrado escondendo erros simples.
8. Tabelas vazias/legadas sem governanca.
9. Endpoints internos sem catalogo formal.
10. Performance/bundle crescendo sem code splitting.

## 10. Top 10 Melhorias Recomendadas

1. Manter um unico head Alembic e revisar toda nova migration.
2. Criar pacote `economico` com importacao, auditoria, consultas e drilldown separados.
3. Criar pacote `bm` com ciclo, lancamentos, pendencias, dashboard e legado separados.
4. Formalizar contrato XER por uso: Programacao, Painel e Producao.
5. Definir fonte canonica de documento de engenharia.
6. Modularizar as tres maiores paginas React.
7. Corrigir lint por modulo.
8. Criar testes de API para endpoints economicos.
9. Catalogar endpoints internos e legados.
10. Planejar remocao futura de tabelas vazias/legadas.

## 11. Roadmap Tecnico Recomendado

1. Merge Alembic e disciplina de migrations. Concluido nesta sprint.
2. Consolidacao BM: reduzir acoplamento com legado e documentar ciclo canonico.
3. Refatoracao Economico: separar importacao, normalizacao, auditoria e telas.
4. Refatoracao Producao: estabilizar modelo XER e contratos fisicos.
5. Baseline Producao: implementar BL Units oficial antes de indicadores integrados.
6. Gestao Integrada: retomar somente com baseline validada.
