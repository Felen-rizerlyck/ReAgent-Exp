from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from types import UnionType
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints


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


def _annotation_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Convert a resolved Python annotation into a small JSON schema."""
    if annotation is Any:
        return {}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, UnionType):
        non_none = [item for item in args if item is not type(None)]
        if len(non_none) == 1:
            schema = _annotation_to_json_schema(non_none[0])
            schema["nullable"] = True
            return schema
        return {"anyOf": [_annotation_to_json_schema(item) for item in non_none]}

    if origin is list:
        item_schema = _annotation_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item_schema}

    if origin is dict:
        value_schema = _annotation_to_json_schema(args[1]) if len(args) > 1 else {}
        return {"type": "object", "additionalProperties": value_schema}

    json_type = python_type_to_json_type(annotation)
    return {"type": json_type}


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
        self._research_output_dir: str | None = None

    def set_research_output_dir(self, output_dir: str | None) -> None:
        """Bind research tools to the current conversation's result directory."""
        self._research_output_dir = output_dir

    def get_research_output_dir(self) -> str | None:
        return self._research_output_dir

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
    try:
        type_hints = get_type_hints(func)
    except (NameError, TypeError):
        type_hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in signature.parameters.items():
        annotation = type_hints.get(param_name, param.annotation)
        if annotation is inspect._empty:
            annotation = str
        properties[param_name] = _annotation_to_json_schema(annotation)
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
