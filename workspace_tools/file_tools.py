from __future__ import annotations

from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROTECTED_DIRS = {
    WORKSPACE_ROOT / "agent_framework",
    WORKSPACE_ROOT / ".venv",
    WORKSPACE_ROOT / ".git",
    WORKSPACE_ROOT / "__pycache__",
    WORKSPACE_ROOT / "workspace_tools",
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


def read_text_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace, excluding protected paths."""
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    if not target.exists():
        raise FileToolError(f"File not found: {path}")
    if not target.is_file():
        raise FileToolError(f"Not a file: {path}")

    return target.read_text(encoding="utf-8")


def write_text_file(path: str, content: str, overwrite: bool = True) -> str:
    """Write a UTF-8 text file inside the workspace, excluding protected paths."""
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    if target.exists() and not overwrite:
        raise FileToolError(f"File already exists: {path}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote file: {target.relative_to(WORKSPACE_ROOT)}"


def append_text_file(path: str, content: str) -> str:
    """Append UTF-8 text to a workspace file, excluding protected paths."""
    target = _resolve_user_path(path)
    _ensure_allowed(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(content)
    return f"Appended file: {target.relative_to(WORKSPACE_ROOT)}"


def list_directory(path: str = ".") -> list[str]:
    """List files in a workspace directory, excluding protected directories."""
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
