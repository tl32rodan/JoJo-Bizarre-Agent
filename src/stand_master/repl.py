"""Interactive REPL for STAR PLATINUM.

Single Responsibility: handles user I/O only.
All service construction is done by bootstrap.py.
"""

from __future__ import annotations

from stand_master.bootstrap import AppContext

_BANNER = r"""
  ____  _____  _    ____    ____  _        _  _____ ___ _   _ _   _ __  __
 / ___||_   _|/ \  |  _ \  |  _ \| |      / \|_   _|_ _| \ | | | | |  \/  |
 \___ \  | | / _ \ | |_) | | |_) | |     / _ \ | |  | ||  \| | | | | |\/| |
  ___) | | |/ ___ \|  _ <  |  __/| |___ / ___ \| |  | || |\  | |_| | |  | |
 |____/  |_/_/   \_\_| \_\ |_|   |_____/_/   \_\_| |___|_| \_|\___/|_|  |_|

    「オラオラオラ！」 — Stand Arrow Ready.
    Stands: THE WORLD | HIEROPHANT GREEN | HARVEST | SHEER HEART ATTACK | CRAZY DIAMOND
"""


async def run_repl(ctx: AppContext) -> None:
    """Run the interactive STAR PLATINUM REPL."""
    print(_BANNER)
    print("Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            user_input = input("STAR PLATINUM> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        result = await ctx.agent.run(user_input)
        print(f"\n{result.answer}\n")

        details = []
        if result.tool_calls:
            details.append(f"{len(result.tool_calls)} tool(s)")
        if result.stands_used:
            details.append(f"Stands: {', '.join(result.stands_used)}")
        details.append(f"{result.steps} step(s)")
        print(f"  [{' | '.join(details)}]")

    print("やれやれだぜ… Goodbye!")
