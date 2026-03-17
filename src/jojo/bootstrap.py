"""Dependency injection and service wiring for JoJo.

Single Responsibility: construct the complete dependency graph
from configuration.  No business logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jojo.config import AgentConfig, load_agent_config
from jojo.core.jojo import JoJo
from jojo.memory.store import MemoryStore
from jojo.mcp.client import MCPClientManager
from jojo.mcp.skill_loader import load_skills_from_paths
from jojo.mcp.tool_registry import ToolRegistry
from jojo.services.email_notifier import EmailNotifier
from jojo.services.heartbeat import HeartbeatService
from jojo.services.permission import PermissionManager
from jojo.stands.base import StandType

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Holds all wired-up services."""
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

    # Build JoJo orchestrator
    jojo = JoJo(memory=memory, config=config)

    # Register Stands
    _register_stands(
        jojo, config, llm, reasoning_llm, tool_registry, memory, permissions,
    )

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
    """Graceful shutdown."""
    ctx.heartbeat.stop()
    await ctx.mcp_client.disconnect_all()
    ctx.memory.persist()


# ---------------------------------------------------------------------------
# Stand registration
# ---------------------------------------------------------------------------

def _register_stands(
    jojo: JoJo,
    config: AgentConfig,
    llm: Any,
    reasoning_llm: Any | None,
    tool_registry: ToolRegistry,
    memory: MemoryStore,
    permissions: PermissionManager,
) -> None:
    """Create and register all Stands with JoJo."""
    from jojo.stands.star_platinum import StarPlatinum
    from jojo.stands.gold_experience import GoldExperience
    from jojo.stands.the_world import TheWorld
    from jojo.stands.hierophant_green import HierophantGreen
    from jojo.stands.harvest import Harvest
    from jojo.stands.sheer_heart_attack import SheerHeartAttack

    # Star Platinum — default ReAct + Time Stop
    jojo.register_stand(StarPlatinum(
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        reasoning_llm=reasoning_llm,
        permissions=permissions,
    ))

    # Gold Experience — sub-agent spawner
    stand_factory = _build_stand_factory(
        config, llm, reasoning_llm, tool_registry, memory,
    )
    jojo.register_stand(GoldExperience(
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        stand_factory=stand_factory,
    ))

    # The World — deep reasoning (also spawnable by Gold Experience)
    jojo.register_stand(TheWorld(
        llm=reasoning_llm or llm,
        tool_registry=tool_registry,
    ))

    # Hierophant Green — RAG
    query_service = _build_query_service(config)
    jojo.register_stand(HierophantGreen(
        memory_store=memory,
        query_service=query_service,
    ))

    # Harvest — parallel execution
    harvest_worker = _make_harvest_worker(llm, tool_registry, memory)
    max_c = config.subagent.max_concurrent if config.subagent else 10
    jojo.register_stand(Harvest(worker=harvest_worker, max_concurrency=max_c))

    # Sheer Heart Attack — background tasks
    spawner = _build_subagent_spawner(config)
    timeout = config.subagent.timeout_seconds if config.subagent else 600
    jojo.register_stand(SheerHeartAttack(spawner=spawner, timeout=timeout))


def _build_stand_factory(
    config: AgentConfig,
    llm: Any,
    reasoning_llm: Any | None,
    tool_registry: ToolRegistry,
    memory: MemoryStore,
) -> Any:
    """Factory function for Gold Experience to spawn sub-agent Stands."""
    from jojo.stands.the_world import TheWorld
    from jojo.stands.hierophant_green import HierophantGreen
    from jojo.stands.harvest import Harvest
    from jojo.stands.sheer_heart_attack import SheerHeartAttack

    query_service = _build_query_service(config)
    spawner = _build_subagent_spawner(config)
    harvest_worker = _make_harvest_worker(llm, tool_registry, memory)

    def factory(stand_type: StandType) -> Any:
        if stand_type == StandType.THE_WORLD:
            return TheWorld(llm=reasoning_llm or llm, tool_registry=tool_registry)
        elif stand_type == StandType.HIEROPHANT_GREEN:
            return HierophantGreen(memory_store=memory, query_service=query_service)
        elif stand_type == StandType.HARVEST:
            max_c = config.subagent.max_concurrent if config.subagent else 10
            return Harvest(worker=harvest_worker, max_concurrency=max_c)
        elif stand_type == StandType.SHEER_HEART_ATTACK:
            timeout = config.subagent.timeout_seconds if config.subagent else 600
            return SheerHeartAttack(spawner=spawner, timeout=timeout)
        else:
            raise ValueError(f"Cannot spawn: {stand_type}")

    return factory


# ---------------------------------------------------------------------------
# Private builders
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


def _build_query_service(config: AgentConfig) -> Any | None:
    try:
        from smak.factory import create_query_service
        return create_query_service(config.smak.workspace_config)
    except Exception:
        logger.info("SMAK QueryService not available — HIEROPHANT GREEN will use memory only.")
        return None


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
        from jojo.stands.star_platinum import StarPlatinum
        mini = StarPlatinum(llm=llm, tool_registry=tool_registry, memory=memory, max_steps=5)
        result = await mini.execute(task, {"max_steps": 5})
        return str(result.output) if result.output else (result.error or "")
    return worker
