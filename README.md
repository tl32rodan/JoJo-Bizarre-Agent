# JoJo's Bizarre Agent

**JoJo（ジョジョ）** — A multi-agent orchestrator inspired by JoJo's Bizarre Adventure.

JoJo is the main protagonist. He channels **Stands** — each Stand is an agent
with a distinct ability (pipeline). JoJo auto-selects the best Stand for the task,
or you can force one manually.

## Stands

| Stand | Ability | Pipeline |
|---|---|---|
| **STAR PLATINUM** | Precision + Time Stop | Default ReAct loop. Can activate "The World" mode for deep reasoning. |
| **GOLD EXPERIENCE** | Life Giver | Orchestrator that spawns sub-agent Stands for complex tasks. |
| **THE WORLD** | Time Stop | Deep chain-of-thought reasoning with dedicated reasoning model. |
| **HIEROPHANT GREEN** | Emerald Splash | Semantic search & RAG — embed → vector search → SMAK expansion. |
| **HARVEST** | Colony | Parallel batch execution via `asyncio.gather`. |
| **SHEER HEART ATTACK** | Automatic Tracking | Fire-and-forget background tasks via subprocess. |

**Stand** = the agent entity. **Ability** = what it does.

## Architecture

```
                    ┌──────────────────────┐
                    │   JoJo (orchestrator) │
                    │   Heartbeat · Memory  │
                    └──────────┬───────────┘
                               │ channels
        ┌────────┬─────────────┼─────────────┬──────────┐
        ▼        ▼             ▼             ▼          ▼
   STAR       GOLD          THE         HIEROPHANT   HARVEST
  PLATINUM   EXPERIENCE    WORLD         GREEN
  (ReAct)    (spawner)    (reasoning)    (RAG)      (parallel)
                │                                       │
                │ spawns                          SHEER HEART
                ├── THE WORLD                      ATTACK
                ├── HIEROPHANT GREEN              (background)
                ├── HARVEST
                └── SHEER HEART ATTACK
```

## Project Structure

```
src/jojo/
├── main.py              # Entry point
├── bootstrap.py         # DI container
├── repl.py              # Interactive REPL
├── config.py            # YAML config
├── core/
│   ├── jojo.py          # Main orchestrator
│   ├── context_manager.py
│   └── prompt_engine.py
├── stands/
│   ├── base.py          # Stand ABC, StandType, StandProfile
│   ├── star_platinum.py # Precision + Time Stop
│   ├── gold_experience.py # Sub-agent spawner
│   ├── the_world.py     # Deep reasoning
│   ├── hierophant_green.py # RAG
│   ├── harvest.py       # Parallel
│   ├── sheer_heart_attack.py # Background
│   └── runner.py        # Subprocess entry
├── mcp/                 # MCP tool integration
├── memory/              # Vector memory (FAISS + SMAK)
└── services/            # Heartbeat, permissions, email, subagent
```

## Usage

```bash
pip install -e .
jojo
```

```
JoJo> What does the auth module do?
  [STAR PLATINUM | 2 tool(s) | 3 step(s)]

JoJo> /timestop Explain the payment system architecture in detail
  「スタープラチナ ザ・ワールド！」
  [STAR PLATINUM | 5 tool(s) | 12 step(s)]

JoJo> /stand gold_experience
  → GOLD EXPERIENCE（ゴールド・エクスペリエンス）
```

## Adding a New Stand

1. Add a value to `StandType` in `stands/base.py`
2. Add a `StandProfile` to `STAND_PROFILES`
3. Create `stands/my_stand.py` implementing the `Stand` ABC
4. Register it in `bootstrap.py`'s `_register_stands()`

## License

MIT
