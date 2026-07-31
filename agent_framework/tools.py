from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable


def python_type_to_json_type(annotation: Any) -> str:
    mapping = {
        int: "integer",
        float: "number",
        bool: "boolean",
        str: "string",
        dict: "object",
        list: "array",
    }
    return mapping.get(annotation, "string")


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def call(self, arguments: dict[str, Any]) -> str:
        result = self.func(**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool_obj: Tool) -> None:
        self._tools[tool_obj.name] = tool_obj

    def register_many(self, tool_objects: list[Tool]) -> None:
        for tool_obj in tool_objects:
            self.register(tool_obj)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            available = ", ".join(sorted(self._tools))
            raise KeyError(f"Tool '{name}' not found. Available: {available}")
        return self._tools[name]

    def specs(self) -> list[dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        return self.get(name).call(arguments)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def tools(self) -> list[Tool]:
        return list(self._tools.values())


def build_schema_from_function(func: Callable[..., Any]) -> dict[str, Any]:
    signature = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in signature.parameters.items():
        annotation = param.annotation if param.annotation is not inspect._empty else str
        properties[param_name] = {
            "type": python_type_to_json_type(annotation),
        }
        if param.default is inspect._empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def tool(description: str) -> Callable[[Callable[..., Any]], Tool]:
    def decorator(func: Callable[..., Any]) -> Tool:
        return Tool(
            name=func.__name__,
            description=description,
            parameters=build_schema_from_function(func),
            func=func,
        )

    return decorator
