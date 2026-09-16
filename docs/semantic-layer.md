# Semantic Layer

The semantic project is the source of truth for analytical SQL. Generic backend code does not contain Tempo entity values or business synonyms.

Each project supplies:

- dataset sources, metrics, dimensions, time dimensions, relationships, and query rules;
- metric and dimension aliases;
- governed entity values and aliases;
- named periods, explicit date ranges, and previous-period mappings;
- comparison expressions, time-grain aliases, and analytical-pattern phrases;
- project-level golden questions.

Configuration is loaded by `app.semantic.loader` and validated into Pydantic models before resolution or SQL compilation. The resolver can only emit canonical semantic names and governed entity values. Normalization rejects unknown metrics, dimensions, filter targets, filter values, periods, and unsupported time grains.

Tempo-specific configuration is under `projects/tempo_scan/semantic/`. A reusable empty resolution profile remains under `projects/_template/semantic/`.
