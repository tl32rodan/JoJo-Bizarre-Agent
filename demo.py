import argparse
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

from agent_core import LLMClient, ReactResult, query_sales_database, run_react_agent


@dataclass(frozen=True)
class SearchEngine:
    index_path: Path

    def search(self, query: str) -> str:
        return f"[RAG]: Results for '{query}' from index at {self.index_path}"


def initialize_search_engine(index_path: str) -> SearchEngine:
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Index not found at {path}."
        )
    return SearchEngine(index_path=path)


@dataclass
class ReActAgent:
    client: LLMClient
    model: str
    tools: Dict[str, Callable[[str], str]]

    def run(self, question: str) -> ReactResult:
        return run_react_agent(
            question,
            client=self.client,
            model=self.model,
            tools=self.tools,
        )


def build_llm_client() -> LLMClient:
    spec = importlib.util.find_spec("openai")
    if spec is None:
        raise RuntimeError("Missing 'openai' package. Install it to run the demo.")
    openai = importlib.import_module("openai")
    return openai.OpenAI()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ReAct agent demo interactively.")
    parser.add_argument(
        "--index",
        default="../faiss-for-code-indexing/faiss_index_store",
        help="Path to the FAISS index store built by the RAG repo.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model name for the LLM backend.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        search_engine = initialize_search_engine(args.index)
    except FileNotFoundError as exc:
        print(
            f"{exc} Index 需先在 RAG repo 建好。",
        )
        return

    client = build_llm_client()
    tools = {
        "search_docs": search_engine.search,
        "search_sales": query_sales_database,
    }
    agent = ReActAgent(client=client, model=args.model, tools=tools)

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
        print(result.answer)


if __name__ == "__main__":
    main()
