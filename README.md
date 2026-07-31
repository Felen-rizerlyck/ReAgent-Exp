# Simple Python Agent Framework

一个从零开始、便于扩展的 Python Agent 骨架，当前包含：

- 模型抽象层
- DeepSeek V4 默认接入
- 工具注册与调用
- Agent 执行循环
- 命令行交互入口

## 1. 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. 配置

复制 `.env.example` 为 `.env`，然后填入你的 API Key：

```bash
copy .env.example .env
```

默认模型配置：

- provider: `deepseek`
- model: `deepseek-v4-flash`

如果你想切到更强的版本，可以把 `AGENT_MODEL_NAME` 改为 `deepseek-v4-pro`。

## 3. 运行

```bash
python -m agent_framework.cli
```

进入命令行后可以直接提问，例如：

- `现在上海时间几点？`
- `帮我计算 (12 + 8) * 3`

输入 `exit` 或 `quit` 可退出。

## 4. 项目结构

```text
agent_framework/
  cli.py
  config.py
  agent.py
  tools.py
  builtin_tools.py
  models/
    base.py
    registry.py
    openai_compatible.py
    deepseek.py
```

## 5. 默认内置工具

当前内置工具统一定义在 `agent_framework/builtin_tools.py`：

- `get_current_time`
- `calculator`
- `echo`
- `list_directory`
- `read_text_file`
- `write_text_file`
- `append_text_file`
- `path_exists`
- `find_paths`

其中涉及文件系统的工具会默认保护：

- `.env`
- `.venv/`
- `.git/`

## 6. 后续扩展建议

- 增加记忆模块
- 增加规划器 Planner
- 增加多 Agent 协作
- 增加流式输出
- 增加更完整的工具参数校验

## 7. 如何添加新模型

这个框架已经把模型提供方做成了注册表模式。你只需要：

1. 新建一个模型类，继承 `ChatModel` 或直接复用 `OpenAICompatibleChatModel`
2. 在 `build_model_registry()` 中注册新的 provider 名称
3. 给它补上对应的环境变量读取逻辑

例如：

```python
from agent_framework.models.openai_compatible import OpenAICompatibleChatModel


class MyModel(OpenAICompatibleChatModel):
    def __init__(self, *, api_key: str, model_name: str, timeout: int = 60):
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url="https://example.com/v1",
            timeout=timeout,
        )
```

## 8. 研究模式

使用研究模式进行分析：

```bash
python -m agent_framework.cli --mode research
```

添加工具：

- `search_arxiv`
- `search_openalex`
- `search_web`
- `search_scholar`
- `research_literature`

The `research_literature` tool performs multi-source search, deduplication, ranking, evidence packaging, and a preliminary report.

## 9. 研究模式环境配置

设置环境变量：

- `SERPAPI_API_KEY`
- `OPENALEX_API_KEY`
- `OPENALEX_MAILTO`
- `ARXIV_USER_AGENT`
- `RESEARCH_TIMEOUT`
