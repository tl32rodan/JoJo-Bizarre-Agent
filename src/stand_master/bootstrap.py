"""Dependency injection and service wiring for STAR PLATINUM.

Single Responsibility: This module's only job is to construct the
complete dependency graph from configuration.  No business logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stand_master.config import AgentConfig, load_agent_config
from stand_master.core.agent_loop import AgentLoop
from stand_master.memory.store import MemoryStore
from stand_master.mcp.client import MCPClientManager
from stand_master.mcp.skill_loader import load_skills_from_paths
from stand_master.mcp.tool_registry import ToolRegistry
from stand_master.services.email_notifier import EmailNotifier
from stand_master.services.heartbeat import HeartbeatService
from stand_master.services.permission import PermissionManager
from stand_master.stands.arrow import StandArrow

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Holds all wired-up services.  Passed to the REPL for runtime use."""
    config: AgentConfig
    agent: AgentLoop
    memory: MemoryStore
    mcp_client: MCPClientManager
    heartbeat: HeartbeatService
    stand_arrow: StandArrow


async def build_app(config_path: str = "agent.yaml") -> AppContext:
    """Wire all dependencies and return a ready-to-use AppContext."""
    config = load_agent_config(config_path)

    llm, reasoning_llm = _build_llms(config)
    mcp_client = await _build_mcp_client(config)
    embedder = _build_embedder(config)
    memory = _build_memory(config, embedder)
    query_service = _build_query_service(config)
    permissions = PermissionManager(config.permissions)
    tool_registry = await _build_tool_registry(mcp_client)
    subagent_spawner = _build_subagent_spawner(config)
    email = EmailNotifier(config.email)

    stand_arrow = StandArrow(
        llm=llm,
        reasoning_llm=reasoning_llm,
        tool_registry=tool_registry,
        memory_store=memory,
        query_service=query_service,
        subagent_spawner=subagent_spawner,
        harvest_worker=_make_harvest_worker(llm, tool_registry, memory),
        config=config,
    )

    heartbeat = _build_heartbeat(config, llm, email)
    heartbeat.start()

    agent = AgentLoop(
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        permissions=permissions,
        config=config,
        stand_arrow=stand_arrow,
    )

    return AppContext(
        config=config,
        agent=agent,
        memory=memory,
        mcp_client=mcp_client,
        heartbeat=heartbeat,
        stand_arrow=stand_arrow,
    )


async def teardown_app(ctx: AppContext) -> None:
    """Graceful shutdown of all services."""
    ctx.heartbeat.stop()
    await ctx.mcp_client.disconnect_all()
    ctx.memory.persist()
    ctx.stand_arrow.retire_all()


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
        from stand_master.services.subagent import SubAgentSpawner
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
    async def worker(task: str, ctx: dict) -> str:
        mini = AgentLoop.__new__(AgentLoop)
        mini._llm = llm
        mini._tools = tool_registry
        mini._memory = memory
        mini._permissions = PermissionManager(AgentConfig().permissions)
        mini._config = AgentConfig()
        mini._context = __import__("stand_master.core.context_manager", fromlist=["ContextManager"]).ContextManager()
        mini._arrow = StandArrow(llm=llm)
        result = await mini.run(task, max_steps=5)
        return result.answer
    return worker
