from dataclasses import dataclass
from typing import Dict, List

from agent_core import (
    ReactResult,
    evaluate_thoughts,
    generate_thoughts,
    run_react_agent,
    run_tot_agent,
)


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


def test_run_react_agent_returns_final_answer():
    def responder(messages: List[Dict[str, str]]) -> str:
        last = messages[-1]["content"]
        if last.startswith("Question:"):
            return (
                "Thought: need docs\n"
                "Action: search_docs\n"
                "Action Input: latency limits"
            )
        return (
            "Thought: I now know the final answer.\n"
            "Final Answer: The docs show latency limits are within SLA."
        )

    client = FakeClient(responder)

    def tool(keyword: str) -> str:
        return f"info about {keyword}"

    result = run_react_agent(
        "Summarize latency limits",
        client=client,
        model="qwen-235b",
        tools={"search_docs": tool},
    )

    assert isinstance(result, ReactResult)
    assert "latency limits" in result.answer


def test_generate_thoughts_splits_lines():
    client = FakeClient(lambda messages: "Plan A\nPlan B\nPlan C")
    thoughts = generate_thoughts("state", client=client, model="qwen-235b", k=3)
    assert thoughts == ["Plan A", "Plan B", "Plan C"]


def test_evaluate_thoughts_normalizes_scores():
    responses = iter(["8", "4.5", "0"])
    client = FakeClient(lambda messages: next(responses))
    scores = evaluate_thoughts(
        ["idea1", "idea2", "idea3"],
        client=client,
        model="qwen-235b",
        goal="goal",
    )
    assert scores == [0.8, 0.45, 0.0]


def test_run_tot_agent_selects_best_path():
    def responder(messages: List[Dict[str, str]]) -> str:
        prompt = messages[-1]["content"]
        if "Generate" in prompt:
            return "option best\noption other"
        if "Candidate step" in prompt:
            return "9" if "best" in prompt else "2"
        return ""

    client = FakeClient(responder)
    result = run_tot_agent(
        "Improve onboarding",
        client=client,
        model="qwen-235b",
        depth=1,
        width=2,
    )
    assert "option best" in result
