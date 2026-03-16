# Local ReAct Agent

A local, offline-capable ReAct agent built on top of **SMAK** (as a Python library) with MCP client support for external tools.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              local-react-agent                        │
│                                                       │
│  ┌────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │ AgentLoop  │  │ MCPClient   │  │ MemoryStore   │  │
│  │ (ReAct +   │  │ (filesystem │  │ (SMAK index + │  │
│  │  bind_tools)│  │  + others)  │  │  QueryService)│  │
│  └─────┬──────┘  └──────┬──────┘  └───────┬───────┘  │
│        │                │                 │           │
│  ┌─────┴──────┐  ┌──────┴──────┐  ┌──────┴────────┐  │
│  │ ChatOpenAI │  │ Permission  │  │ SMAK library  │  │
│  │ (OpenAI v1)│  │ Manager     │  │ (direct       │  │
│  └────────────┘  └─────────────┘  │  Python import)│  │
│                                   └───────────────┘  │
│  ┌────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │ SkillLoader│  │ Heartbeat   │  │ SubAgent      │  │
│  │ (SKILL.md) │  │ Service     │  │ Spawner       │  │
│  └────────────┘  └─────────────┘  └───────────────┘  │
│  ┌─────────────────────────────┐                      │
│  │ EmailNotifier (ddi_api.pl)  │                      │
│  └─────────────────────────────┘                      │
└──────────────────────────────────────────────────────┘
         │                    │
    ┌────┴─────┐        ┌────┴──────┐
    │Filesystem│        │ Other MCP │
    │MCP Server│        │ Servers   │
    └──────────┘        └───────────┘
```

**SMAK** is imported directly as a Python library (no MCP roundtrip for RAG).
Only external tools (filesystem\_server, etc.) use the MCP stdio client.

## Project Structure

```
├── agent.yaml                        # Main configuration
├── pyproject.toml                    # Dependencies & build
├── src/react_agent/
│   ├── config.py                     # YAML config with ${VAR:-default} env substitution
│   ├── main.py                       # CLI entry point
│   ├── core/
│   │   ├── agent_loop.py             # ReAct loop (ChatOpenAI + bind_tools)
│   │   ├── context_manager.py        # Token window / sliding history
│   │   └── prompt_engine.py          # System prompt assembly
│   ├── mcp/
│   │   ├── client.py                 # MCP stdio client for external tools
│   │   ├── tool_registry.py          # Unified registry (SMAK + MCP + local)
│   │   └── skill_loader.py           # SKILL.md parser
│   ├── memory/
│   │   ├── store.py                  # SMAK-backed memory (1-hop relation expansion)
│   │   ├── summarizer.py             # LLM-based conversation compression
│   │   └── fallback.py               # In-memory stubs when SMAK is absent
│   └── services/
│       ├── permission.py             # Glob-based allow/deny/confirm rules
│       ├── heartbeat.py              # Async periodic health checks
│       ├── email_notifier.py         # Notifications via ddi_api.pl
│       └── subagent.py               # tmux/cron spawner (1-level depth limit)
└── tests/                            # 85 unit tests
```

## Prerequisites

- Python 3.10+
- A local OpenAI-compatible LLM endpoint (e.g. vLLM serving `gpt-oss-120b`)

Optional (for full RAG memory):
- [SMAK](https://github.com/tl32rodan/SMAK) — semantic search + 1-hop relation expansion
- [faiss-storage-lib](https://github.com/tl32rodan/faiss-storage-lib) — FAISS + SQLite vector store

## Installation

```bash
pip install -e .

# With SMAK support (recommended for production)
pip install -e ".[smak]"

# Development
pip install -e ".[dev]"
```

## Configuration

Copy and edit `agent.yaml`:

```yaml
llm:
  base_url: ${LLM_BASE_URL:-http://f15dtpai1:11517/v1}
  model: ${LLM_MODEL:-gpt-oss-120b}
  api_key: ${LLM_API_KEY:-EMPTY}

memory:
  storage_dir: ./agent_data/memory
  auto_memorize: true

mcp_servers:
  filesystem:
    command: python
    args: ["-m", "filesystem_server.server"]
    env:
      ROOT_DIR: ${WORKSPACE_ROOT:-.}

permissions:
  mode: ask        # ask | allow_all | deny_all
  require_confirmation:
    - delete_file
    - write_file
    - run_terminal_command
```

Environment variables use `${VAR:-default}` syntax and are resolved at load time.

## Usage

```bash
# Run with default agent.yaml
react-agent

# Or specify a config file
react-agent /path/to/my-config.yaml

# Or run directly
python -m react_agent.main agent.yaml
```

Interactive session:

```
Local ReAct Agent ready. Type 'exit' or 'quit' to leave.
> What files are in the current directory?

The current directory contains: README.md, src/, tests/, agent.yaml ...

  [Used 1 tool(s) in 2 step(s)]
> exit
Goodbye!
```

## Testing

```bash
pytest tests/ -v
```

All tests run without network access or external services.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| SMAK as library, not MCP | No IPC overhead for RAG; direct access to 1-hop relation expansion |
| `ChatOpenAI.bind_tools()` | Structured tool calling — no fragile text parsing |
| Protocol-based interfaces | `MemoryStore` accepts any embedding/vector store via duck typing |
| 1-level subagent limit | `AGENT_DEPTH` env var prevents recursive spawning |
| Fallback stubs | Agent starts without SMAK/FAISS using in-memory replacements |

## License

MIT
