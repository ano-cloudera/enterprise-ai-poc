# Tempo Scan — high-level architecture

**PNG exports** (for slides / Confluence) live in [`diagrams/`](diagrams/). Source is Mermaid (`.mmd`); re-render with:

```bash
cd docs/diagrams
npx @mermaid-js/mermaid-cli mmdc -i tempo-ask-ai-overview.mmd -o tempo-ask-ai-overview.png -b white -w 1400
```

| PNG | Description |
|-----|-------------|
| [`diagrams/tempo-ask-ai-overview.png`](diagrams/tempo-ask-ai-overview.png) | One-slide stack + data flow |
| [`diagrams/tempo-ask-ai-topology.png`](diagrams/tempo-ask-ai-topology.png) | Deployment components (FE, BE, LLM, Impala) |
| [`diagrams/tempo-ask-ai-sequence.png`](diagrams/tempo-ask-ai-sequence.png) | Typical Ask Data request (stream) |
| [`diagrams/tempo-langgraph-flow.png`](diagrams/tempo-langgraph-flow.png) | LangGraph governed pipeline |

See also [`architecture.md`](architecture.md) for contracts and guardrails.
