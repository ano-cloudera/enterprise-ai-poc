# Prompt Management — Design

## Current state

- Markdown files in `backend-dev/prompts/` loaded at runtime by `workflow.py`, `conversational.py`
- No versioning, activation API, or project isolation in DB

## Hierarchy (target)

```text
Workspace-scoped prompts (scope=workspace, project_id NULL)
        │
Project prompts (scope=project, project_id set)
        │
Skill prompts (scope=skill, bound to skill_version)
        │
Session Context (dynamic, not versioned)
        │
User Message
```

**Important:** “Global” in product language means **workspace-level** defaults (`workspace_id` + `scope=workspace`), **not** implicitly installation-wide. A deployment may host multiple workspaces, each with its own system prompt set.

## Data model keys

Every `prompt` row:

- `workspace_id` — **required**
- `project_id` — **optional** (null → workspace-wide)
- `scope` — explicit: `workspace` | `project` | `skill`

## Precedence (assembly)

1. Workspace-scoped system/safety prompts (**highest authority** for safety rules)
2. Project prompt overlays domain tone + policies (when `project_id` matches active project)
3. Active skill prompt adds task behavior
4. Session context (prior turns, analysis frame) injected by orchestrator
5. User message last

**Rule:** Safety/guardrail blocks in global cannot be weakened by project/skill.

## Entities

See `DATA_MODEL.md`: `prompt`, `prompt_version` with `scope` as **text** (`workspace`, `project`, `skill`).

## Versioning behaviors

- `create_version(prompt_id, body)` → increments version
- `activate_version(version_id)` → deactivates siblings
- `list_history(prompt_id)`
- `rollback(prompt_id, version)` → activate historical

Never overwrite content in place.

## Runtime resolution (M3)

```python
def assemble_prompt(project_id, skill_id|null, session_ctx) -> list[ChatMessage]:
    ...
```

Cache active versions in memory with TTL; invalidate on activation webhook/event.

## Migration from disk

One-time import:

| File | Scope |
|------|-------|
| `global_system.md` | global |
| `planner.md`, `result_analyst.md`, ... | project or skill mapping table |

Keep disk fallback env `PROMPT_SOURCE=disk|db` during transition.

## API (target)

- CRUD prompts
- `POST .../prompts/{id}/versions`
- `POST .../versions/{id}/activate`
- `GET .../prompts/{id}/active`

## FE (target)

Prompts list + editor + history timeline (Studio-like) — M3.

## Audit

Log `prompt.activate` in `audit_event`.
