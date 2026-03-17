# JoJo's Bizarre Agent

**JoJo（ジョジョ）** — A multi-agent orchestrator built on the Stand architecture from JoJo's Bizarre Adventure.

JoJo is the main protagonist. Like the JoJos across each season, he can channel different **JoJo Stand personas** — each with its own philosophy, system prompt, and approach to problem-solving. All personas share JoJo's memory.

Only **GOLD EXPERIENCE** can spawn independent sub-agent **Stands** for specialised tasks.

## Architecture

```
                         ┌─────────────────────────────────┐
                         │           JoJo（ジョジョ）        │
                         │         Main Orchestrator        │
                         │         core/jojo.py             │
                         │                                  │
                         │   Heartbeat · Memory · Persona   │
                         └───────────────┬─────────────────┘
                                         │ channels one of:
        ┌──────────┬──────────┬──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼          ▼          ▼
  ┌───────────┐┌──────────┐┌──────────┐┌──────────┐┌────────┐┌──────────┐
  │   STAR    ││  CRAZY   ││   GOLD   ││  STONE   ││  TUSK  ││ SOFT &   │
  │ PLATINUM  ││ DIAMOND  ││EXPERIENCE││  FREE    ││        ││   WET    │
  │  Part 3   ││  Part 4  ││  Part 5  ││  Part 6  ││ Part 7 ││  Part 8  │
  │ Precision ││ Recovery ││Orchestrat││ Decompose││Iterativ││ Extract  │
  └───────────┘└──────────┘└────┬─────┘└──────────┘└────────┘└──────────┘
                                │ spawns sub-agents:
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
        ┌─────────────┐  ┌──────────┐  ┌───────────────┐
        │  THE WORLD  │  │HIEROPHANT│  │    HARVEST    │
        │ ザ・ワールド  │  │  GREEN   │  │  ハーヴェスト  │
        │ Close-Range │  │Long-Range│  │    Colony     │
        │ in-process  │  │ subagent │  │  in-process   │
        └─────────────┘  └──────────┘  └───────────────┘
                                       ┌───────────────┐
                                       │ SHEER HEART   │
                                       │    ATTACK     │
                                       │  Automatic    │
                                       │   subagent    │
                                       └───────────────┘
```

### JoJo Stand Personas (how JoJo thinks)

| Persona | Part | Stand User | Philosophy |
|---|---|---|---|
| **STAR PLATINUM** | 3 | Jotaro Kujo | Direct, precise, no-nonsense execution |
| **CRAZY DIAMOND** | 4 | Josuke Higashikata | Diagnose, restore, heal the system |
| **GOLD EXPERIENCE** | 5 | Giorno Giovanna | Break into sub-tasks, spawn agents, synthesise |
| **STONE FREE** | 6 | Jolyne Cujoh | Unravel complexity, find connections |
| **TUSK** | 7 | Johnny Joestar | Iterative deepening (Act 1→4) |
| **SOFT & WET** | 8 | Josuke (Gappy) | Extract, isolate, purify |

### Spawnable Stands (sub-agents via Gold Experience)

| Stand | Ability | Spawn Mode | Pipeline |
|---|---|---|---|
| **THE WORLD** | Close-Range Power | in-process | Inner ReAct loop with reasoning model |
| **HIEROPHANT GREEN** | Long-Range | subagent | embed → vector search → SMAK expansion → consolidate |
| **HARVEST** | Colony | in-process | Split → `asyncio.gather` parallel → collect |
| **SHEER HEART ATTACK** | Automatic | subagent | Spawn subprocess → poll → collect |

## Project Structure

```
stand-master/
├── agent.yaml                          # Main configuration
├── pyproject.toml
└── src/jojo/
    ├── main.py                         # Thin entry point
    ├── bootstrap.py                    # DI container — wires all dependencies
    ├── repl.py                         # Interactive REPL
    ├── config.py                       # YAML config with ${VAR:-default} substitution
    ├── core/
    │   ├── jojo.py                     # JoJo main orchestrator (persona switching)
    │   ├── context_manager.py          # Token window / sliding history
    │   └── prompt_engine.py            # Shared prompt utilities
    ├── jojo_stands/                    # JoJo Stand personas (how JoJo thinks)
    │   ├── base.py                     # JoJoStand ABC, JoJoStandType, StandProfile
    │   ├── star_platinum.py            # Part 3 — precision execution
    │   ├── crazy_diamond.py            # Part 4 — recovery & restoration
    │   ├── gold_experience.py          # Part 5 — sub-agent orchestration
    │   ├── stone_free.py               # Part 6 — decomposition & connection
    │   ├── tusk.py                     # Part 7 — iterative deepening (Acts 1-4)
    │   └── soft_and_wet.py             # Part 8 — extraction & isolation
    ├── stands/                         # Spawnable Stands (sub-agents)
    │   ├── base.py                     # Stand ABC, StandType, SpawnMode
    │   ├── the_world.py                # Close-Range Power (in-process)
    │   ├── hierophant_green.py         # Long-Range RAG (subagent)
    │   ├── harvest.py                  # Colony parallel (in-process)
    │   ├── sheer_heart_attack.py       # Automatic background (subagent)
    │   └── runner.py                   # Subprocess entry for subagent Stands
    ├── mcp/
    │   ├── client.py                   # MCP stdio client
    │   ├── tool_registry.py            # Unified tool registry (MCP + local)
    │   └── skill_loader.py             # SKILL.md parser
    ├── memory/
    │   ├── store.py                    # SMAK-backed vector memory
    │   └── summarizer.py              # LLM-based conversation compression
    └── services/
        ├── permission.py               # Glob-based allow/deny/confirm rules
        ├── heartbeat.py                # Async periodic health checks (belongs to JoJo)
        ├── email_notifier.py           # Notifications via ddi_api.pl
        └── subagent.py                 # tmux/cron spawner (1-level depth limit)
```

## Prerequisites

- Python 3.10+
- A local OpenAI-compatible LLM endpoint (e.g. vLLM serving `gpt-oss-120b`)
- [SMAK](https://github.com/tl32rodan/SMAK) — semantic search + 1-hop relation expansion
- [faiss-storage-lib](https://github.com/tl32rodan/faiss-storage-lib) — FAISS + SQLite vector store
- A local Nomic-compatible embedding endpoint (e.g. Ollama serving `nomic-embed-text`)

## Installation

```bash
pip install -e .

# Development
pip install -e ".[dev]"
```

## Configuration

Edit `agent.yaml`. All values support `${VAR:-default}` env substitution.

## Usage

```bash
# Run with default agent.yaml
jojo

# Specify a config file
jojo /path/to/my-config.yaml
```

Interactive session:

```
JoJo> What does the auth module do?

[STAR PLATINUM | HIEROPHANT GREEN] Task completed.
Output: [SMAK #1] (source_code) auth.py — handles JWT validation ...

The auth module validates JWT tokens on every request.

  [STAR PLATINUM | 1 tool(s) | Stands: hierophant_green | 3 step(s)]

JoJo> /persona tusk
  Switching to TUSK（タスク）

TUSK> Research how the payment system works
  [Act 1 — broad scan...]
  [Act 2 — focused search...]
  [Act 3 — deep analysis...]
  [Act 4 — final answer]

  [TUSK | 8 tool(s) | 12 step(s)]

JoJo> exit
やれやれだぜ… Goodbye!
```

## Design Principles

| Principle | Implementation |
|---|---|
| **Single Responsibility** | `bootstrap.py` wires deps, `repl.py` handles I/O, `jojo.py` orchestrates |
| **Open/Closed** | New JoJo Stands added without modifying existing ones — extend `JoJoStandType` |
| **Liskov Substitution** | `JoJoStand` ABC guarantees all personas share `build_system_prompt()` + `run()` |
| **Interface Segregation** | `EmbeddingModel`, `VectorStore`, `QueryServiceLike` expose minimal surfaces |
| **Dependency Inversion** | `JoJo` depends on abstractions; concrete deps injected by `bootstrap.py` |
| **Subagent depth limit** | `AGENT_DEPTH` env var prevents recursive spawning |
| **Dynamic embedding dim** | Dimension set from `embedder.get_embedding_dimension()` at startup |

## License

MIT
