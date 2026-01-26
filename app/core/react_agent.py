from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Callable, Dict, Protocol

from agent_core import ReactResult, run_react_agent


class LLMClient(Protocol):
    def invoke(self, prompt: str) -> str:
        ...


@dataclass
class FallbackReactAgent:
    client: LLMClient
    model: str
    tools: Dict[str, Callable[[str], str]]

    def run(self, question: str) -> ReactResult:
        return run_react_agent(
            question,
            client=self._wrap_client(),
            model=self.model,
            tools=self.tools,
        )

    def _wrap_client(self):
        class _ChatCompletions:
            def __init__(self, outer):
                self._outer = outer

            def create(self, *, model, messages, temperature, stop=None):
                prompt = messages[-1]["content"]
                content = self._outer.client.invoke(prompt)
                return type(
                    "Response",
                    (),
                    {
                        "choices": [
                            type("Choice", (), {"message": type("Message", (), {"content": content})()})()
                        ]
                    },
                )()

        class _Chat:
            def __init__(self, outer):
                self.completions = _ChatCompletions(outer)

        return type("Client", (), {"chat": _Chat(self)})()


@dataclass
class ReactAgentRunner:
    llm: LLMClient
    model: str
    tools: Dict[str, Callable[[str], str]]

    def run(self, question: str) -> ReactResult | str:
        if self._langchain_available():
            return self._run_langchain(question)
        fallback = FallbackReactAgent(client=self.llm, model=self.model, tools=self.tools)
        return fallback.run(question)

    @staticmethod
    def _langchain_available() -> bool:
        return importlib.util.find_spec("langchain") is not None

    def _run_langchain(self, question: str) -> str:
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.tools import Tool

        tool_objects = [
            Tool(name=name, description=func.__doc__ or "", func=func)
            for name, func in self.tools.items()
        ]
        prompt = ChatPromptTemplate.from_template(
            """
You are a helpful assistant that uses tools.

Question: {input}
Thought: {agent_scratchpad}
""".strip()
        )
        agent = create_react_agent(self.llm, tool_objects, prompt)
        executor = AgentExecutor(agent=agent, tools=tool_objects, verbose=False)
        return executor.invoke({"input": question})
