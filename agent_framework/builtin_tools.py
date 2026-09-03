from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

from .tools import Tool, ToolRegistry, tool


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROTECTED_DIRS = {
    WORKSPACE_ROOT / "agent_framework",
    WORKSPACE_ROOT / "workspace_tools",
    WORKSPACE_ROOT / ".git",
    WORKSPACE_ROOT / ".venv",
    WORKSPACE_ROOT / "__pycache__",
}
PROTECTED_FILES = {
    WORKSPACE_ROOT / ".env",
}


class FileToolError(Exception):
    """Raised when a file tool operation is not allowed."""


def _resolve_user_path(path: str) -> Path:
    candidate = (WORKSPACE_ROOT / path).resolve()
    try:
        candidate.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise FileToolError("Path escapes the workspace root.") from exc
    return candidate


def _ensure_allowed(target: Path) -> None:
    if target in PROTECTED_FILES:
        raise FileToolError(f"Protected file access denied: {target.name}")

    for protected_dir in PROTECTED_DIRS:
        try:
            target.relative_to(protected_dir)
        except ValueError:
            continue
        raise FileToolError(f"Protected path access denied: {target}")


@tool("\u83b7\u53d6\u5f53\u524d\u672c\u5730\u65f6\u95f4\u3002")
def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool("\u6267\u884c\u57fa\u7840\u6570\u5b66\u8868\u8fbe\u5f0f\u8ba1\u7b97\uff0c\u4f8b\u5982 '(12 + 8) * 3'\u3002")
def calculator(expression: str) -> str:
    node = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Num,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.UAdd,
        ast.USub,
        ast.Load,
    )

    for child in ast.walk(node):
        if not isinstance(child, allowed_nodes):
            raise ValueError("Unsupported expression")

    result = eval(compile(node, "<calculator>", "eval"), {"__builtins__": {}}, {})
    return str(result)


@tool("\u56de\u663e\u8f93\u5165\u5185\u5bb9\uff0c\u9002\u5408\u8c03\u8bd5\u5de5\u5177\u8c03\u7528\u3002")
def echo(text: str) -> str:
    return text


@tool("\u5217\u51fa\u5de5\u4f5c\u533a\u76ee\u5f55\u4e2d\u7684\u6587\u4ef6\u548c\u5b50\u76ee\u5f55\u3002")
def list_directory(path: str = ".") -> list[str]:
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    if not target.exists():
        raise FileToolError(f"Directory not found: {path}")
    if not target.is_dir():
        raise FileToolError(f"Not a directory: {path}")

    items: list[str] = []
    for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
        skip = False
        for protected_dir in PROTECTED_DIRS:
            if child == protected_dir:
                skip = True
                break
        if not skip:
            items.append(child.relative_to(WORKSPACE_ROOT).as_posix())
    return items


@tool("\u8bfb\u53d6\u5de5\u4f5c\u533a\u4e2d\u7684 UTF-8 \u6587\u672c\u6587\u4ef6\u3002")
def read_text_file(path: str) -> str:
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    if not target.exists():
        raise FileToolError(f"File not found: {path}")
    if not target.is_file():
        raise FileToolError(f"Not a file: {path}")

    return target.read_text(encoding="utf-8")


@tool("\u5199\u5165 UTF-8 \u6587\u672c\u6587\u4ef6\u3002overwrite \u4e3a false \u65f6\uff0c\u5982\u679c\u6587\u4ef6\u5df2\u5b58\u5728\u5219\u62d2\u7edd\u8986\u76d6\u3002")
def write_text_file(path: str, content: str, overwrite: bool = True) -> str:
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    if target.exists() and not overwrite:
        raise FileToolError(f"File already exists: {path}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote file: {target.relative_to(WORKSPACE_ROOT).as_posix()}"


@tool("\u5728 UTF-8 \u6587\u672c\u6587\u4ef6\u672b\u5c3e\u8ffd\u52a0\u5185\u5bb9\u3002")
def append_text_file(path: str, content: str) -> str:
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(content)
    return f"Appended file: {target.relative_to(WORKSPACE_ROOT).as_posix()}"


@tool("\u68c0\u67e5\u5de5\u4f5c\u533a\u4e2d\u67d0\u4e2a\u8def\u5f84\u662f\u5426\u5b58\u5728\u3002")
def path_exists(path: str) -> str:
    target = _resolve_user_path(path)
    _ensure_allowed(target)
    return "true" if target.exists() else "false"


@tool("\u5728\u5de5\u4f5c\u533a\u4e2d\u6309\u540d\u79f0\u67e5\u627e\u6587\u4ef6\u6216\u76ee\u5f55\u3002")
def find_paths(keyword: str, path: str = ".") -> list[str]:
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    if not target.exists():
        raise FileToolError(f"Directory not found: {path}")
    if not target.is_dir():
        raise FileToolError(f"Not a directory: {path}")

    matches: list[str] = []
    for child in target.rglob("*"):
        blocked = False
        for protected_dir in PROTECTED_DIRS:
            try:
                child.relative_to(protected_dir)
            except ValueError:
                continue
            blocked = True
            break
        if blocked:
            continue

        if keyword.lower() in child.name.lower():
            matches.append(child.relative_to(WORKSPACE_ROOT).as_posix())

    return matches[:200]


def get_builtin_tools() -> list[Tool]:
    return [
        get_current_time,
        calculator,
        echo,
        list_directory,
        read_text_file,
        write_text_file,
        append_text_file,
        path_exists,
        find_paths,
    ]


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_many(get_builtin_tools())
    return registry
