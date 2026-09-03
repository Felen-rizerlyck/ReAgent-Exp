# Literature Research Agent

An extensible Python Agent framework for general chat, tool calling, and multi-source literature research.

Current capabilities:

- OpenAI-compatible chat model transport, with DeepSeek enabled by default;
- tool registration, JSON schema generation, and a bounded Agent loop;
- built-in time, calculator, and workspace file tools;
- arXiv, OpenAlex, SerpApi Web, and Google Scholar search;
- normalized search results, deduplication, relevance ranking, and source confidence;
- structured research reports and reference lists;
- automatic export of every research pass to `research_results/`.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy the environment template and add the model API key:

```bash
copy .env.example .env
```

Default model configuration:

```text
AGENT_MODEL_PROVIDER=deepseek
AGENT_MODEL_NAME=deepseek-v4-flash
```

Optional research configuration:

```text
SERPAPI_API_KEY=        # required for Web and Google Scholar search
OPENALEX_API_KEY=       # optional
OPENALEX_MAILTO=        # optional request identification
ARXIV_USER_AGENT=       # optional request identification
RESEARCH_TIMEOUT=30     # optional source request timeout
```

Optional model and Agent settings:

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com
AGENT_TIMEOUT=60
AGENT_MAX_STEPS=8
```

## Running

The default mode is research mode:

```bash
python -m agent_framework.cli
```

Modes can also be selected explicitly:

```bash
python -m agent_framework.cli --mode chat
python -m agent_framework.cli --mode research
```

Optional provider and model overrides:

```bash
python -m agent_framework.cli --provider deepseek --model deepseek-v4-flash
```

Enter a question in the interactive prompt. Type `exit` or `quit` to leave.

## Research Tools

Research mode registers the following tools:

- `search_arxiv`: search arXiv papers and preprints;
- `search_openalex`: search OpenAlex scholarly works and metadata;
- `search_web`: search general web pages through SerpApi;
- `search_scholar`: search Google Scholar through SerpApi;
- `research_literature`: run multi-source search, deduplication, ranking, evidence packaging, and report generation.

The normalized source names are `arxiv`, `openalex`, `serpapi_web`, and `serpapi_scholar`. SerpApi results are primarily discovery and cross-checking signals; they are not automatically equivalent to peer-reviewed sources.

## Research Result Export

Each `research_literature` call creates a new directory under the project root:

```text
research_results/
  topic__YYYYMMDD_HHMMSS_microseconds/
    report.md
    report.json
    references.md
    references.json
    metadata.json
```

File descriptions:

- `report.md`: readable Markdown report;
- `report.json`: structured research report;
- `references.md`: references with authors, dates, sources, and URLs;
- `references.json`: metadata for the top ranked results;
- `metadata.json`: query, sources, result counts, and export information.

The current version creates reference links only. It does not download paper files.

Existing return fields from `research_literature` are preserved. The result additionally contains an `artifacts` field:

```json
{
  "artifacts": {
    "output_dir": "...",
    "report_path": "...",
    "report_json_path": "...",
    "references_path": "...",
    "references_json_path": "...",
    "metadata_path": "..."
  }
}
```

If local export fails, the search result is still returned and `artifacts` contains `status` and `reason` fields.

## Project Structure

```text
agent_framework/
  agent.py                 # Agent execution loop
  cli.py                   # CLI entry point and composition
  config.py                # environment configuration
  tools.py                 # tool definitions and registry
  builtin_tools.py         # built-in tools
  models/                  # model abstractions and providers
  schema/                  # research data models
  sources/                 # external source adapters
  research/                # pipeline, processing, export, and runtime config
  memory/                  # session memory abstractions and in-memory store
docs/                      # architecture, roadmap, and usage notes
research_results/          # generated at runtime
workspace_tools/           # separately attachable workspace tools
```

## Safety and Current Limitations

- File paths are restricted to the workspace; `.env`, `.git/`, `.venv/`, `agent_framework/`, and `workspace_tools/` are protected;
- research exports use generated unique directory names and do not overwrite previous results;
- reports currently use retrieved metadata and abstracts, without PDF full-text parsing;
- only an in-memory session store is available;
- there is no HTTP service entry point yet; the primary interface is the CLI.

## Adding a Model Provider

Subclass `ChatModel` or reuse `OpenAICompatibleChatModel`, then register the provider in `build_model_registry()` in `agent_framework/cli.py` and add its environment configuration in `config.py`.

Example:

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

## Future Directions

- query planning and iterative research;
- PDF download and full-text parsing;
- claim-to-evidence and citation verification;
- persistent sessions, caching, and report management;
- HTTP service interface;
- multi-agent orchestration and research quality evaluation.
