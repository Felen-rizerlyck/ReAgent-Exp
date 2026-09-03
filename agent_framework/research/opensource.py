from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import quote

import requests

from agent_framework.schema.research import SearchQuery, SearchResult
from agent_framework.sources.base import SourceAdapter, SourceAdapterError


GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"
MAX_CONTENT_CHARACTERS = 24000
MAX_FILES_PER_REPOSITORY = 8


class OpenSourceError(Exception):
    """Raised when an allowlisted GitHub source cannot be read."""


class GitHubSourceAdapter(SourceAdapter):
    source_name = "opensource_github"

    def __init__(self, *, token: str | None = None, timeout: int = 30) -> None:
        self.token = token
        self.timeout = timeout

    def search(self, query: SearchQuery, limit: int = 10) -> list[SearchResult]:
        return search_github_repositories(query.query_text, limit=limit, token=self.token, timeout=self.timeout)

    def health_check(self) -> bool:
        return True


def search_github_repositories(
    query: str,
    *,
    limit: int = 10,
    token: str | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> list[SearchResult]:
    """Search GitHub repositories and enrich each result with repository evidence."""
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": max(1, min(limit, 20))}
    payload = _github_json("/search/repositories", params=params, token=token, timeout=timeout, retries=retries)
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise OpenSourceError("GitHub repository search returned an unexpected response shape")

    results: list[SearchResult] = []
    for item in items[: max(1, min(limit, 20))]:
        if not isinstance(item, dict) or not item.get("full_name"):
            continue
        try:
            results.append(_read_repository(item, token=token, timeout=timeout, retries=retries))
        except OpenSourceError as exc:
            results.append(_repository_result(item, notes=[{"status": "partial", "reason": str(exc)}]))
    return results


def read_github_raw_file(
    raw_url: str,
    *,
    token: str | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> str:
    """Read a raw GitHub file, restricted to raw.githubusercontent.com."""
    if not raw_url.startswith(GITHUB_RAW + "/"):
        raise OpenSourceError("raw file URL is outside raw.githubusercontent.com")
    response = _github_request(raw_url, token=token, timeout=timeout, retries=retries)
    if len(response.content) > 2 * 1024 * 1024:
        raise OpenSourceError("raw file exceeds 2 MB limit")
    return response.content.decode(response.encoding or "utf-8", errors="replace")


def write_opensource_snapshots(output_dir: str | Path, ranked_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = Path(output_dir) / "opensource_sources"
    root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for item in ranked_results:
        result = item.get("result") if isinstance(item, dict) else None
        if not isinstance(result, dict):
            continue
        raw = result.get("raw_payload")
        if not isinstance(raw, dict) or not raw.get("snapshot_markdown"):
            continue
        path = root / f"{_safe_name(result.get('source_id') or result.get('title'))}.md"
        path.write_text(str(raw["snapshot_markdown"]), encoding="utf-8")
        records.append({
            "repository": result.get("source_id"),
            "title": result.get("title"),
            "url": result.get("url"),
            "path": path.as_posix(),
            "version": raw.get("version"),
            "commit": raw.get("commit"),
            "release": raw.get("release"),
            "content_hash": raw.get("content_hash"),
        })
    return records


def _read_repository(item: dict[str, Any], *, token: str | None, timeout: int, retries: int) -> SearchResult:
    full_name = str(item["full_name"])
    repo = _github_json(f"/repos/{full_name}", token=token, timeout=timeout, retries=retries)
    default_branch = str(repo.get("default_branch") or item.get("default_branch") or "main")
    contents = _read_repository_files(full_name, default_branch, token=token, timeout=timeout, retries=retries)
    release = _latest_release(full_name, token=token, timeout=timeout, retries=retries)
    commit = _latest_commit(full_name, default_branch, token=token, timeout=timeout, retries=retries)
    return _repository_result(item, repo=repo, contents=contents, release=release, commit=commit)


def _read_repository_files(full_name: str, branch: str, *, token: str | None, timeout: int, retries: int) -> dict[str, str]:
    try:
        root = _github_json(f"/repos/{full_name}/git/trees/{quote(branch, safe='')}", params={"recursive": "1"}, token=token, timeout=timeout, retries=retries)
    except OpenSourceError:
        return {}
    tree = root.get("tree") if isinstance(root, dict) else []
    if not isinstance(tree, list):
        return {}
    candidates: list[str] = []
    for entry in tree:
        path = str(entry.get("path", "")) if isinstance(entry, dict) else ""
        lower = path.lower()
        if entry.get("type") != "blob" or not path:
            continue
        if lower in {"readme.md", "readme.rst", "readme.txt"} or lower.startswith("docs/") or lower.endswith(("/readme.md", "/readme.rst")):
            candidates.append(path)
    candidates.sort(key=lambda path: (0 if path.lower().startswith("readme") else 1, len(path)))
    selected = candidates[:MAX_FILES_PER_REPOSITORY]
    contents: dict[str, str] = {}
    for path in selected:
        raw_url = f"{GITHUB_RAW}/{full_name}/{quote(branch, safe='')}/{quote(path, safe='/')}"
        try:
            contents[path] = read_github_raw_file(raw_url, token=token, timeout=timeout, retries=retries)[:MAX_CONTENT_CHARACTERS]
        except OpenSourceError:
            continue
    return contents


def _latest_release(full_name: str, *, token: str | None, timeout: int, retries: int) -> dict[str, Any] | None:
    try:
        payload = _github_json(f"/repos/{full_name}/releases/latest", token=token, timeout=timeout, retries=retries)
    except OpenSourceError:
        return None
    return {key: payload.get(key) for key in ("tag_name", "name", "published_at", "html_url", "body")}


def _latest_commit(full_name: str, branch: str, *, token: str | None, timeout: int, retries: int) -> dict[str, Any] | None:
    try:
        payload = _github_json(f"/repos/{full_name}/commits", params={"sha": branch, "per_page": 1}, token=token, timeout=timeout, retries=retries)
    except OpenSourceError:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    commit = payload[0] if isinstance(payload[0], dict) else {}
    detail = commit.get("commit") or {}
    return {"sha": commit.get("sha"), "url": commit.get("html_url"), "message": detail.get("message"), "date": (detail.get("committer") or {}).get("date")}


def _repository_result(
    item: dict[str, Any],
    *,
    repo: dict[str, Any] | None = None,
    contents: dict[str, str] | None = None,
    release: dict[str, Any] | None = None,
    commit: dict[str, Any] | None = None,
    notes: list[dict[str, Any]] | None = None,
) -> SearchResult:
    repo = repo or item
    full_name = str(repo.get("full_name") or item.get("full_name"))
    contents = contents or {}
    release = release or {}
    commit = commit or {}
    version = release.get("tag_name") or repo.get("default_branch") or item.get("default_branch")
    evidence = _extract_project_evidence(contents, release.get("body") or "")
    snapshot = _repository_snapshot(full_name, repo, contents, release, commit, evidence)
    payload = {
        "source_type": "open_source_repository",
        "document_type": "github_repository",
        "publisher": "GitHub repository owner",
        "vendor_claim": False,
        "is_vendor_claim": False,
        "repository": full_name,
        "version": version,
        "commit": commit,
        "release": release,
        "default_branch": repo.get("default_branch"),
        "install": evidence["install"],
        "architecture": evidence["architecture"],
        "api": evidence["api"],
        "benchmark": evidence["benchmark"],
        "files_read": list(contents),
        "retrieved_at": datetime.utcnow().isoformat(),
        "content_hash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
        "snapshot_markdown": snapshot,
        "notes": notes or [],
    }
    abstract = _compact_text(repo.get("description") or "")
    return SearchResult(
        source="opensource_github",
        source_id=full_name,
        title=str(repo.get("name") or full_name),
        published_date=repo.get("updated_at") or repo.get("created_at"),
        venue="GitHub",
        abstract=abstract or snapshot[:1200],
        url=repo.get("html_url") or item.get("html_url"),
        query=item.get("query"),
        raw_payload=payload,
    )


def _extract_project_evidence(contents: dict[str, str], release_body: str) -> dict[str, str]:
    combined = "\n\n".join(contents.values()) + "\n\n" + release_body
    return {
        "install": _section_or_matches(combined, r"install(?:ation)?|getting started|quick start|setup|pip install|npm install"),
        "architecture": _section_or_matches(combined, r"architect(?:ure|ural)|how it works|design|组件|架构"),
        "api": _section_or_matches(combined, r"\bapi\b|usage|接口|调用"),
        "benchmark": _section_or_matches(combined, r"benchmark|evaluation|performance|结果|性能"),
    }


def _section_or_matches(text: str, pattern: str) -> str:
    lines = text.splitlines()
    hits: list[str] = []
    for index, line in enumerate(lines):
        if re.search(pattern, line, flags=re.IGNORECASE):
            hits.extend(lines[index : index + 8])
    return _compact_text("\n".join(dict.fromkeys(hits)))[:4000]


def _repository_snapshot(full_name: str, repo: dict[str, Any], contents: dict[str, str], release: dict[str, Any], commit: dict[str, Any], evidence: dict[str, str]) -> str:
    lines = [f"# {full_name}", "", f"- Repository: https://github.com/{full_name}", f"- Version: {release.get('tag_name') or repo.get('default_branch') or 'unknown'}", f"- Commit: {commit.get('sha') or 'unknown'}", f"- Release: {release.get('html_url') or 'none'}", f"- Retrieved at: {datetime.utcnow().isoformat()}", "- Vendor claim: false", "", str(repo.get("description") or "")]
    for label, key in (("Installation", "install"), ("Architecture", "architecture"), ("API", "api"), ("Benchmark", "benchmark")):
        lines.extend([f"\n## {label}", "", evidence[key] or "No matching information extracted."])
    lines.extend(["\n## Files Read", "", *[f"- `{path}`" for path in contents]])
    if release.get("body"):
        lines.extend(["\n## Latest Release Notes", "", str(release["body"])[:6000]])
    return "\n".join(lines) + "\n"


def _github_json(path: str, *, params: dict[str, Any] | None = None, token: str | None, timeout: int, retries: int) -> Any:
    response = _github_request(GITHUB_API + path, params=params, token=token, timeout=timeout, retries=retries)
    try:
        return response.json()
    except ValueError as exc:
        raise OpenSourceError("GitHub returned invalid JSON") from exc


def _github_request(url: str, *, params: dict[str, Any] | None = None, token: str | None, timeout: int, retries: int) -> requests.Response:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AgentResearch/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_error = "unknown GitHub error"
    for attempt in range(1, max(1, retries) + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < max(1, retries):
                time.sleep(2 ** (attempt - 1))
    raise OpenSourceError(last_error)


def _compact_text(value: Any) -> str:
    return re.sub(r"\n{3,}", "\n\n", str(value or "")).strip()


def _safe_name(value: Any) -> str:
    return (re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._") or "repository")[:120]
