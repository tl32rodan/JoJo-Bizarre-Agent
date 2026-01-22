from dataclasses import dataclass
from typing import Dict, List

from agent_core import ReactResult, run_react_agent


@dataclass
class _Message:
    content: str


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Response:
    choices: List[_Choice]


class _ChatCompletions:
    def __init__(self, responder):
        self._responder = responder

    def create(self, *, model, messages, temperature, stop=None):
        return _Response(choices=[_Choice(message=_Message(content=self._responder(messages)))])


class FakeClient:
    def __init__(self, responder):
        self.chat = type("Chat", (), {"completions": _ChatCompletions(responder)})()


def demo_react() -> ReactResult:
    def responder(messages: List[Dict[str, str]]) -> str:
        last = messages[-1]["content"]
        if last.startswith("Question:"):
            return (
                "Thought: I should look up the technical docs.\n"
                "Action: search_docs\n"
                "Action Input: release checklist"
            )
        return (
            "Thought: I now know the final answer.\n"
            "Final Answer: The release checklist is complete per the docs."
        )

    client = FakeClient(responder)
    return run_react_agent(
        "Check if release checklist is complete",
        client=client,
        model="qwen-235b",
    )


if __name__ == "__main__":
    result = demo_react()
    print("Demo result:")
    print(result.answer)
