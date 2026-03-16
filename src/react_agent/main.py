"""Entry point for the local ReAct agent — STAR PLATINUM edition."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from react_agent.config import load_agent_config
from react_agent.core.agent_loop import AgentLoop
from react_agent.memory.store import MemoryStore
from react_agent.mcp.client import MCPClientManager
from react_agent.mcp.skill_loader import load_skills_from_paths
from react_agent.mcp.tool_registry import ToolRegistry
from react_agent.services.email_notifier import EmailNotifier
from react_agent.services.heartbeat import HeartbeatService
from react_agent.services.permission import PermissionManager
from react_agent.stands.arrow import StandArrow

logger = logging.getLogger(__name__)

_BANNER = r"""
  ____  _____  _    ____    ____  _        _  _____ ___ _   _ _   _ __  __
 / ___||_   _|/ \  |  _ \  |  _ \| |      / \|_   _|_ _| \ | | | | |  \/  |
 \___ \  | | / _ \ | |_) | | |_) | |     / _ \ | |  | ||  \| | | | | |\/| |
  ___) | | |/ ___ \|  _ <  |  __/| |___ / ___ \| |  | || |\  | |_| | |  | |
 |____/  |_/_/   \_\_| \_\ |_|   |_____/_/   \_\_| |___|_| \_|\___/|_|  |_|

    「オラオラオラ！」 — Stand Arrow Ready.
"""


async def async_main(config_path: str = "agent.yaml") -> None:
    config = load_agent_config(config_path)

    # --- LLM (lazy import to avoid hard dep on langchain at import time) ---
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            base_url=config.llm.base_url,
            model=config.llm.model,
            api_key=config.llm.api_key,
        )

        # Optional reasoning model for THE WORLD.
        reasoning_model = config.llm.models.get("reasoning")
        reasoning_llm = None
        if reasoning_model and reasoning_model != config.llm.model:
            reasoning_llm = ChatOpenAI(
                base_url=config.llm.base_url,
                model=reasoning_model,
                api_key=config.llm.api_key,
            )
    except ImportError:
        logger.error("langchain-openai not installed. Cannot start agent.")
        return

    # --- MCP client (external tools) ---
    mcp_client = MCPClientManager()
    if config.mcp_servers:
        try:
            await mcp_client.connect_all(config.mcp_servers)
        except Exception:
            logger.exception("Failed to connect to MCP servers")

    # --- Memory ---
    try:
        from smak.utils.embedding import InternalNomicEmbedding
        embedder = InternalNomicEmbedding()
    except ImportError:
        logger.warning("SMAK not installed, using fallback embedding (memory will be limited).")
        from react_agent.memory.fallback import FallbackEmbedding
        embedder = FallbackEmbedding()  # type: ignore[assignment]

    try:
        from faiss_storage_lib.engine.faiss_engine import FaissEngine
        vs = FaissEngine(config.memory.storage_dir, dimension=768)
    except ImportError:
        logger.warning("faiss-storage-lib not installed, using in-memory vector store.")
        from react_agent.memory.fallback import FallbackVectorStore
        vs = FallbackVectorStore()  # type: ignore[assignment]

    memory = MemoryStore(vector_store=vs, embedder=embedder)

    # --- SMAK QueryService (for HIEROPHANT GREEN) ---
    query_service = None
    try:
        from smak.factory import create_query_service
        query_service = create_query_service(config.smak.workspace_config)
    except Exception:
        logger.info("SMAK QueryService not available — HIEROPHANT GREEN will use memory only.")

    # --- Permissions ---
    permissions = PermissionManager(config.permissions)

    # --- Tool registry ---
    tool_registry = ToolRegistry()
    if mcp_client.server_names:
        await tool_registry.register_mcp_tools(mcp_client)

    skills = load_skills_from_paths([Path(".")])
    tool_registry.enhance_with_skills(skills)

    # --- SubAgent spawner (for SHEER HEART ATTACK) ---
    subagent_spawner = None
    try:
        from react_agent.services.subagent import SubAgentSpawner
        subagent_spawner = SubAgentSpawner(config.subagent)
    except Exception:
        logger.info("SubAgent spawner not available — SHEER HEART ATTACK disabled.")

    # --- Stand Arrow (スタンドの矢) ---
    async def harvest_worker(task: str, ctx: dict) -> str:
        """Default HARVEST worker: run a mini agent loop."""
        mini_agent = AgentLoop(llm=llm, tool_registry=tool_registry, memory=memory)
        result = await mini_agent.run(task, max_steps=5)
        return result.answer

    stand_arrow = StandArrow(
        llm=llm,
        reasoning_llm=reasoning_llm,
        tool_registry=tool_registry,
        memory_store=memory,
        query_service=query_service,
        subagent_spawner=subagent_spawner,
        harvest_worker=harvest_worker,
        config=config,
    )

    # --- Email ---
    email = EmailNotifier(config.email)

    # --- Heartbeat ---
    async def check_llm() -> bool:
        try:
            llm.invoke([{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False

    heartbeat = HeartbeatService(
        config=config.heartbeat,
        checks={"llm_health": check_llm},
        on_failure=lambda status: email.notify(
            "heartbeat_failure",
            "Heartbeat failure",
            f"Failed checks: {status.failures}",
        ),
    )
    heartbeat.start()

    # --- STAR PLATINUM agent loop ---
    agent = AgentLoop(
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        permissions=permissions,
        config=config,
        stand_arrow=stand_arrow,
    )

    print(_BANNER)
    print("STAR PLATINUM ready. Type 'exit' or 'quit' to leave.")
    print("Stand Arrow can summon: THE WORLD, HIEROPHANT GREEN, HARVEST, SHEER HEART ATTACK\n")

    try:
        while True:
            try:
                user_input = input("STAR PLATINUM> ").strip()
            except EOFError:
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            result = await agent.run(user_input)
            print(f"\n{result.answer}\n")
            details = []
            if result.tool_calls:
                details.append(f"{len(result.tool_calls)} tool(s)")
            if result.stands_used:
                details.append(f"Stands: {', '.join(result.stands_used)}")
            details.append(f"{result.steps} step(s)")
            print(f"  [{' | '.join(details)}]")
    finally:
        heartbeat.stop()
        await mcp_client.disconnect_all()
        memory.persist()
        stand_arrow.retire_all()
        print("やれやれだぜ… Goodbye!")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config_path = sys.argv[1] if len(sys.argv) > 1 else "agent.yaml"
    asyncio.run(async_main(config_path))


if __name__ == "__main__":
    main()
