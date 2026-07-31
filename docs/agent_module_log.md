# Agent Module Log

This file records the current modules and capabilities available in the agent workspace.

## Core Chat Stack

- `agent_framework/agent.py`
  - Base agent execution loop
  - Tool-call handling
  - Local shortcuts for time and calculator queries

- `agent_framework/tools.py`
  - Tool schema generation
  - Tool registry
  - Tool invocation wrapper

- `agent_framework/builtin_tools.py`
  - Core utility tools
  - Workspace-safe file operations
  - Directory listing and path checks

- `agent_framework/models/`
  - DeepSeek-compatible model layer
  - Provider registry
  - OpenAI-compatible transport

## Research Stack

- `agent_framework/schema/research.py`
  - `ResearchTask`
  - `SearchQuery`
  - `SearchResult`
  - `EvidenceItem`
  - `ResearchReport`
  - `ResearchSession`
  - research status and confidence enums

- `agent_framework/sources/`
  - `SourceAdapter` base interface
  - `ArxivSourceAdapter`
  - `OpenAlexSourceAdapter`
  - `SerpApiSearchAdapter`

- `agent_framework/research/`
  - source adapter registry
  - research runtime configuration
  - research tool registration
  - research workflow scaffolding
  - research planning scaffold

## Research Mode Behavior

- Research mode is enabled through the CLI `--mode research` flag.
- Research mode adds search tools to the model toolset.
- Research mode also appends research workflow instructions to the system prompt.
- The model is instructed to prefer arXiv first, then OpenAlex, then SerpApi for broader discovery and verification.

## Available Retrieval Tools

- `search_arxiv`
- `search_openalex`
- `search_web`
- `search_scholar`
- `research_literature`

## Current Source Confidence Policy

- arXiv: high
- OpenAlex: high
- SerpApi web results: medium
- SerpApi scholar results: medium

## Required Environment Variables

- `SERPAPI_API_KEY` for `search_web` and `search_scholar`
- `OPENALEX_API_KEY` for higher-throughput OpenAlex access, if needed
- `OPENALEX_MAILTO` to identify requests to OpenAlex
- `ARXIV_USER_AGENT` to identify requests to arXiv
- `RESEARCH_TIMEOUT` to tune research request timeout

## Pending Extensions

- PDF fetching
- full-text parsing
- evidence store persistence
- citation verification
- multi-agent orchestration
- memory backend beyond in-memory state

## Research Pipeline Added

- deduplication of raw search results
- ranking by query overlap, source confidence, and recency
- evidence item extraction from abstracts and metadata
- structured preliminary research report generation

## Update Rule

When the agent architecture changes materially, update this file so the current module inventory stays accurate.
