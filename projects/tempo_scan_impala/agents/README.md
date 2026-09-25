# TEMPO Agent Studio — Master Orchestration + Domain Agents

**Arsitektur:** [assets/tempo-agent-orchestration-architecture.png](../../../assets/tempo-agent-orchestration-architecture.png)

| Agent Studio name | File prompt | Domain |
|-------------------|-------------|--------|
| TEMPO Master Orchestrator | [master_orchestrator.md](master_orchestrator.md) | Routing |
| TEMPO Agent Sales | [agent_sales.md](agent_sales.md) | Sell-In / PTT |
| TEMPO Agent B2B | [agent_b2b.md](agent_b2b.md) | Sell-Out partner |
| TEMPO Agent Stock SAT-IDM | [agent_stock_sat_idm.md](agent_stock_sat_idm.md) | DC/outlet partner stock |
| TEMPO Agent SAT OOS | [agent_sat_oos.md](agent_sat_oos.md) | Field OOS |
| TEMPO Agent Stock Tempo | [agent_stock_tempo.md](agent_stock_tempo.md) | SAP warehouse stock |
| TEMPO Agent Service Level | [agent_service_level.md](agent_service_level.md) | PO/DO fill rate |
| TEMPO Agent Picking | [agent_picking.md](agent_picking.md) | Outbound logistics |
| TEMPO Agent Unloading | [agent_unloading.md](agent_unloading.md) | Inbound logistics |
| TEMPO Agent Data Promo | [agent_data_promo.md](agent_data_promo.md) | SAT Promo Des 2024 |

## Shared tools (semua sub-agent)

Mount dari [../agent_studio_tools/](../agent_studio_tools/):

1. `resolve_semantic_object`
2. `get_metric_definition`
3. `query_ontology`
4. `find_join_path`
5. `execute_governed_query`

## Workflow Agent Studio

Lihat [AGENT_STUDIO_ORCHESTRATION.md](AGENT_STUDIO_ORCHESTRATION.md).

## Kamus & pertanyaan

- [datasets/TEMPO_KAMUS_DATA_AI.md](../../../datasets/TEMPO_KAMUS_DATA_AI.md)
- [datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md](../../../datasets/TEMPO_BUSINESS_QUESTIONS_CATALOG.md)
- [datasets/TEMPO_BUSINESS_QUESTIONS_CHART_INDEX.md](../../../datasets/TEMPO_BUSINESS_QUESTIONS_CHART_INDEX.md)
- Regresi: [../ossie/golden_questions.yaml](../ossie/golden_questions.yaml)
