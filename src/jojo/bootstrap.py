"""Dependency injection and service wiring for JoJo.

Single Responsibility: This module's only job is to construct the
complete dependency graph from configuration.  No business logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jojo.config import AgentConfig, load_agent_config
from jojo.core.jojo import JoJo
from jojo.jojo_stands import JOJO_STAND_CLASSES
from jojo.jojo_stands.base import JoJoStandType
from jojo.memory.store import MemoryStore
from jojo.mcp.client import MCPClientManager
from jojo.mcp.skill_loader import load_skills_from_paths
from jojo.mcp.tool_registry import ToolRegistry
from jojo.services.email_notifier import EmailNotifier
from jojo.services.heartbeat import HeartbeatService
from jojo.services.permission import PermissionManager

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Holds all wired-up services.  Passed to the REPL for runtime use."""
    config: AgentConfig
    jojo: JoJo
    memory: MemoryStore
    mcp_client: MCPClientManager
    heartbeat: HeartbeatService


async def build_app(config_path: str = "agent.yaml") -> AppContext:
    """Wire all dependencies and return a ready-to-use AppContext."""
    config = load_agent_config(config_path)

    llm, reasoning_llm = _build_llms(config)
    mcp_client = await _build_mcp_client(config)
    embedder = _build_embedder(config)
    memory = _build_memory(config, embedder)
    permissions = PermissionManager(config.permissions)
    tool_registry = await _build_tool_registry(mcp_client)
    email = EmailNotifier(config.email)

    # Build main JoJo orchestrator
    jojo = JoJo(
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        permissions=permissions,
        config=config,
    )

    # Register all 6 JoJo Stand personas
    for stand_type, stand_class in JOJO_STAND_CLASSES.items():
        persona = stand_class(
            llm=llm,
            tool_registry=tool_registry,
            memory=memory,
            config=config,
        )
        # Gold Experience needs a stand spawner for summoning non-JoJo stands
        if stand_type == JoJoStandType.GOLD_EXPERIENCE:
            spawner = _build_stand_spawner(
                config, llm, reasoning_llm, tool_registry, memory,
            )
            if spawner and hasattr(persona, "set_stand_spawner"):
                persona.set_stand_spawner(spawner)

        jojo.register_persona(stand_type, persona)

    # Heartbeat belongs to JoJo
    heartbeat = _build_heartbeat(config, llm, email)
    heartbeat.start()

    return AppContext(
        config=config,
        jojo=jojo,
        memory=memory,
        mcp_client=mcp_client,
        heartbeat=heartbeat,
    )


async def teardown_app(ctx: AppContext) -> None:
    """Graceful shutdown of all services."""
    ctx.heartbeat.stop()
    await ctx.mcp_client.disconnect_all()
    ctx.memory.persist()


# ---------------------------------------------------------------------------
# Private builders (each responsible for one concern)
# ---------------------------------------------------------------------------

def _build_llms(config: AgentConfig) -> tuple[Any, Any | None]:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        base_url=config.llm.base_url,
        model=config.llm.model,
        api_key=config.llm.api_key,
    )

    reasoning_model = config.llm.models.get("reasoning")
    reasoning_llm = None
    if reasoning_model and reasoning_model != config.llm.model:
        reasoning_llm = ChatOpenAI(
            base_url=config.llm.base_url,
            model=reasoning_model,
            api_key=config.llm.api_key,
        )

    return llm, reasoning_llm


def _build_embedder(config: AgentConfig) -> Any:
    from smak.utils.embedding import InternalNomicEmbedding
    from smak.config import EmbeddingConfig as SmakEmbeddingConfig

    smak_cfg = SmakEmbeddingConfig(
        api_base=config.embedding.api_base,
        model=config.embedding.model,
    )
    return InternalNomicEmbedding(embedding_config=smak_cfg)


def _build_memory(config: AgentConfig, embedder: Any) -> MemoryStore:
    from faiss_storage_lib.engine.faiss_engine import FaissEngine

    dimension = embedder.get_embedding_dimension()
    vs = FaissEngine(config.memory.storage_dir, dimension=dimension)
    return MemoryStore(vector_store=vs, embedder=embedder)


async def _build_mcp_client(config: AgentConfig) -> MCPClientManager:
    client = MCPClientManager()
    if config.mcp_servers:
        try:
            await client.connect_all(config.mcp_servers)
        except Exception:
            logger.exception("Failed to connect to MCP servers")
    return client


async def _build_tool_registry(mcp_client: MCPClientManager) -> ToolRegistry:
    registry = ToolRegistry()
    if mcp_client.server_names:
        await registry.register_mcp_tools(mcp_client)
    skills = load_skills_from_paths([Path(".")])
    registry.enhance_with_skills(skills)
    return registry


def _build_stand_spawner(
    config: AgentConfig,
    llm: Any,
    reasoning_llm: Any | None,
    tool_registry: ToolRegistry,
    memory: MemoryStore,
) -> Any | None:
    """Build the spawnable-stand factory (used by Gold Experience JoJo persona)."""
    query_service = _build_query_service(config)
    subagent_spawner = _build_subagent_spawner(config)
    harvest_worker = _make_harvest_worker(llm, tool_registry, memory)

    # Re-use the old GoldExperience factory from stands/ if it exists
    try:
        from jojo.stands.base import StandType, STAND_PROFILES

        class StandSpawner:
            """Lightweight factory for spawning non-JoJo stands."""

            def __init__(self) -> None:
                self._active: list[Any] = []

            def summon_by_name(self, name: str) -> Any:
                try:
                    stand_type = StandType(name.lower().strip())
                except ValueError:
                    name_lower = name.lower()
                    for st in StandType:
                        profile = STAND_PROFILES[st]
                        if name_lower in profile["name"].lower() or name_lower == st.name.lower():
                            stand_type = st
                            break
                    else:
                        raise ValueError(
                            f"Unknown Stand: '{name}'. "
                            f"Available: {[st.value for st in StandType]}"
                        )
                return self.summon(stand_type)

            def summon(self, stand_type: StandType) -> Any:
                if stand_type == StandType.THE_WORLD:
                    from jojo.stands.the_world import TheWorld
                    stand = TheWorld(llm=reasoning_llm or llm, tool_registry=tool_registry, max_steps=30)
                elif stand_type == StandType.HIEROPHANT_GREEN:
                    from jojo.stands.hierophant_green import HierophantGreen
                    stand = HierophantGreen(memory_store=memory, query_service=query_service, top_k=10)
                elif stand_type == StandType.HARVEST:
                    from jojo.stands.harvest import Harvest
                    max_c = config.subagent.max_concurrent if config else 10
                    stand = Harvest(worker=harvest_worker, max_concurrency=max_c)
                elif stand_type == StandType.SHEER_HEART_ATTACK:
                    from jojo.stands.sheer_heart_attack import SheerHeartAttack
                    timeout = config.subagent.timeout_seconds if config else 600
                    stand = SheerHeartAttack(spawner=subagent_spawner, timeout=timeout)
                else:
                    raise ValueError(f"Unknown Stand type: {stand_type}")
                self._active.append(stand)
                return stand

            def describe_stands(self) -> str:
                lines = ["## Spawnable Stands\n"]
                for st in StandType:
                    p = STAND_PROFILES[st]
                    mode = p.get("spawn_mode", "in_process")
                    lines.append(f"### {p['name']}  [{p['ability']}]  (mode: {mode})")
                    lines.append(f"{p['description']}\n")
                    lines.append(f"Summon: `summon_stand(\"{st.value}\")`\n")
                return "\n".join(lines)

        return StandSpawner()
    except Exception:
        logger.info("Stand spawner not available — Gold Experience cannot summon sub-agents.")
        return None


def _build_query_service(config: AgentConfig) -> Any | None:
    try:
        from smak.factory import create_query_service
        return create_query_service(config.smak.workspace_config)
    except Exception:
        logger.info("SMAK QueryService not available — HIEROPHANT GREEN will use memory only.")
        return None


def _build_subagent_spawner(config: AgentConfig) -> Any | None:
    if not config.subagent.enabled:
        return None
    try:
        from jojo.services.subagent import SubAgentSpawner
        return SubAgentSpawner(config.subagent)
    except Exception:
        logger.info("SubAgent spawner not available — SHEER HEART ATTACK disabled.")
        return None


def _build_heartbeat(config: AgentConfig, llm: Any, email: EmailNotifier) -> HeartbeatService:
    async def check_llm() -> bool:
        try:
            llm.invoke([{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False

    return HeartbeatService(
        config=config.heartbeat,
        checks={"llm_health": check_llm},
        on_failure=lambda status: email.notify(
            "heartbeat_failure", "Heartbeat failure",
            f"Failed checks: {status.failures}",
        ),
    )


def _make_harvest_worker(llm: Any, tool_registry: ToolRegistry, memory: MemoryStore) -> Any:
    """Simple worker function for HARVEST's parallel sub-tasks."""
    async def worker(task: str, ctx: dict) -> str:
        from jojo.jojo_stands.star_platinum import StarPlatinum
        mini = StarPlatinum(llm=llm, tool_registry=tool_registry, memory=memory, config=AgentConfig())
        result = await mini.run(task, {"max_steps": 5})
        return result["answer"]
    return worker
