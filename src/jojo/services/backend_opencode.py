"""OpenCodeBackend — sub-agent execution via OpenCode server.

Connects to a running ``opencode serve`` instance using the
``opencode-ai`` Python SDK.  Falls back gracefully when OpenCode
is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from jojo.services.backend import SubAgentBackend, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class OpenCodeBackend:
    """SubAgentBackend backed by an OpenCode server (``opencode serve``)."""

    def __init__(
        self,
        base_url: str = "http://localhost:4096",
        password: str = "",
        default_agent: str = "build",
        timeout_seconds: int = 300,
    ) -> None:
        self._base_url = base_url
        self._password = password
        self._default_agent = default_agent
        self._timeout = timeout_seconds
        self._client: Any | None = None
        self._sessions: dict[str, str] = {}  # handle_id → session_id

    # ------------------------------------------------------------------
    # Lazy client initialisation
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Return (and cache) an ``AsyncOpencode`` client instance."""
        if self._client is not None:
            return self._client

        try:
            from opencode_ai import AsyncOpencode
        except ImportError:
            raise RuntimeError(
                "opencode-ai SDK is not installed.  "
                "Install with: pip install 'opencode-ai>=0.1.0a30'"
            )

        kwargs: dict[str, Any] = {"base_url": self._base_url}
        if self._password:
            kwargs["username"] = "opencode"
            kwargs["password"] = self._password

        self._client = AsyncOpencode(**kwargs)
        return self._client

    # ------------------------------------------------------------------
    # SubAgentBackend interface
    # ------------------------------------------------------------------

    async def spawn(
        self,
        task: str,
        *,
        agent: str = "default",
        tools: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        client = self._get_client()
        agent_name = agent if agent != "default" else self._default_agent

        session = await client.session.create()
        session_id = session.id

        # Send the task as a chat message (non-blocking kickoff).
        # The chat method returns an AssistantMessage once the agent
        # finishes processing the prompt.
        asyncio.create_task(self._run_chat(session_id, task, agent_name))

        self._sessions[session_id] = session_id
        logger.info("OpenCodeBackend: spawned session %s (agent=%s)", session_id, agent_name)
        return session_id

    async def poll(self, handle_id: str) -> TaskStatus:
        if handle_id not in self._sessions:
            return TaskStatus.FAILED

        client = self._get_client()
        try:
            messages = await client.session.messages(handle_id)
            # If we have assistant messages, the task finished.
            if messages and hasattr(messages, "__iter__"):
                for msg in messages:
                    if getattr(msg, "role", None) == "assistant":
                        return TaskStatus.COMPLETED
            return TaskStatus.RUNNING
        except Exception:
            return TaskStatus.RUNNING

    async def collect(self, handle_id: str, timeout: float = 300) -> TaskResult:
        elapsed = 0.0
        interval = 3.0
        while elapsed < timeout:
            status = await self.poll(handle_id)
            if status == TaskStatus.COMPLETED:
                return await self._extract_result(handle_id)
            if status == TaskStatus.FAILED:
                return TaskResult(handle_id=handle_id, status=TaskStatus.FAILED, error="Session failed")
            await asyncio.sleep(interval)
            elapsed += interval

        return TaskResult(handle_id=handle_id, status=TaskStatus.FAILED, error=f"Timeout after {timeout}s")

    async def abort(self, handle_id: str) -> None:
        client = self._get_client()
        try:
            await client.session.abort(handle_id)
            logger.info("OpenCodeBackend: aborted session %s", handle_id)
        except Exception as exc:
            logger.warning("OpenCodeBackend: abort failed for %s: %s", handle_id, exc)

    async def cleanup(self, handle_id: str) -> None:
        client = self._get_client()
        try:
            await client.session.delete(handle_id)
        except Exception:
            pass
        self._sessions.pop(handle_id, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_chat(self, session_id: str, task: str, agent: str) -> None:
        """Send a chat message in the background."""
        client = self._get_client()
        try:
            await client.session.chat(session_id, parts=[{"type": "text", "text": task}])
        except Exception as exc:
            logger.error("OpenCodeBackend: chat failed for session %s: %s", session_id, exc)

    async def _extract_result(self, handle_id: str) -> TaskResult:
        """Pull the last assistant message as the task output."""
        client = self._get_client()
        try:
            messages = await client.session.messages(handle_id)
            # Walk backwards to find the last assistant message.
            last_text = ""
            if messages and hasattr(messages, "__iter__"):
                for msg in reversed(list(messages)):
                    if getattr(msg, "role", None) == "assistant":
                        # Extract text parts.
                        parts = getattr(msg, "parts", [])
                        texts = []
                        for p in parts:
                            if getattr(p, "type", None) == "text":
                                texts.append(getattr(p, "text", str(p)))
                        last_text = "\n".join(texts) if texts else str(msg)
                        break

            return TaskResult(handle_id=handle_id, status=TaskStatus.COMPLETED, output=last_text)
        except Exception as exc:
            return TaskResult(handle_id=handle_id, status=TaskStatus.FAILED, error=str(exc))
