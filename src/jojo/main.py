"""Entry point — thin launcher that wires bootstrap + REPL."""

from __future__ import annotations

import asyncio
import logging
import sys

from jojo.bootstrap import build_app, teardown_app
from jojo.repl import run_repl


async def async_main(config_path: str = "agent.yaml") -> None:
    ctx = await build_app(config_path)
    try:
        await run_repl(ctx)
    finally:
        await teardown_app(ctx)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config_path = sys.argv[1] if len(sys.argv) > 1 else "agent.yaml"
    asyncio.run(async_main(config_path))


if __name__ == "__main__":
    main()
