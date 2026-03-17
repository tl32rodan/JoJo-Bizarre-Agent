"""Stand subprocess runner — entry point for subagent-spawned Stands.

When STAR PLATINUM summons HIEROPHANT GREEN or SHEER HEART ATTACK via
GOLD EXPERIENCE, the SubAgentSpawner launches this module as a separate
process. It reads input.json, runs the Stand's pipeline, and writes
output.json or error.txt.

Usage:
    python -m jojo.stands.runner <task_id> --work-dir <path>
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _setup_stand(stand_type: str, task: str, context: dict) -> object:
    """Instantiate the correct Stand with its dependencies."""
    if stand_type == "hierophant_green":
        from smak.utils.embedding import InternalNomicEmbedding
        from faiss_storage_lib.engine.faiss_engine import FaissEngine
        from jojo.memory.store import MemoryStore

        embedder = InternalNomicEmbedding()
        dimension = embedder.get_embedding_dimension()
        storage_dir = context.get("storage_dir", "./agent_data/memory")
        vs = FaissEngine(storage_dir, dimension=dimension)
        memory = MemoryStore(vector_store=vs, embedder=embedder)

        query_service = None
        try:
            from smak.factory import create_query_service
            workspace_config = context.get("workspace_config", "./workspace_config.yaml")
            query_service = create_query_service(workspace_config)
        except Exception:
            logger.info("SMAK QueryService not available in subagent")

        from jojo.stands.hierophant_green import HierophantGreen
        return HierophantGreen(
            memory_store=memory,
            query_service=query_service,
            top_k=context.get("top_k", 10),
        )

    if stand_type == "sheer_heart_attack":
        # SHEER HEART ATTACK in subagent mode runs its inner task directly
        # (it doesn't re-spawn; the spawning already happened)
        from jojo.stands.hierophant_green import HierophantGreen
        from smak.utils.embedding import InternalNomicEmbedding
        from faiss_storage_lib.engine.faiss_engine import FaissEngine
        from jojo.memory.store import MemoryStore

        embedder = InternalNomicEmbedding()
        dimension = embedder.get_embedding_dimension()
        storage_dir = context.get("storage_dir", "./agent_data/memory")
        vs = FaissEngine(storage_dir, dimension=dimension)
        memory = MemoryStore(vector_store=vs, embedder=embedder)

        return HierophantGreen(memory_store=memory, top_k=context.get("top_k", 10))

    raise ValueError(f"Unknown stand type for subagent runner: {stand_type}")


async def run_stand(work_dir: Path) -> None:
    input_file = work_dir / "input.json"
    output_file = work_dir / "output.json"
    error_file = work_dir / "error.txt"

    # Write PID for polling
    (work_dir / "pid").write_text(str(os.getpid()))

    try:
        data = json.loads(input_file.read_text(encoding="utf-8"))
        task = data["task"]
        context = data.get("context", {})
        stand_type = context.get("stand_type", "hierophant_green")

        stand = _setup_stand(stand_type, task, context)
        result = await stand.execute(task, context=context)

        output_file.write_text(
            json.dumps({
                "status": result.status.value,
                "output": result.output,
                "error": result.error,
                "metadata": result.metadata,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    except Exception as exc:
        logger.exception("Stand runner failed")
        error_file.write_text(str(exc), encoding="utf-8")

    finally:
        pid_file = work_dir / "pid"
        if pid_file.exists():
            pid_file.unlink()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m jojo.stands.runner <task_id> --work-dir <path>")
        sys.exit(1)

    work_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--work-dir" and i + 1 < len(sys.argv):
            work_dir = Path(sys.argv[i + 1])
            break

    if work_dir is None:
        print("--work-dir is required")
        sys.exit(1)

    asyncio.run(run_stand(work_dir))


if __name__ == "__main__":
    main()
