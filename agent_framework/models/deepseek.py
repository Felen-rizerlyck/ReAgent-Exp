from __future__ import annotations

from .openai_compatible import OpenAICompatibleChatModel


class DeepSeekChatModel(OpenAICompatibleChatModel):
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 60,
        thinking_enabled: bool = False,
    ) -> None:
        extra_body = {
            "thinking": {"type": "disabled" if not thinking_enabled else "enabled"},
        }
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            extra_body=extra_body,
        )
