"""GOLD EXPERIENCE（ゴールド・エクスペリエンス）— The Orchestrator.

Ability 1: Life Giver — spawns and manages sub-agent Stands + OpenCode agents.
Ability 2: Life Sensor — monitors agent status, examines output, quality gate.

Giorno's Stand.  Creates life, gives purpose to each creation.
Strategic, caring, but ruthless about quality.

「このジョルノ・ジョバァーナには夢がある！」
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jojo.stands.base import (
    Stand, StandProfile, StandResult, StandStatus, StandType,
    STAND_PROFILES,
)

logger = logging.getLogger(__name__)

# Stands that Gold Experience can summon in-process
SPAWNABLE_TYPES = (
    StandType.HIEROPHANT_GREEN,
    StandType.CRAZY_DIAMOND,
    StandType.SHEER_HEART_ATTACK,
)


class GoldExperience(Stand):
    """「無駄無駄無駄！」"""

    stand_type = StandType.GOLD_EXPERIENCE

    def __init__(
        self,
        llm: Any,
        tool_registry: Any,
        memory: Any,
        stand_factory: Any | None = None,
        backend: Any | None = None,
        message_bus: Any | None = None,
        max_steps: int = 20,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._tools = tool_registry
        self._memory = memory
        self._factory = stand_factory  # callable(StandType) -> Stand
        self._backend = backend        # SubAgentBackend (OpenCode or tmux)
        self._bus = message_bus        # MessageBus for inter-Stand comms
        self._max_steps = max_steps
        self._active_handles: dict[str, dict[str, Any]] = {}

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> StandResult:
        """Orchestrator ReAct loop — Life Giver + Life Sensor."""
        from jojo.core.context_manager import ContextManager

        self._status = StandStatus.ACTIVE
        ctx = context or {}
        max_steps = ctx.get("max_steps", self._max_steps)

        tool_desc = self._tools.get_tool_descriptions()
        memory_text = _format_memories(self._memory, task)

        system_prompt = (
            "You are GOLD EXPERIENCE（ゴールド・エクスペリエンス）.\n"
            "User: Giorno Giovanna.  You have a dream — and you will achieve it.\n\n"
            "## Abilities\n"
            "1. **Life Giver** — Break complex tasks into sub-tasks.  Spawn agents\n"
            "   to handle each piece.  Give them clear goals and freedom to work.\n"
            "2. **Life Sensor** — Monitor spawned agents.  Examine their output.\n"
            "   If quality is lacking, send feedback or reassign.\n\n"
            "## Spawning Options\n"
            f"{_describe_spawnable()}\n"
            f"{_describe_backend(self._backend)}\n\n"
            "## Philosophy\n"
            "- Give agents 自由發揮的空間 (room to work freely) under scoped access.\n"
            "- Examine ALL output before accepting — you are the quality gate.\n"
            "- Cherish every agent you spawn.  Monitor their status.  Don't abandon them.\n"
            "- After the task, reflect on what worked and what didn't.\n"
            "「無駄無駄無駄！」 on bad output.  Route to Crazy Diamond for review when unsure.\n\n"
            f"## Available Tools\n{tool_desc}"
            f"{memory_text}"
        )

        ctx_mgr = ContextManager(max_tokens=ctx.get("max_history_tokens", 8000))
        ctx_mgr.add_message({"role": "system", "content": system_prompt})
        ctx_mgr.add_message({"role": "user", "content": task})

        tool_records: list[dict[str, Any]] = []
        stands_used: list[str] = []

        try:
            for step in range(max_steps):
                response = self._llm.invoke(ctx_mgr.get_messages())
                tool_calls = _extract_tool_calls(response)

                if not tool_calls:
                    answer = _extract_text(response)
                    ctx_mgr.add_message({"role": "assistant", "content": answer})

                    # Post-task compaction
                    await self._post_task_compact(task, answer)

                    return self._succeed(
                        answer,
                        steps=step + 1,
                        tool_calls=tool_records,
                        stands_used=stands_used,
                    )

                ctx_mgr.add_message({
                    "role": "assistant",
                    "content": _extract_text(response),
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    name = tc["name"]
                    args = tc.get("arguments", {})

                    if name == "summon_stand":
                        result_text = await self._handle_summon(args, ctx)
                        stands_used.append(args.get("stand_name", "unknown"))
                    elif name == "spawn_agent":
                        result_text = await self._handle_spawn_agent(args, ctx)
                        stands_used.append(f"opencode:{args.get('agent', 'build')}")
                    elif name == "check_agent_status":
                        result_text = await self._handle_check_status(args)
                    elif name == "collect_agent_result":
                        result_text = await self._handle_collect(args)
                    else:
                        result_text = await self._tools.call(name, args)

                    result_text = ContextManager.truncate_tool_result(str(result_text))
                    ctx_mgr.add_message({
                        "role": "tool",
                        "content": result_text,
                        "tool_call_id": tc.get("id", ""),
                    })
                    tool_records.append({
                        "name": name, "arguments": args, "result": result_text,
                    })

            return self._succeed(
                "Gold Experience: max steps reached. 無駄無駄…",
                steps=max_steps,
                tool_calls=tool_records,
                stands_used=stands_used,
            )
        except Exception as exc:
            logger.exception("Gold Experience failed — task_id=%s", self._task_id)
            return self._fail(str(exc))
        finally:
            # Cleanup any remaining handles
            await self._cleanup_handles()

    # ------------------------------------------------------------------
    # summon_stand — in-process Stand spawning
    # ------------------------------------------------------------------

    async def _handle_summon(self, args: dict[str, Any], ctx: dict[str, Any]) -> str:
        """Summon a sub-agent Stand and execute its task."""
        stand_name = args.get("stand_name", args.get("name", ""))
        sub_task = args.get("task", "")

        if not self._factory:
            return "[GOLD EXPERIENCE] No stand factory available."

        try:
            stand_type = _resolve_stand_type(stand_name)
            if stand_type not in SPAWNABLE_TYPES:
                return f"[GOLD EXPERIENCE] Cannot spawn {stand_name} — not spawnable."

            stand = self._factory(stand_type)
            result = await stand.execute(sub_task, ctx)

            # Publish result to message bus
            if self._bus:
                from jojo.core.message_bus import StandMessage
                self._bus.publish(StandMessage(
                    from_stand=stand_type.value,
                    to_stand=self.stand_type.value,
                    msg_type="result",
                    content=str(result.output)[:500] if result.output else result.error,
                ))

            if result.status == StandStatus.RETIRED:
                return f"[{result.stand_type.value}] Completed.\n{result.output}"
            return f"[{result.stand_type.value}] Failed: {result.error}"
        except Exception as exc:
            return f"[GOLD EXPERIENCE] Summon failed: {exc}"

    # ------------------------------------------------------------------
    # spawn_agent — OpenCode / tmux backend spawning
    # ------------------------------------------------------------------

    async def _handle_spawn_agent(self, args: dict[str, Any], ctx: dict[str, Any]) -> str:
        """Spawn a task via SubAgentBackend (OpenCode or tmux)."""
        if self._backend is None:
            return "[GOLD EXPERIENCE] No SubAgentBackend available. Use summon_stand instead."

        sub_task = args.get("task", "")
        agent = args.get("agent", "build")
        tools = args.get("tools")

        try:
            handle_id = await self._backend.spawn(
                sub_task, agent=agent, tools=tools, context=ctx,
            )
            self._active_handles[handle_id] = {
                "task": sub_task, "agent": agent,
            }
            logger.info("Gold Experience spawned agent — handle=%s, agent=%s", handle_id, agent)
            return f"[GOLD EXPERIENCE] Agent spawned: handle={handle_id}, agent={agent}. Use check_agent_status or collect_agent_result to monitor."
        except Exception as exc:
            return f"[GOLD EXPERIENCE] Spawn failed: {exc}"

    async def _handle_check_status(self, args: dict[str, Any]) -> str:
        """Life Sensor — check a spawned agent's status."""
        if self._backend is None:
            return "[GOLD EXPERIENCE] No backend."

        handle_id = args.get("handle_id", "")
        try:
            status = await self._backend.poll(handle_id)
            return f"[LIFE SENSOR] Agent {handle_id}: {status.value}"
        except Exception as exc:
            return f"[LIFE SENSOR] Check failed: {exc}"

    async def _handle_collect(self, args: dict[str, Any]) -> str:
        """Collect a completed agent's result."""
        if self._backend is None:
            return "[GOLD EXPERIENCE] No backend."

        handle_id = args.get("handle_id", "")
        timeout = args.get("timeout", 120)
        try:
            result = await self._backend.collect(handle_id, timeout=timeout)
            self._active_handles.pop(handle_id, None)
            if result.error:
                return f"[GOLD EXPERIENCE] Agent {handle_id} failed: {result.error}"
            return f"[GOLD EXPERIENCE] Agent {handle_id} completed:\n{result.output}"
        except Exception as exc:
            return f"[GOLD EXPERIENCE] Collect failed: {exc}"

    # ------------------------------------------------------------------
    # Post-task learning
    # ------------------------------------------------------------------

    async def _post_task_compact(self, task: str, final_output: str) -> None:
        """Extract lessons learned and compact into memory."""
        if self._memory is None:
            return
        try:
            self._memory.store(
                f"[GE Lesson] Task: {task[:200]}\nOutcome: {final_output[:300]}",
                {"type": "lesson", "stand": "gold_experience"},
            )
        except Exception:
            logger.debug("Gold Experience: memory compaction failed (non-critical)")

    async def _cleanup_handles(self) -> None:
        """Best-effort cleanup of any remaining active handles."""
        if self._backend is None:
            return
        for handle_id in list(self._active_handles):
            try:
                await self._backend.cleanup(handle_id)
            except Exception:
                pass
        self._active_handles.clear()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resolve_stand_type(name: str) -> StandType:
    name_lower = name.lower().strip()
    try:
        return StandType(name_lower)
    except ValueError:
        pass
    for st in SPAWNABLE_TYPES:
        p = STAND_PROFILES[st]
        if name_lower in p.name.lower() or name_lower in st.name.lower():
            return st
    raise ValueError(
        f"Unknown Stand: '{name}'. Spawnable: {[st.value for st in SPAWNABLE_TYPES]}"
    )


def _describe_spawnable() -> str:
    lines = ["### Internal Stands (summon_stand)"]
    for st in SPAWNABLE_TYPES:
        p = STAND_PROFILES[st]
        lines.append(f"- `summon_stand(\"{st.value}\", task)` — {p.name}: {p.ability_description}")
    return "\n".join(lines)


def _describe_backend(backend: Any) -> str:
    if backend is None:
        return "### External Agents\n(No SubAgentBackend configured)"
    return (
        "### External Agents (spawn_agent)\n"
        "- `spawn_agent(agent=\"build\", task=...)` — Full coding agent (file edit, shell, tools)\n"
        "- `spawn_agent(agent=\"plan\", task=...)` — Read-only planning/analysis agent\n"
        "- `check_agent_status(handle_id=...)` — Life Sensor: check status\n"
        "- `collect_agent_result(handle_id=...)` — Collect completed result"
    )


def _format_memories(memory: Any, query: str) -> str:
    if memory is None:
        return ""
    try:
        hits = memory.recall(query, top_k=5)
        if not hits:
            return ""
        lines = [f"- [{h.match_type}] {h.content}" for h in hits]
        return "\n\n## Relevant Memories\n" + "\n".join(lines)
    except Exception:
        return ""


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    if hasattr(response, "tool_calls") and response.tool_calls:
        calls = []
        for tc in response.tool_calls:
            if isinstance(tc, dict):
                calls.append(tc)
            elif hasattr(tc, "name"):
                calls.append({
                    "id": getattr(tc, "id", ""),
                    "name": tc.name,
                    "arguments": getattr(tc, "args", {}),
                })
        return calls
    if hasattr(response, "additional_kwargs"):
        raw = response.additional_kwargs.get("tool_calls", [])
        calls = []
        for tc in raw:
            func = tc.get("function", {})
            args = func.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            calls.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": args,
            })
        return calls
    return []


def _extract_text(response: Any) -> str:
    return str(response.content) if hasattr(response, "content") else str(response)
