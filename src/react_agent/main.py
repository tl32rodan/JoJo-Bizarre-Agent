"""Entry point for the local ReAct agent."""

from __future__ import annotations

import asyncio
import logging
import signal
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

logger = logging.getLogger(__name__)


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
    # Try SMAK / faiss-storage-lib first; fall back to lightweight in-memory stubs.
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

    # --- Permissions ---
    permissions = PermissionManager(config.permissions)

    # --- Tool registry ---
    tool_registry = ToolRegistry()
    if mcp_client.server_names:
        await tool_registry.register_mcp_tools(mcp_client)

    # Load SKILL.md from known paths.
    # TODO: make configurable.
    skills = load_skills_from_paths([Path(".")])
    tool_registry.enhance_with_skills(skills)

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

    # --- Agent loop ---
    agent = AgentLoop(
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        permissions=permissions,
        config=config,
    )

    print("Local ReAct Agent ready. Type 'exit' or 'quit' to leave.")
    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            result = await agent.run(user_input)
            print(f"\n{result.answer}\n")
            if result.tool_calls:
                print(f"  [Used {len(result.tool_calls)} tool(s) in {result.steps} step(s)]")
    finally:
        heartbeat.stop()
        await mcp_client.disconnect_all()
        memory.persist()
        print("Goodbye!")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config_path = sys.argv[1] if len(sys.argv) > 1 else "agent.yaml"
    asyncio.run(async_main(config_path))


if __name__ == "__main__":
    main()
