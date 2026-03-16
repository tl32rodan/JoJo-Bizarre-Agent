"""Heartbeat service for periodic health checks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from stand_master.config import HeartbeatConfig

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def healthy(self) -> bool:
        return all(self.checks.values())

    @property
    def failures(self) -> list[str]:
        return [name for name, ok in self.checks.items() if not ok]


HealthCheck = Callable[[], Coroutine[Any, Any, bool]]


class HeartbeatService:
    def __init__(
        self,
        config: HeartbeatConfig,
        checks: dict[str, HealthCheck] | None = None,
        on_failure: Callable[[HealthStatus], None] | None = None,
    ) -> None:
        self._config = config
        self._checks = checks or {}
        self._on_failure = on_failure
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if not self._config.enabled or self._task is not None:
            return
        self._task = asyncio.ensure_future(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def run_checks(self) -> HealthStatus:
        results: dict[str, bool] = {}
        for name, check_fn in self._checks.items():
            try:
                results[name] = await check_fn()
            except Exception:
                logger.exception("Health check '%s' raised", name)
                results[name] = False
        return HealthStatus(checks=results)

    async def _loop(self) -> None:
        try:
            while True:
                status = await self.run_checks()
                if not status.healthy:
                    logger.warning("Heartbeat failures: %s", status.failures)
                    if self._on_failure:
                        try:
                            self._on_failure(status)
                        except Exception:
                            logger.exception("on_failure callback raised")
                await asyncio.sleep(self._config.interval_seconds)
        except asyncio.CancelledError:
            pass
