from __future__ import annotations

import json
from typing import Any

import requests

from .base import ChatModel, Message, ModelError, ModelResponse, ToolCall


class OpenAICompatibleChatModel(ChatModel):
    def __init__(
        self,
        *,
        model_name: str,
        api_key: str,
        base_url: str,
        timeout: int = 60,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.extra_body = extra_body or {}

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            **self.extra_body,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.SSLError as exc:
            raise ModelError(
                "SSL handshake failed while connecting to the model provider. "
                "This is usually caused by network interception, proxy/VPN issues, "
                "or TLS compatibility problems on the current machine."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ModelError(f"Model request failed: {exc}") from exc

        try:
            data = response.json()
            message = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelError(
                "Model provider returned an invalid chat completion response."
            ) from exc

        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []

        for item in raw_tool_calls:
            function = item.get("function", {})
            arguments_text = function.get("arguments") or "{}"
            try:
                arguments = json.loads(arguments_text)
            except json.JSONDecodeError:
                arguments = {"raw_arguments": arguments_text}

            tool_calls.append(
                ToolCall(
                    id=item["id"],
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )

        return ModelResponse(content=content, tool_calls=tool_calls, raw=data)
