import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Protocol

from agent_tools import TOOLS_MAP


class ChatCompletions(Protocol):
    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        stop: Optional[List[str]] = None,
    ) -> object:
        ...


class ChatInterface(Protocol):
    completions: ChatCompletions


class LLMClient(Protocol):
    chat: ChatInterface


REACT_SYSTEM_PROMPT = """
You are an internal AI assistant that answers complex user questions using RAG tools.
Available tools:
{tool_descriptions}

Follow this exact format step-by-step:

Question: user input question
Thought: describe what to do next based only on the latest Observation
Action: must be one of [{tool_names}]
Action Input: tool input (plain text or JSON)
Observation: (left blank, system fills tool output)
... (repeat Thought/Action/Observation until enough info)
Thought: I now know the final answer based only on Observations.
Final Answer: final response to the original question.

Rules:
- Only use facts found in Observations. Do not make up details.
- If Observations are insufficient, say what is missing and ask for clarification.

Begin.
""".strip()


@dataclass(frozen=True)
class ReactResult:
    answer: str
    steps: List[str]


def get_tool_descriptions(tools: Dict[str, Callable[[str], str]]) -> str:
    return "\n".join([f"- {name}: {tool.__doc__}" for name, tool in tools.items()])


def call_llm(
    client: LLMClient,
    *,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    stop: Optional[List[str]] = None,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stop=stop,
    )
    return response.choices[0].message.content.strip()


def run_react_agent(
    user_query: str,
    *,
    client: LLMClient,
    model: str,
    tools: Optional[Dict[str, Callable[[str], str]]] = None,
    max_steps: int = 10,
) -> ReactResult:
    tools = tools or TOOLS_MAP
    tool_names = ", ".join(tools.keys())
    system_prompt = REACT_SYSTEM_PROMPT.format(
        tool_descriptions=get_tool_descriptions(tools),
        tool_names=tool_names,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {user_query}"},
    ]

    steps: List[str] = []

    for _ in range(max_steps):
        content = call_llm(
            client,
            model=model,
            messages=messages,
            temperature=0.1,
            stop=["Observation:"],
        )
        messages.append({"role": "assistant", "content": content})
        steps.append(content)

        if "Final Answer:" in content:
            final_answer = content.split("Final Answer:")[-1].strip()
            return ReactResult(answer=final_answer, steps=steps)

        action_match = re.search(r"Action:\s*(.*)", content)
        input_match = re.search(r"Action Input:\s*(.*)", content)

        if not action_match or not input_match:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "System Warning: Unable to parse your Action. "
                        "Use 'Action: <Tool Name>' followed by 'Action Input: <Value>'."
                    ),
                }
            )
            continue

        tool_name = action_match.group(1).strip()
        tool_input = input_match.group(1).strip()

        if tool_name in tools:
            try:
                observation = tools[tool_name](tool_input)
            except Exception as exc:  # noqa: BLE001 - surface tool errors to model
                observation = f"Error: Tool execution failed: {exc}"
        else:
            observation = f"Error: Tool '{tool_name}' not found"

        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return ReactResult(
        answer="Error: exceeded max steps without finishing.",
        steps=steps,
    )


def generate_thoughts(
    state: str,
    *,
    client: LLMClient,
    model: str,
    k: int = 3,
) -> List[str]:
    prompt = (
        "Current solution state:\n"
        f"{state}\n\n"
        f"Generate {k} distinct next-step thoughts or actions. "
        "Provide one per line."
    )
    response = call_llm(
        client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return [line.strip() for line in response.split("\n") if line.strip()]


def evaluate_thoughts(
    thoughts: Iterable[str],
    *,
    client: LLMClient,
    model: str,
    goal: str,
) -> List[float]:
    scores: List[float] = []
    for thought in thoughts:
        prompt = (
            f"Goal: {goal}\n"
            f"Candidate step: {thought}\n\n"
            "Score how helpful this step is (0 to 10). "
            "Return only a number."
        )
        response = call_llm(
            client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        match = re.findall(r"[-+]?\d*\.?\d+", response)
        if not match:
            scores.append(0.0)
            continue
        scores.append(float(match[0]) / 10.0)
    return scores


def run_tot_agent(
    problem: str,
    *,
    client: LLMClient,
    model: str,
    depth: int = 3,
    width: int = 3,
) -> str:
    current_states = [problem]

    for _ in range(depth):
        next_candidates: List[str] = []
        for state in current_states:
            thoughts = generate_thoughts(state, client=client, model=model, k=width)
            for thought in thoughts:
                next_candidates.append(f"{state}\n -> {thought}")

        if not next_candidates:
            break

        scores = evaluate_thoughts(next_candidates, client=client, model=model, goal=problem)
        scored_candidates = sorted(
            zip(scores, next_candidates), key=lambda pair: pair[0], reverse=True
        )
        current_states = [cand for _, cand in scored_candidates[:width]]

    return current_states[0]
