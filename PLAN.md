# JoJo Stand Redesign — Implementation Plan

## Overview

Redesign the Stand system: 4 Primary Stands + 1 Spawnable, each with distinct
character and abilities. Add OpenCode integration as a swappable sub-agent backend.
Introduce Crazy Diamond (Reviewer) as the missing quality gate role.

```
                         ┌─────────┐
                         │  User   │
                         └────┬────┘
                              │
                         ┌────▼────┐
                         │  JoJo   │  routes by task analysis
                         └────┬────┘
                              │
         ┌────────────────────┼─────────────────────┐
         │                    │                      │
    ┌────▼─────┐       ┌─────▼──────┐       ┌──────▼───────┐
    │   STAR   │       │    GOLD    │       │  HIEROPHANT  │
    │ PLATINUM │       │ EXPERIENCE │       │    GREEN     │
    │ Executor │       │ Orchestrat.│       │  Researcher  │
    │          │       │            │       │              │
    │ OraOra   │       │ Life Giver │       │ Emerald      │
    │ TheWorld │       │ Life Sensor│       │  Splash      │
    └──────────┘       │            │       │ 20m Barrier  │
                       │  spawns ↓  │       └──────────────┘
                       └─────┬──────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │   CRAZY   │ │   SHEER   │ │ SP/HG/CD  │
        │  DIAMOND  │ │   HEART   │ │ instances  │
        │  Reviewer │ │  ATTACK   │ │via OpenCode│
        └───────────┘ └───────────┘ └───────────┘

  Shared Services (NOT Stands):
  ┌──────────────────────────────────────────┐
  │ MemoryStore (FAISS + SMAK)               │
  │ SubAgentBackend (Protocol: OpenCode/tmux)│
  │ StandMessage bus                         │
  │ ToolRegistry (MCP)                       │
  └──────────────────────────────────────────┘
```

---

## Stand Definitions

### 1. STAR PLATINUM 「スタープラチナ」 — The Executor
**User**: Jotaro Kujo (Part 3)
**Character**: Precise, powerful, minimal words. Senior engineer who writes the code.

| Ability | Mode | Description |
|---------|------|-------------|
| **Ora Ora Rush** | Default | Direct ReAct execution. Fast, iterative tool use. |
| **Star Platinum: The World** | `time_stop=True` | Deep CoT with reasoning model. Plans before acting. |

- Absorbs THE WORLD (already implemented as `time_stop` flag)
- Full tool access (MCP + local)
- Memory: recalls relevant past executions

### 2. GOLD EXPERIENCE 「ゴールド・エクスペリエンス」 — The Orchestrator
**User**: Giorno Giovanna (Part 5)
**Character**: Strategic, caring, ruthless about quality. Tech lead who delegates.

| Ability | Description |
|---------|-------------|
| **Life Giver** | Split task → spawn agents (internal Stands or OpenCode sessions). Each gets scoped tools. |
| **Life Sensor** | Monitor status, examine output, abort/retry. Cherishes agents. |

- Spawns via `SubAgentBackend` (OpenCode or tmux fallback)
- Post-task: triggers memory compaction + lesson extraction
- MCP-aware: routes tools to the right agent

### 3. HIEROPHANT GREEN 「ハイエロファントグリーン」 — The Researcher
**User**: Noriaki Kakyoin (Part 3)
**Character**: Long-range, methodical, thorough. Staff engineer who investigates.

| Ability | Description |
|---------|-------------|
| **Emerald Splash** | Deep RAG: embed → vector search → SMAK relation expansion → consolidate. |
| **20m Emerald Barrier** | Load SKILL.md methodology files (TDD, debugging, retrospective, design review) and apply as structured analysis frameworks. |

- **Read-only**: never modifies code (matches OpenClaw Research Specialist pattern)
- Has LLM access (upgrade from pure pipeline to LLM-guided research)
- Outputs structured reports / methodology-guided plans

### 4. CRAZY DIAMOND 「クレイジー・ダイヤモンド」 — The Reviewer (**NEW**)
**User**: Josuke Higashikata (Part 4)
**Character**: Fixes things, restores to correct state. Obsessed with quality.

| Ability | Description |
|---------|-------------|
| **Restoration** | Code review: read diffs, detect bugs/security/style issues, suggest fixes. |
| **Breakdown** | Verify output against requirements, check edge cases, validate correctness. |

- Quality gate for Gold Experience (reviews spawned agent output)
- Can be invoked directly via `/stand crazy_diamond`
- Reads SKILL.md patterns as review checklists
- Has tool access for running tests/linters but NOT for writing code

### 5. SHEER HEART ATTACK 「シアーハートアタック」 — Background Worker (spawnable)
**User**: Yoshikage Kira (Part 4)
**Character**: Automatic, relentless, fire-and-forget.

| Ability | Description |
|---------|-------------|
| **Automatic Tracking** | Fire-and-forget via SubAgentBackend. Poll or forget. |

- Spawned only by Gold Experience
- Backend: OpenCode sessions (new) or tmux (fallback)

### Retired / Absorbed

| Stand | Absorbed By | Reason |
|-------|-------------|--------|
| THE WORLD | Star Platinum's `time_stop` mode | Already implemented this way |
| HARVEST | Gold Experience's parallel spawning | GE spawns N agents concurrently |

---

## Phase 1: Foundation (SubAgentBackend + StandMessage)

### Step 1.1 — SubAgentBackend Protocol

**File**: `src/jojo/services/backend.py` (NEW)

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass(frozen=True)
class TaskResult:
    handle_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None

class SubAgentBackend(Protocol):
    async def spawn(self, task: str, *, agent: str = "default",
                    tools: list[str] | None = None,
                    context: dict[str, Any] | None = None) -> str: ...
    async def poll(self, handle_id: str) -> TaskStatus: ...
    async def collect(self, handle_id: str, timeout: float = 300) -> TaskResult: ...
    async def abort(self, handle_id: str) -> None: ...
    async def cleanup(self, handle_id: str) -> None: ...
```

### Step 1.2 — TmuxBackend (wraps existing SubAgentSpawner)

**File**: `src/jojo/services/backend_tmux.py` (NEW)

Thin adapter that wraps the existing `SubAgentSpawner` to implement `SubAgentBackend`.
No behavior change — just the interface alignment.

### Step 1.3 — OpenCodeBackend

**File**: `src/jojo/services/backend_opencode.py` (NEW)

Uses `opencode-ai` Python SDK:
- `spawn()` → `client.session.create()` + `client.session.chat()`
- `poll()` → check session status via events
- `collect()` → `client.session.messages()` to get final response
- `abort()` → `client.session.abort()`
- `cleanup()` → `client.session.delete()`

Connects to a running `opencode serve` instance.
Falls back gracefully if OpenCode is not running.

### Step 1.4 — StandMessage Protocol

**File**: `src/jojo/core/message_bus.py` (NEW)

```python
@dataclass(frozen=True)
class StandMessage:
    from_stand: StandType
    to_stand: StandType | None  # None = broadcast
    msg_type: str               # "task" | "result" | "status" | "feedback"
    content: Any
    correlation_id: str         # links related messages
    timestamp: float

class MessageBus:
    """Simple in-process pub/sub for Stand-to-Stand communication."""
    def publish(self, msg: StandMessage) -> None: ...
    def subscribe(self, stand: StandType, callback: Callable) -> None: ...
    def get_history(self, correlation_id: str) -> list[StandMessage]: ...
```

### Step 1.5 — Config additions

**File**: `src/jojo/config.py` (MODIFY)

```python
@dataclass(frozen=True)
class OpenCodeConfig:
    enabled: bool = False
    base_url: str = "http://localhost:4096"
    password: str = ""
    default_agent: str = "build"
    timeout_seconds: int = 300

@dataclass(frozen=True)
class SubAgentConfig:
    # ... existing fields ...
    backend: str = "tmux"  # "tmux" | "opencode"
```

Add `opencode: OpenCodeConfig` field to `AgentConfig`.

**File**: `agent.yaml` (MODIFY)

```yaml
subagent:
  backend: opencode           # NEW: "tmux" | "opencode"
  # ... existing fields ...

opencode:                     # NEW section
  enabled: true
  base_url: ${OPENCODE_BASE_URL:-http://localhost:4096}
  password: ${OPENCODE_SERVER_PASSWORD:-}
  default_agent: build
  timeout_seconds: 300
```

---

## Phase 2: Stand Redesign

### Step 2.1 — Update base.py (StandType + Profiles)

**File**: `src/jojo/stands/base.py` (MODIFY)

- Remove: `THE_WORLD`, `HARVEST` from `StandType`
- Add: `CRAZY_DIAMOND` to `StandType`
- Update `STAND_PROFILES` accordingly
- Update `SPAWNABLE_TYPES` concept → move to Gold Experience

New StandType enum:
```python
class StandType(Enum):
    STAR_PLATINUM = "star_platinum"
    GOLD_EXPERIENCE = "gold_experience"
    HIEROPHANT_GREEN = "hierophant_green"
    CRAZY_DIAMOND = "crazy_diamond"
    SHEER_HEART_ATTACK = "sheer_heart_attack"
```

New profiles:
```python
STAND_PROFILES = {
    StandType.STAR_PLATINUM: StandProfile(
        name="STAR PLATINUM", name_jp="スタープラチナ",
        user="Jotaro Kujo", part=3,
        ability_name="Ora Ora Rush + The World",
        ability_description="Direct ReAct executor. Ora Ora for building, The World for deep reasoning.",
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.GOLD_EXPERIENCE: StandProfile(
        name="GOLD EXPERIENCE", name_jp="ゴールド・エクスペリエンス",
        user="Giorno Giovanna", part=5,
        ability_name="Life Giver + Life Sensor",
        ability_description="Orchestrates complex tasks. Spawns, monitors, and examines sub-agents.",
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.HIEROPHANT_GREEN: StandProfile(
        name="HIEROPHANT GREEN", name_jp="法皇の緑",
        user="Noriaki Kakyoin", part=3,
        ability_name="Emerald Splash + 20m Barrier",
        ability_description="Deep research via RAG + methodology enforcement via SKILL.md. Read-only.",
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.CRAZY_DIAMOND: StandProfile(
        name="CRAZY DIAMOND", name_jp="クレイジー・ダイヤモンド",
        user="Josuke Higashikata", part=4,
        ability_name="Restoration + Breakdown",
        ability_description="Code review, quality gate, bug detection. Fixes what's broken.",
        spawn_mode=SpawnMode.IN_PROCESS,
    ),
    StandType.SHEER_HEART_ATTACK: StandProfile(
        name="SHEER HEART ATTACK", name_jp="シアーハートアタック",
        user="Yoshikage Kira", part=4,
        ability_name="Automatic Tracking",
        ability_description="Fire-and-forget background tasks via SubAgentBackend.",
        spawn_mode=SpawnMode.SUBAGENT,
    ),
}
```

### Step 2.2 — Star Platinum refactor

**File**: `src/jojo/stands/star_platinum.py` (MODIFY)

Minimal changes — already works correctly:
- Update docstring to reflect "Ora Ora Rush" + "The World" naming
- System prompt: make the two modes more distinct in character
- Keep the existing `time_stop` flag and `reasoning_llm` logic
- No structural changes needed

### Step 2.3 — Hierophant Green upgrade (Emerald Splash + 20m Barrier)

**File**: `src/jojo/stands/hierophant_green.py` (MODIFY — significant)

Current state: Pure pipeline (no LLM, no tools). Just vector search + SMAK.

Upgrade to:
1. **Emerald Splash** (existing RAG pipeline) — keep as-is
2. **20m Barrier** (NEW) — LLM-guided analysis using SKILL.md patterns
3. Add LLM parameter for Barrier mode
4. Load skills from `SkillLoader` and inject as methodology frameworks
5. Enforce read-only: no write/exec tools, only read/search tools

```python
class HierophantGreen(Stand):
    def __init__(self, memory_store, query_service, llm=None, skills=None, tool_registry=None):
        ...

    async def execute(self, task, context=None):
        ctx = context or {}
        mode = ctx.get("mode", "splash")  # "splash" | "barrier"

        if mode == "barrier":
            return await self._barrier_mode(task, ctx)
        return await self._splash_mode(task, ctx)

    async def _splash_mode(self, task, ctx):
        # Existing RAG pipeline (unchanged)
        ...

    async def _barrier_mode(self, task, ctx):
        # 1. Run Emerald Splash first for context
        # 2. Load applicable SKILL.md methodology
        # 3. LLM analysis guided by methodology
        # 4. Return structured report
        ...
```

### Step 2.4 — Crazy Diamond (NEW Stand)

**File**: `src/jojo/stands/crazy_diamond.py` (NEW)

```python
class CrazyDiamond(Stand):
    """「直す」 — I'll fix it."""

    stand_type = StandType.CRAZY_DIAMOND

    def __init__(self, llm, tool_registry, memory, skills=None):
        ...

    async def execute(self, task, context=None):
        ctx = context or {}
        mode = ctx.get("mode", "restoration")  # "restoration" | "breakdown"

        if mode == "breakdown":
            return await self._breakdown(task, ctx)
        return await self._restoration(task, ctx)

    async def _restoration(self, task, ctx):
        # Code review mode:
        # 1. Recall relevant memories + SKILL.md review checklists
        # 2. ReAct loop: read code, run tests/linters, identify issues
        # 3. Suggest fixes (or apply if authorized)
        # Tools: read_file, search, run_tests, run_linter (NO write_file)
        ...

    async def _breakdown(self, task, ctx):
        # Output verification mode:
        # 1. Receive output from another Stand (via context)
        # 2. Check against requirements
        # 3. Verify edge cases
        # 4. Return pass/fail with details
        ...
```

Tool access: Can read files, run tests, run linters. Cannot write files directly
(unless Gold Experience explicitly authorizes a fix pass).

### Step 2.5 — Gold Experience refactor (Life Giver + Life Sensor)

**File**: `src/jojo/stands/gold_experience.py` (MODIFY — major)

New capabilities:
1. **spawn_opencode_agent** tool — delegates to SubAgentBackend
2. **Life Sensor** — check_agent_status, examine_output tools
3. **Quality gate** — route output through Crazy Diamond before accepting
4. **Post-task compaction** — extract lessons, store in memory
5. **Parallel spawning** — absorbs Harvest's parallel execution

```python
class GoldExperience(Stand):
    def __init__(self, llm, tool_registry, memory, stand_factory,
                 backend: SubAgentBackend | None = None,
                 message_bus: MessageBus | None = None):
        ...

    async def execute(self, task, context=None):
        # Enhanced ReAct loop with:
        # - summon_stand() — internal Stands
        # - spawn_agent() — OpenCode/tmux background agents
        # - check_status() — Life Sensor
        # - examine_output() — quality check (may invoke Crazy Diamond)
        # - compact_memory() — post-task learning
        ...

    async def _handle_spawn_agent(self, args, ctx):
        """Spawn via SubAgentBackend (OpenCode or tmux)."""
        handle = await self._backend.spawn(
            task=args["task"],
            agent=args.get("agent", "build"),
            tools=args.get("tools"),
        )
        # Track active handles for Life Sensor
        self._active_handles[handle] = args
        return f"Agent spawned: {handle}"

    async def _handle_check_status(self, args, ctx):
        """Life Sensor — monitor spawned agents."""
        handle = args["handle_id"]
        status = await self._backend.poll(handle)
        if status == TaskStatus.COMPLETED:
            result = await self._backend.collect(handle)
            return f"Completed: {result.output}"
        return f"Status: {status.value}"

    async def _post_task_compact(self, task, results):
        """Extract lessons and compact into memory."""
        # LLM summarizes: what worked, what failed, patterns discovered
        # Store as tagged memory entry
        ...
```

### Step 2.6 — Sheer Heart Attack refactor

**File**: `src/jojo/stands/sheer_heart_attack.py` (MODIFY)

Replace `SubAgentSpawner` dependency with `SubAgentBackend`:

```python
class SheerHeartAttack(Stand):
    def __init__(self, backend: SubAgentBackend | None = None, ...):
        self._backend = backend
        ...

    async def execute(self, task, context=None):
        handle = await self._backend.spawn(task, agent="build")

        if fire_and_forget:
            return self._succeed(f"Background task: {handle}")

        result = await self._backend.collect(handle, timeout=self._timeout)
        return self._succeed(result.output)
```

---

## Phase 3: Wiring & Integration

### Step 3.1 — Bootstrap updates

**File**: `src/jojo/bootstrap.py` (MODIFY)

- Remove: TheWorld, Harvest registration
- Add: CrazyDiamond registration
- Add: SubAgentBackend selection (OpenCode vs tmux)
- Add: MessageBus creation
- Update: GoldExperience gets `backend` and `message_bus`
- Update: SheerHeartAttack gets `backend`
- Update: HierophantGreen gets `llm` and `skills`
- Update: stand_factory to produce CrazyDiamond instead of TheWorld/Harvest

### Step 3.2 — JoJo orchestrator updates

**File**: `src/jojo/core/jojo.py` (MODIFY)

- Update `_STAND_HINTS` for new Stand types:
  ```python
  _STAND_HINTS = {
      GOLD_EXPERIENCE: ["spawn", "orchestrate", "complex", "multi-step", ...],
      HIEROPHANT_GREEN: ["research", "investigate", "analyze", "study", "plan", ...],
      CRAZY_DIAMOND: ["review", "check", "fix", "bug", "quality", ...],
  }
  ```
- Remove THE_WORLD, HARVEST references

### Step 3.3 — REPL updates

**File**: `src/jojo/repl.py` (MODIFY)

- Update banner to show new Stand roster
- Add `/barrier <query>` shortcut for Hierophant Green barrier mode
- Add `/review <query>` shortcut for Crazy Diamond

### Step 3.4 — Delete retired files

- `src/jojo/stands/the_world.py` → DELETE
- `src/jojo/stands/harvest.py` → DELETE

(The World's logic is already in Star Platinum. Harvest's logic moves to GE.)

### Step 3.5 — Update runner.py

**File**: `src/jojo/stands/runner.py` (MODIFY)

- Remove THE_WORLD, HARVEST cases
- Add CRAZY_DIAMOND case

### Step 3.6 — Update pyproject.toml

**File**: `pyproject.toml` (MODIFY)

Add `opencode-ai` as optional dependency:
```toml
[project.optional-dependencies]
opencode = ["opencode-ai>=0.1.0a30"]
```

### Step 3.7 — agent.yaml update

**File**: `agent.yaml` (MODIFY)

Update banner, add opencode section, add skills paths config.

---

## Phase 4: Memory Compaction & Learning

### Step 4.1 — Memory compaction service

**File**: `src/jojo/memory/compactor.py` (NEW)

Called by Gold Experience after completing complex tasks:
```python
class MemoryCompactor:
    def __init__(self, llm, memory_store):
        ...

    async def compact(self, task: str, results: list[StandResult]) -> str:
        """Extract lessons learned, store as compact memory."""
        # 1. Summarize what happened
        # 2. Extract: what worked, what failed, patterns
        # 3. Store tagged entry: type="lesson", stands=[...], task_type=...
        # 4. Prune redundant old memories (optional)
        ...
```

Owned by Gold Experience (the orchestrator owns the learning loop).

### Step 4.2 — Per-Stand episodic memory

Each Stand already auto-memorizes via JoJo. Enhance with:
- Tag memories with `stand_type` + `ability_mode` for better recall
- ConversationSummarizer already exists — wire it to auto-trigger

---

## Phase 5: SKILL.md Foundation

### Step 5.1 — Create initial SKILL.md files

```
skills/
├── debugging/SKILL.md      — Reproduce → isolate → fix → verify
├── tdd/SKILL.md            — Write tests first, then implement
├── retrospective/SKILL.md  — What worked, what didn't, what to change
└── design_review/SKILL.md  — SOLID, DRY, separation of concerns
```

Used by:
- Hierophant Green (Barrier mode): as research/analysis frameworks
- Crazy Diamond: as review checklists

---

## Execution Order

1. **Phase 1** (Foundation) — backend protocol, configs
2. **Phase 2** (Stand redesign) — the main changes
3. **Phase 3** (Wiring) — bootstrap, orchestrator, cleanup
4. **Phase 4** (Memory) — compaction
5. **Phase 5** (Skills) — SKILL.md files

Each phase is independently testable. Phase 1+2 can be developed in parallel.

---

## Files Changed Summary

| File | Action | Phase |
|------|--------|-------|
| `src/jojo/services/backend.py` | NEW | 1 |
| `src/jojo/services/backend_tmux.py` | NEW | 1 |
| `src/jojo/services/backend_opencode.py` | NEW | 1 |
| `src/jojo/core/message_bus.py` | NEW | 1 |
| `src/jojo/config.py` | MODIFY | 1 |
| `src/jojo/stands/base.py` | MODIFY | 2 |
| `src/jojo/stands/star_platinum.py` | MODIFY (minor) | 2 |
| `src/jojo/stands/hierophant_green.py` | MODIFY (major) | 2 |
| `src/jojo/stands/crazy_diamond.py` | NEW | 2 |
| `src/jojo/stands/gold_experience.py` | MODIFY (major) | 2 |
| `src/jojo/stands/sheer_heart_attack.py` | MODIFY | 2 |
| `src/jojo/bootstrap.py` | MODIFY | 3 |
| `src/jojo/core/jojo.py` | MODIFY | 3 |
| `src/jojo/repl.py` | MODIFY | 3 |
| `src/jojo/stands/the_world.py` | DELETE | 3 |
| `src/jojo/stands/harvest.py` | DELETE | 3 |
| `src/jojo/stands/runner.py` | MODIFY | 3 |
| `pyproject.toml` | MODIFY | 3 |
| `agent.yaml` | MODIFY | 3 |
| `src/jojo/memory/compactor.py` | NEW | 4 |
| `skills/debugging/SKILL.md` | NEW | 5 |
| `skills/tdd/SKILL.md` | NEW | 5 |
| `skills/retrospective/SKILL.md` | NEW | 5 |
| `skills/design_review/SKILL.md` | NEW | 5 |
