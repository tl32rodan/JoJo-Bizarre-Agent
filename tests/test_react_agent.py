from app.core.react_agent import ReactAgentRunner


class FakeLLM:
    def invoke(self, prompt: str) -> str:
        return "Thought: done\nFinal Answer: OK"


def test_react_agent_runner_fallback() -> None:
    runner = ReactAgentRunner(llm=FakeLLM(), model="demo", tools={})

    result = runner.run("Hello")

    assert result.answer == "OK"
