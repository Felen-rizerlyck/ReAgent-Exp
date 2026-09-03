from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .models.base import ChatModel, Message, ModelError
from .tools import ToolRegistry


DEFAULT_SYSTEM_PROMPT = """\u4f60\u662f\u4e00\u4e2a\u7b80\u5355\u4f46\u53ef\u9760\u7684 Python Agent\u3002

\u4f60\u7684\u76ee\u6807\uff1a
1. \u7406\u89e3\u7528\u6237\u95ee\u9898\u3002
2. \u5fc5\u8981\u65f6\u8c03\u7528\u5de5\u5177\u3002
3. \u57fa\u4e8e\u5de5\u5177\u7ed3\u679c\u7ee7\u7eed\u63a8\u7406\u3002
4. \u7ed9\u51fa\u6e05\u6670\u3001\u76f4\u63a5\u7684\u6700\u7ec8\u7b54\u6848\u3002

\u5f53\u5de5\u5177\u80fd\u5e2e\u52a9\u4f60\u83b7\u5f97\u66f4\u51c6\u786e\u7684\u7ed3\u679c\u65f6\uff0c\u4f18\u5148\u8c03\u7528\u5de5\u5177\u3002"""


TIME_KEYWORDS = (
    "\u5317\u4eac\u65f6\u95f4",
    "\u73b0\u5728\u51e0\u70b9",
    "\u5f53\u524d\u65f6\u95f4",
    "\u73b0\u5728\u65f6\u95f4",
    "\u51e0\u70b9\u4e86",
)


CALC_PATTERNS = (
    r"\u8ba1\u7b97[:\uff1a]?\s*(.+)",
    r"\u5e2e\u6211\u7b97[:\uff1a]?\s*(.+)",
)


class Agent:
    def __init__(
        self,
        *,
        model: ChatModel,
        tools: ToolRegistry,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: int = 8,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.status_callback = status_callback
        self.messages: list[Message] = []
        self.research_output_dir: str | None = None

    def reset(self) -> None:
        """Start a fresh conversation and clear its research binding."""
        self.messages = []
        self.research_output_dir = None

    def _emit_status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)

    def _try_handle_locally(self, user_input: str) -> str | None:
        text = user_input.strip()

        if any(keyword in text for keyword in TIME_KEYWORDS):
            return self.tools.call("get_current_time", {})

        for pattern in CALC_PATTERNS:
            match = re.search(pattern, text)
            if match:
                expression = match.group(1).strip()
                return self.tools.call("calculator", {"expression": expression})

        return None

    def run(self, user_input: str) -> str:
        local_result = self._try_handle_locally(user_input)
        if local_result is not None:
            if not self.messages:
                self.messages.append({"role": "system", "content": self.system_prompt})
            self.messages.extend([
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": local_result},
            ])
            return local_result

        if not self.messages:
            self.messages.append({"role": "system", "content": self.system_prompt})
        self.messages.append({"role": "user", "content": user_input})

        for step in range(1, self.max_steps + 1):
            self._emit_status(f"step {step}/{self.max_steps}: calling model")
            try:
                response = self.model.complete(self.messages, tools=self.tools.specs())
            except ModelError as exc:
                self._emit_status(f"model call failed: {exc}")
                return f"Model call failed: {exc}"

            assistant_message: Message = {
                "role": "assistant",
                "content": response.content,
            }

            if response.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in response.tool_calls
                ]

            self.messages.append(assistant_message)

            if not response.tool_calls:
                self._emit_status("model returned a final answer")
                if self.research_output_dir:
                    _save_research_response(self.research_output_dir, user_input, self.messages, response.content)
                return response.content.strip()

            for call in response.tool_calls:
                self._emit_status(f"calling tool: {call.name}")
                self.tools.set_research_output_dir(self.research_output_dir)
                try:
                    tool_result = self.tools.call(call.name, call.arguments)
                except Exception as exc:  # noqa: BLE001
                    tool_result = f"Tool execution failed: {exc}"
                    self._emit_status(f"tool failed: {call.name}: {exc}")
                else:
                    self._emit_status(f"tool completed: {call.name}")

                self.research_output_dir = self.research_output_dir or _find_research_output_dir(
                    tool_result, call.arguments
                )

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": tool_result,
                    }
                )

        self._emit_status("agent stopped at the maximum number of steps")
        return "Agent stopped because it reached the maximum number of steps."


def _find_research_output_dir(tool_result: str, arguments: dict[str, object]) -> str | None:
    try:
        payload = json.loads(tool_result)
    except (TypeError, json.JSONDecodeError):
        payload = {}
    if isinstance(payload, dict):
        artifacts = payload.get("artifacts")
        if isinstance(artifacts, dict) and isinstance(artifacts.get("output_dir"), str):
            return artifacts["output_dir"]
        if isinstance(payload.get("research_dir"), str):
            return payload["research_dir"]
    value = arguments.get("research_dir")
    return value if isinstance(value, str) else None


def _save_research_response(
    output_dir: str,
    user_input: str,
    messages: list[Message],
    final_answer: str,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    target = Path(output_dir)
    if not target.is_absolute():
        target = project_root / target
    target = target.resolve()
    try:
        target.relative_to(project_root / "research_results")
    except ValueError:
        return
    if not target.is_dir():
        return
    (target / "final_answer.md").write_text(final_answer.strip() + "\n", encoding="utf-8")
    trace = {
        "generated_at": datetime.utcnow().isoformat(),
        "user_input": user_input,
        "messages": messages,
        "final_answer": final_answer,
    }
    (target / "conversation.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
