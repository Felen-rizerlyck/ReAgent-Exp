# Workspace Tools

这些是为当前项目准备的“外接工具模块”，暂时没有直接接入 `agent_framework/` 的主 Agent。

当前提供：

- `read_text_file(path)`
- `write_text_file(path, content, overwrite=True)`
- `append_text_file(path, content)`
- `list_directory(path=".")`

## 安全限制

这些工具默认禁止访问或修改以下区域：

- `agent_framework/`
- `workspace_tools/`
- `.venv/`
- `.git/`
- `.env`

这样可以避免工具直接修改 Agent 自身逻辑或本地敏感配置。

## 后续接入

如果你后面想把这些工具真正注册进 Agent，我们可以单独做一步很小的接线修改，把它们挂到主工具注册表中。
