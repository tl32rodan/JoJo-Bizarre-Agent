"""Interactive REPL for JoJo.

Single Responsibility: handles user I/O only.
All service construction is done by bootstrap.py.
"""

from __future__ import annotations

from jojo.bootstrap import AppContext
from jojo.jojo_stands.base import JoJoStandType, JOJO_STAND_PROFILES

_BANNER = r"""
      _        _
     | | ___  | | ___
  _  | |/ _ \ | |/ _ \
 | |_| | (_) || | (_) |
  \___/ \___/_/ |\___/
            |__/

    JoJo's Bizarre Agent — Stand Master
    Personas: Star Platinum | Crazy Diamond | Gold Experience
              Stone Free | Tusk | Soft & Wet
"""


async def run_repl(ctx: AppContext) -> None:
    """Run the interactive JoJo REPL."""
    print(_BANNER)
    print("Type 'exit' or 'quit' to leave.")
    print("Type '/persona <name>' to switch Stand persona.\n")

    while True:
        try:
            persona_name = ""
            if ctx.jojo.current_persona:
                p = JOJO_STAND_PROFILES[ctx.jojo.current_persona]
                persona_name = p.name
            prompt_label = persona_name or "JoJo"
            user_input = input(f"{prompt_label}> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        # Manual persona switch command
        forced_persona = None
        if user_input.lower().startswith("/persona "):
            name = user_input[9:].strip().lower()
            for st in JoJoStandType:
                if name in st.value or name in JOJO_STAND_PROFILES[st].name.lower():
                    forced_persona = st
                    print(f"\n  Switching to {JOJO_STAND_PROFILES[st].name}（{JOJO_STAND_PROFILES[st].name_jp}）\n")
                    break
            else:
                print(f"\n  Unknown persona: '{name}'")
                print(f"  Available: {', '.join(st.value for st in JoJoStandType)}\n")
            continue

        result = await ctx.jojo.run(user_input, persona=forced_persona)
        print(f"\n{result.answer}\n")

        details = []
        if result.persona:
            details.append(result.persona)
        if result.tool_calls:
            details.append(f"{len(result.tool_calls)} tool(s)")
        if result.stands_summoned:
            details.append(f"Stands: {', '.join(result.stands_summoned)}")
        details.append(f"{result.steps} step(s)")
        print(f"  [{' | '.join(details)}]")

    print("やれやれだぜ… Goodbye!")
