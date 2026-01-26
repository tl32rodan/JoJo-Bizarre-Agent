import argparse
import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

from agent_core import ReactResult
from app.config import load_config
from app.core.react_agent import ReactAgentRunner
from app.tools import TOOLS


@dataclass(frozen=True)
class SearchEngine:
    index_path: Path

    def search(self, query: str) -> str:
        return f"[RAG]: Results for '{query}' from index at {self.index_path}"


def initialize_search_engine(index_path: str) -> SearchEngine:
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(f"Index not found at {path}.")
    return SearchEngine(index_path=path)


class OpenAIClientAdapter:
    def __init__(self, client, *, model: str) -> None:
        self._client = client
        self._model = model

    def invoke(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()


@dataclass
class ReActAgent:
    runner: ReactAgentRunner

    def run(self, question: str) -> ReactResult | str:
        return self.runner.run(question)


def build_llm_client(model: str) -> OpenAIClientAdapter:
    spec = importlib.util.find_spec("openai")
    if spec is None:
        raise RuntimeError("Missing 'openai' package. Install it to run the demo.")
    openai = importlib.import_module("openai")
    client = openai.OpenAI()
    return OpenAIClientAdapter(client, model=model)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ReAct agent demo interactively.")
    parser.add_argument(
        "--index",
        default="lib/faiss_code_indexer/faiss_index_store",
        help="Path to the FAISS index store built by the RAG repo.",
    )
    parser.add_argument(
        "--model",
        default=load_config().llm.model_name,
        help="Model name for the LLM backend.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        search_engine = initialize_search_engine(args.index)
    except FileNotFoundError as exc:
        print(f"{exc} Index 需先在 RAG repo 建好。")
        return

    client = build_llm_client(args.model)
    tools: Dict[str, Callable[[str], str]] = {
        **TOOLS,
        "search_docs": search_engine.search,
    }
    agent = ReActAgent(
        runner=ReactAgentRunner(llm=client, model=args.model, tools=tools)
    )

    print("Enter your question (type 'exit' or 'quit' to leave).")
    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print("\nExiting...")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        result = agent.run(user_input)
        print("\nAnswer:")
        if isinstance(result, ReactResult):
            print(result.answer)
        else:
            print(result)


if __name__ == "__main__":
    main()
