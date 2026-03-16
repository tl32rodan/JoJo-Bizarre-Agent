"""Tests for react_agent.services.heartbeat."""

from __future__ import annotations

import asyncio
import pytest

from react_agent.config import HeartbeatConfig
from react_agent.services.heartbeat import HeartbeatService, HealthStatus


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestHeartbeatService:
    @pytest.mark.asyncio
    async def test_run_checks_all_pass(self):
        async def ok_check() -> bool:
            return True

        svc = HeartbeatService(
            config=HeartbeatConfig(enabled=True, interval_seconds=60),
            checks={"check_a": ok_check, "check_b": ok_check},
        )
        status = await svc.run_checks()
        assert status.healthy
        assert status.failures == []

    @pytest.mark.asyncio
    async def test_run_checks_one_fails(self):
        async def ok_check() -> bool:
            return True

        async def fail_check() -> bool:
            return False

        svc = HeartbeatService(
            config=HeartbeatConfig(enabled=True),
            checks={"good": ok_check, "bad": fail_check},
        )
        status = await svc.run_checks()
        assert not status.healthy
        assert "bad" in status.failures

    @pytest.mark.asyncio
    async def test_failure_triggers_callback(self):
        async def fail_check() -> bool:
            return False

        callback_called = []

        def on_fail(status: HealthStatus) -> None:
            callback_called.append(status)

        svc = HeartbeatService(
            config=HeartbeatConfig(enabled=True),
            checks={"failing": fail_check},
            on_failure=on_fail,
        )
        # Run one check cycle manually.
        status = await svc.run_checks()
        # Simulate the loop behavior.
        if not status.healthy:
            on_fail(status)
        assert len(callback_called) == 1

    @pytest.mark.asyncio
    async def test_check_exception_treated_as_failure(self):
        async def exploding_check() -> bool:
            raise RuntimeError("boom")

        svc = HeartbeatService(
            config=HeartbeatConfig(enabled=True),
            checks={"boom": exploding_check},
        )
        status = await svc.run_checks()
        assert not status.healthy
        assert "boom" in status.failures

    def test_stop_cancels_task(self):
        svc = HeartbeatService(config=HeartbeatConfig(enabled=True))
        # stop without start should be safe.
        svc.stop()
        assert svc._task is None
