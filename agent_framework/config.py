from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(dotenv_path: str | Path = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(slots=True)
class AgentSettings:
    model_provider: str = "deepseek"
    model_name: str = "deepseek-v4-flash"
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 60
    max_steps: int = 8

    @classmethod
    def from_env(cls) -> "AgentSettings":
        load_dotenv()
        provider = os.getenv("AGENT_MODEL_PROVIDER", "deepseek")
        model_name = os.getenv("AGENT_MODEL_NAME", "deepseek-v4-flash")

        api_key_map = {
            "deepseek": os.getenv("DEEPSEEK_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
        }
        base_url_map = {
            "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "openai": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        }

        return cls(
            model_provider=provider,
            model_name=model_name,
            api_key=api_key_map.get(provider),
            base_url=base_url_map.get(provider),
            timeout=int(os.getenv("AGENT_TIMEOUT", "60")),
            max_steps=int(os.getenv("AGENT_MAX_STEPS", "8")),
        )
