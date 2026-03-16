"""Tests for react_agent.services.subagent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from react_agent.config import SubAgentConfig
from react_agent.services.subagent import (
    DepthLimitError,
    SubAgentHandle,
    SubAgentSpawner,
    SubAgentStatus,
)


class TestSubAgentSpawner:
    def _make_config(self, tmp_path, **overrides) -> SubAgentConfig:
        defaults = dict(
            enabled=True,
            mode="tmux",
            max_concurrent=3,
            timeout_seconds=60,
            work_dir=str(tmp_path / "tasks"),
        )
        defaults.update(overrides)
        return SubAgentConfig(**defaults)

    @patch("react_agent.services.subagent.subprocess.run")
    def test_spawn_creates_task_dir(self, mock_run, tmp_path):
        spawner = SubAgentSpawner(self._make_config(tmp_path))
        handle = spawner.spawn("do something")
        task_dir = handle.work_dir
        assert task_dir.exists()
        input_file = task_dir / "input.json"
        assert input_file.exists()
        data = json.loads(input_file.read_text())
        assert data["task"] == "do something"

    @patch("react_agent.services.subagent.subprocess.run")
    def test_tmux_command(self, mock_run, tmp_path):
        spawner = SubAgentSpawner(self._make_config(tmp_path, mode="tmux"))
        spawner.spawn("task")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "tmux"
        assert cmd[1] == "new-window"

    @patch("react_agent.services.subagent.subprocess.run")
    def test_depth_env_var_set(self, mock_run, tmp_path):
        spawner = SubAgentSpawner(self._make_config(tmp_path))
        spawner.spawn("task")
        env = mock_run.call_args[1].get("env", {})
        assert env.get("AGENT_DEPTH") == "1"

    def test_depth_limit_blocks_nested(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_DEPTH", "1")
        with pytest.raises(DepthLimitError):
            SubAgentSpawner(self._make_config(tmp_path))

    def test_poll_pending(self, tmp_path):
        task_dir = tmp_path / "tasks" / "abc"
        task_dir.mkdir(parents=True)
        handle = SubAgentHandle(task_id="abc", work_dir=task_dir)
        spawner = SubAgentSpawner.__new__(SubAgentSpawner)
        spawner._config = self._make_config(tmp_path)
        spawner._active = []
        status = spawner.poll(handle)
        assert status == SubAgentStatus.PENDING

    def test_poll_completed(self, tmp_path):
        task_dir = tmp_path / "tasks" / "abc"
        task_dir.mkdir(parents=True)
        (task_dir / "output.json").write_text('{"result": "ok"}')
        handle = SubAgentHandle(task_id="abc", work_dir=task_dir)
        spawner = SubAgentSpawner.__new__(SubAgentSpawner)
        spawner._config = self._make_config(tmp_path)
        spawner._active = []
        status = spawner.poll(handle)
        assert status == SubAgentStatus.COMPLETED

    def test_collect_result(self, tmp_path):
        task_dir = tmp_path / "tasks" / "abc"
        task_dir.mkdir(parents=True)
        (task_dir / "output.json").write_text('{"result": "done"}')
        handle = SubAgentHandle(task_id="abc", work_dir=task_dir)
        spawner = SubAgentSpawner.__new__(SubAgentSpawner)
        spawner._config = self._make_config(tmp_path)
        spawner._active = [handle]
        result = spawner.collect(handle)
        assert result.status == SubAgentStatus.COMPLETED
        assert result.output == {"result": "done"}

    @patch("react_agent.services.subagent.subprocess.run")
    def test_max_concurrent_limit(self, mock_run, tmp_path):
        spawner = SubAgentSpawner(self._make_config(tmp_path, max_concurrent=1))
        spawner.spawn("task1")
        with pytest.raises(RuntimeError, match="Max concurrent"):
            spawner.spawn("task2")
