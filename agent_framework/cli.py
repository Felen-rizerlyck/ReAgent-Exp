from __future__ import annotations

import argparse
import sys

from .agent import Agent, DEFAULT_SYSTEM_PROMPT
from .builtin_tools import build_tool_registry
from .config import AgentSettings
from .models.deepseek import DeepSeekChatModel
from .models.registry import ModelRegistry
from .research.tools import RESEARCH_SYSTEM_PROMPT, build_research_tool_registry


def build_model_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.register("deepseek", lambda **kwargs: DeepSeekChatModel(**kwargs))
    return registry


def create_agent(
    settings: AgentSettings,
    mode: str = "research",
    status_callback=None,
) -> Agent:
    if not settings.api_key:
        raise ValueError(
            "Missing API key. Please set the corresponding environment variable in .env."
        )

    model_registry = build_model_registry()
    model = model_registry.create(
        settings.model_provider,
        api_key=settings.api_key,
        model_name=settings.model_name,
        base_url=settings.base_url,
        timeout=settings.timeout,
    )

    tools = build_tool_registry()
    system_prompt = DEFAULT_SYSTEM_PROMPT
    if mode == "research":
        tools.register_many(build_research_tool_registry(model=model).tools())
        system_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n{RESEARCH_SYSTEM_PROMPT}"

    agent = Agent(
        model=model,
        tools=tools,
        max_steps=settings.max_steps,
        system_prompt=system_prompt,
        status_callback=status_callback,
    )
    return agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple Python Agent Framework")
    parser.add_argument("--provider", help="Model provider, e.g. deepseek")
    parser.add_argument("--model", help="Model name, e.g. deepseek-v4-flash")
    parser.add_argument("--mode", choices=["chat", "research"], default="research")
    args = parser.parse_args()

    settings = AgentSettings.from_env()
    if args.provider:
        settings.model_provider = args.provider
    if args.model:
        settings.model_name = args.model

    def show_status(message: str) -> None:
        print(f"[status] {message}", file=sys.stderr, flush=True)

    agent = create_agent(settings, mode=args.mode, status_callback=show_status)

    print("Simple Agent is ready. Type 'exit' to quit.")
    print(f"Loaded tools: {', '.join(agent.tools.names())}")
    while True:
        user_input = input("\nYou> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if user_input.lower() == "/reset":
            agent.reset()
            print("Conversation and research binding reset.")
            continue
        if not user_input:
            continue

        try:
            reply = agent.run(user_input)
        except Exception as exc:  # noqa: BLE001
            reply = f"Agent execution failed: {exc}"
        print(f"\nAgent> {reply}")


if __name__ == "__main__":
    main()
