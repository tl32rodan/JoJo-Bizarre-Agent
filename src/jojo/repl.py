"""Interactive REPL for JoJo.

Single Responsibility: handles user I/O only.
All service construction is done by bootstrap.py.
"""

from __future__ import annotations

from jojo.bootstrap import AppContext
from jojo.stands.base import StandType, STAND_PROFILES

_BANNER = r"""
      _        _
     | | ___  | | ___
  _  | |/ _ \ | |/ _ \
 | |_| | (_) || | (_) |
  \___/ \___/_/ |\___/
            |__/

    JoJo's Bizarre Agent — 「やれやれだぜ…」

    Stands:
      Star Platinum    — Executor  (Ora Ora Rush + The World)
      Gold Experience  — Orchestrator (Life Giver + Life Sensor)
      Hierophant Green — Researcher (Emerald Splash + 20m Barrier)
      Crazy Diamond    — Reviewer  (Restoration + Breakdown)

    Commands:
      /stand <name>      — Force a specific Stand
      /timestop <query>  — Star Platinum: The World (deep reasoning)
      /barrier <query>   — Hierophant Green: 20m Barrier (methodology)
      /review <query>    — Crazy Diamond: Restoration (code review)
"""


async def run_repl(ctx: AppContext) -> None:
    """Run the interactive JoJo REPL."""
    print(_BANNER)
    print("Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            label = "JoJo"
            if ctx.jojo.current_stand:
                label = STAND_PROFILES[ctx.jojo.current_stand].name
            user_input = input(f"{label}> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        # /stand command — force a specific Stand
        if user_input.lower().startswith("/stand "):
            name = user_input[7:].strip().lower()
            for st in StandType:
                if name in st.value or name in STAND_PROFILES[st].name.lower():
                    print(f"\n  → {STAND_PROFILES[st].name}（{STAND_PROFILES[st].name_jp}）\n")
                    break
            else:
                print(f"\n  Unknown Stand: '{name}'")
                print(f"  Available: {', '.join(st.value for st in StandType)}\n")
            continue

        # /timestop command — Star Platinum: The World
        time_stop = False
        barrier = False
        review = False
        forced_stand = None

        if user_input.lower().startswith("/timestop "):
            user_input = user_input[10:].strip()
            forced_stand = StandType.STAR_PLATINUM
            time_stop = True
            print("\n  「スタープラチナ ザ・ワールド！」\n")

        # /barrier command — Hierophant Green: 20m Barrier
        elif user_input.lower().startswith("/barrier "):
            user_input = user_input[9:].strip()
            forced_stand = StandType.HIEROPHANT_GREEN
            barrier = True
            print("\n  「結界だ… 逃がさん！」\n")

        # /review command — Crazy Diamond: Restoration
        elif user_input.lower().startswith("/review "):
            user_input = user_input[8:].strip()
            forced_stand = StandType.CRAZY_DIAMOND
            review = True
            print("\n  「直してやるよ」\n")

        result = await ctx.jojo.run(
            user_input,
            stand=forced_stand,
            time_stop=time_stop,
            barrier=barrier,
            review=review,
        )
        print(f"\n{result.answer}\n")

        details = [result.stand]
        if result.tool_calls:
            details.append(f"{len(result.tool_calls)} tool(s)")
        if result.stands_summoned:
            details.append(f"Spawned: {', '.join(result.stands_summoned)}")
        details.append(f"{result.steps} step(s)")
        print(f"  [{' | '.join(details)}]")

    print("やれやれだぜ… Goodbye!")
