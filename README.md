# stand-master

**STAR PLATINUM（白金之星）** — A multi-agent orchestrator built on the JoJo Stand architecture.

STAR PLATINUM is the primary agent. It processes tasks directly or summons specialised sub-agents (**Stands**) via the **GOLD EXPERIENCE** for tasks that require specific capabilities.

## Architecture

```
                    ┌─────────────────────────┐
                    │     STAR PLATINUM        │
                    │     （白金之星）           │
                    │   Main Orchestrator      │
                    │   core/agent_loop.py     │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │      GOLD EXPERIENCE         │
                    │    （スタンドの矢）        │
                    │    stands/gold_experience.py       │
                    └──┬───┬────┬───┬──────────┘
         ┌─────────────┘   │    │   └──────────────┐
         ▼                 ▼    ▼                  ▼
  ┌─────────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐
  │  THE WORLD  │  │HIEROPHANT│  │  HARVEST  │  │ SHEER HEART   │
  │ ザ・ワールド  │  │  GREEN   │  │ ハーヴェスト│  │    ATTACK     │
  │             │  │  法皇の緑  │  │           │  │シアーハートアタック│
  │ Close-Range │  │Long-Range│  │  Colony   │  │  Automatic    │
  │  in-process │  │ subagent │  │ in-process│  │  subagent     │
  └─────────────┘  └──────────┘  └───────────┘  └───────────────┘
         ▼
  ┌─────────────┐
  │    CRAZY    │
  │   DIAMOND   │
  │クレイジー・   │
  │ダイヤモンド  │
  │ Restoration │
  │ in-process  │
  └─────────────┘
```

### The Five Stands

| Stand | Ability | Spawn Mode | Pipeline |
|---|---|---|---|
| **THE WORLD** | Close-Range Power | in-process | Inner ReAct loop with dedicated reasoning model and higher step budget |
| **HIEROPHANT GREEN** | Long-Range | **subagent** | embed → vector search → SMAK relation expansion → consolidate |
| **HARVEST** | Colony | in-process | Split sub-tasks → `asyncio.gather` parallel execution → collect |
| **SHEER HEART ATTACK** | Automatic | **subagent** | Spawn subprocess via tmux/cron → (optional) poll → collect |
| **CRAZY DIAMOND** | Restoration | in-process | Detect error → diagnose root cause → attempt fix → verify |

HIEROPHANT GREEN and SHEER HEART ATTACK are spawned as independent subprocess via `SubAgentSpawner` (tmux or cron). They run their own pipeline inside `stands/runner.py`.

## Project Structure

```
stand-master/
├── agent.yaml                          # Main configuration
├── pyproject.toml
└── src/stand_master/
    ├── main.py                         # Thin entry point (bootstrap + repl)
    ├── bootstrap.py                    # DI container — wires all dependencies
    ├── repl.py                         # Interactive REPL — handles user I/O only
    ├── config.py                       # YAML config with ${VAR:-default} substitution
    ├── core/
    │   ├── agent_loop.py               # STAR PLATINUM ReAct loop
    │   ├── context_manager.py          # Token window / sliding history
    │   └── prompt_engine.py            # System prompt assembly
    ├── stands/
    │   ├── base.py                     # Stand ABC, StandType, StandStatus, SpawnMode
    │   ├── arrow.py                    # GoldExperience factory
    │   ├── the_world.py                # Close-Range Power (in-process)
    │   ├── hierophant_green.py         # Long-Range RAG (subagent)
    │   ├── harvest.py                  # Colony parallel (in-process)
    │   ├── sheer_heart_attack.py       # Automatic background (subagent)
    │   ├── crazy_diamond.py            # Restoration / error recovery (in-process)
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
        ├── heartbeat.py                # Async periodic health checks
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

```yaml
llm:
  base_url: ${LLM_BASE_URL:-http://localhost:11517/v1}
  model: ${LLM_MODEL:-gpt-oss-120b}
  api_key: ${LLM_API_KEY:-EMPTY}
  models:
    reasoning: qwen3_235B_A22B    # Used by THE WORLD for deep reasoning

embedding:
  api_base: ${EMBEDDING_API_BASE:-http://localhost:11434}
  model: ${EMBEDDING_MODEL:-nomic-embed-text}

smak:
  workspace_config: ./workspace_config.yaml

memory:
  storage_dir: ./agent_data/memory
  auto_memorize: true

subagent:
  enabled: true
  mode: tmux          # tmux | cron
  max_concurrent: 3
  timeout_seconds: 600
  work_dir: ./agent_data/subagent_tasks/
```

The embedding dimension is determined at runtime by probing the embedding endpoint — it is never hard-coded.

## Usage

```bash
# Run with default agent.yaml
stand-master

# Specify a config file
stand-master /path/to/my-config.yaml

# Or run as a module
python -m stand_master.main agent.yaml
```

Interactive session:

```
STAR PLATINUM> What does the auth module do?

[HIEROPHANT GREEN] Task completed.
Output: [SMAK #1] (source_code) auth.py — handles JWT validation ...

The auth module validates JWT tokens on every request. It uses ...

  [1 tool(s) | Stands: hierophant_green | 3 step(s)]

STAR PLATINUM> exit
やれやれだぜ… Goodbye!
```

## Summoning Stands

STAR PLATINUM can be instructed to use a specific Stand via the `summon_stand` tool:

| Command | Stand | When to use |
|---|---|---|
| `summon_stand("the_world")` | THE WORLD | Complex multi-step reasoning, hard analytical problems |
| `summon_stand("hierophant_green")` | HIEROPHANT GREEN | Semantic search, RAG retrieval, codebase exploration |
| `summon_stand("harvest")` | HARVEST | Batch operations, parallel sub-tasks |
| `summon_stand("sheer_heart_attack")` | SHEER HEART ATTACK | Long-running background jobs, fire-and-forget |
| `summon_stand("crazy_diamond")` | CRAZY DIAMOND | Error recovery, diagnosing failed pipelines, self-healing |

## Design Principles

| Principle | Implementation |
|---|---|
| **Single Responsibility** | `bootstrap.py` wires deps, `repl.py` handles I/O, `agent_loop.py` runs logic |
| **Open/Closed** | New Stands added without modifying existing ones — extend `StandType` and `GoldExperience` |
| **Liskov Substitution** | `Stand` ABC guarantees all Stands share the same `execute()` interface |
| **Interface Segregation** | `EmbeddingModel`, `VectorStore`, `QueryServiceLike` protocols expose minimal surfaces |
| **Dependency Inversion** | `AgentLoop` depends on abstractions; concrete deps injected by `bootstrap.py` |
| **Subagent depth limit** | `AGENT_DEPTH` env var prevents recursive spawning |
| **Dynamic embedding dim** | `FaissEngine` dimension set from `embedder.get_embedding_dimension()` at startup |

## License

MIT
