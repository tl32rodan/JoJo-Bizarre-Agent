"""SubAgent spawner via tmux or cron (1-level depth limit)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from jojo.config import SubAgentConfig

logger = logging.getLogger(__name__)

_DEPTH_ENV_VAR = "AGENT_DEPTH"


class DepthLimitError(RuntimeError):
    pass


class SubAgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class SubAgentHandle:
    task_id: str
    work_dir: Path


@dataclass(frozen=True)
class SubAgentResult:
    task_id: str
    status: SubAgentStatus
    output: Any = None
    error: str | None = None


class SubAgentSpawner:
    def __init__(self, config: SubAgentConfig) -> None:
        self._config = config
        self._active: list[SubAgentHandle] = []
        self._check_depth_limit()

    def _check_depth_limit(self) -> None:
        depth = int(os.environ.get(_DEPTH_ENV_VAR, "0"))
        if depth >= 1:
            raise DepthLimitError(f"SubAgent spawning disabled: {_DEPTH_ENV_VAR}={depth}")

    @property
    def active_count(self) -> int:
        return len(self._active)

    def spawn(self, task: str, context: dict[str, Any] | None = None) -> SubAgentHandle:
        if not self._config.enabled:
            raise RuntimeError("SubAgent spawning is disabled.")
        if self.active_count >= self._config.max_concurrent:
            raise RuntimeError(f"Max concurrent subagents ({self._config.max_concurrent}) reached.")

        task_id = uuid.uuid4().hex[:12]
        task_dir = Path(self._config.work_dir) / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        input_data = {"task": task, "context": context or {}}
        (task_dir / "input.json").write_text(
            json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8",
        )

        handle = SubAgentHandle(task_id=task_id, work_dir=task_dir)

        if self._config.mode == "tmux":
            self._spawn_tmux(handle)
        else:
            self._spawn_cron(handle)

        self._active.append(handle)
        return handle

    def poll(self, handle: SubAgentHandle) -> SubAgentStatus:
        if (handle.work_dir / "output.json").exists():
            return SubAgentStatus.COMPLETED
        if (handle.work_dir / "error.txt").exists():
            return SubAgentStatus.FAILED
        if (handle.work_dir / "pid").exists():
            return SubAgentStatus.RUNNING
        return SubAgentStatus.PENDING

    def collect(self, handle: SubAgentHandle) -> SubAgentResult:
        output_file = handle.work_dir / "output.json"
        error_file = handle.work_dir / "error.txt"

        if output_file.exists():
            data = json.loads(output_file.read_text(encoding="utf-8"))
            self._remove_active(handle)
            return SubAgentResult(task_id=handle.task_id, status=SubAgentStatus.COMPLETED, output=data)

        if error_file.exists():
            error_text = error_file.read_text(encoding="utf-8")
            self._remove_active(handle)
            return SubAgentResult(task_id=handle.task_id, status=SubAgentStatus.FAILED, error=error_text)

        return SubAgentResult(task_id=handle.task_id, status=self.poll(handle))

    def _remove_active(self, handle: SubAgentHandle) -> None:
        self._active = [h for h in self._active if h.task_id != handle.task_id]

    def _spawn_tmux(self, handle: SubAgentHandle) -> None:
        env = {**os.environ, _DEPTH_ENV_VAR: "1"}
        cmd = f"python -m jojo.stands.runner {handle.task_id} --work-dir {handle.work_dir}"
        subprocess.run(
            ["tmux", "new-window", "-d", cmd],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )

    def _spawn_cron(self, handle: SubAgentHandle) -> None:
        env = {**os.environ, _DEPTH_ENV_VAR: "1"}
        cmd = f"python -m jojo.stands.runner {handle.task_id} --work-dir {handle.work_dir}"
        subprocess.run(
            ["bash", "-c", f'echo "{cmd}" | at now'],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
