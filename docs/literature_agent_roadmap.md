# Literature Research Agent Roadmap

This document is the implementation guide for evolving the current simple agent into a literature research agent.

For the higher-level architecture rules and extension constraints, see [Literature Research Agent Design Principles](./literature_agent_design_principles.md).

## 1. Target Capability

The agent should support questions like:

- "What are the current research hotspots in X?"
- "Summarize the latest progress on Y."
- "Find representative papers and compare their methods."
- "Give me a literature review outline with citations."

The output should not be a plain answer only. It should be evidence-backed and include:

- Search strategy
- Retrieved sources
- Relevance ranking
- Summary of key findings
- Gaps and open problems
- Citation list

## 2. Recommended Architecture

Keep the existing `Agent -> ToolRegistry -> Model` core, but split the research workflow into dedicated layers:

1. Query understanding and planning
2. Retrieval from multiple sources
3. Evidence normalization and scoring
4. Reading and summarization
5. Citation formatting
6. Session memory and cache

Suggested logical components:

- `QueryPlanner`
- `SearchProvider`
- `PaperFetcher`
- `EvidenceStore`
- `ResearchSessionMemory`
- `SynthesisAgent`
- `CitationFormatter`

This keeps the current agent usable while making the research workflow easier to extend later.

## 3. Source Strategy

Use multiple sources, with different confidence levels.

### 3.1 Primary scholarly sources

Recommended first-tier sources:

- arXiv
- OpenAlex
- Crossref
- Semantic Scholar, if you later want richer citation graphs or recommendations

Why:

- arXiv gives strong coverage for preprints and recent research.
- OpenAlex is a broad open scholarly index.
- Crossref is useful for DOI and publication metadata normalization.

### 3.2 General web search

Use general web search for:

- conference pages
- lab pages
- survey blogs
- code repositories
- announcements of very recent work

For this layer, SerpApi is a valid choice.

## 4. SerpApi Decision

Yes, SerpApi can be used for this project.

It is especially useful when you want one tool to access broader search sources, including Google-style results and scholarly search surfaces. SerpApi's official docs list Google Search API and Google Scholar API, which makes it a practical bridge between general web search and literature discovery.

Important recommendation:

- Treat arXiv and other scholarly APIs as higher-confidence sources.
- Treat SerpApi results as discovery signals, not final truth.
- When SerpApi finds a paper, try to verify it against arXiv, Crossref, OpenAlex, or the publication site.

Do not use Google Custom Search JSON API as the primary new-project path.
Google's current docs say that API is closed to new customers and only existing customers have a migration window.

## 5. Confidence and Ranking

The agent should assign source confidence instead of trusting every result equally.

Suggested ranking rule:

- arXiv preprint: high confidence for recent technical content
- Crossref metadata: high confidence for DOI, venue, publication date
- OpenAlex: high confidence for graph-level scholarly metadata
- Publisher page / conference page: high confidence if it matches the paper metadata
- SerpApi general web result: medium confidence
- Blog / discussion / repo readme: low to medium confidence, depending on context

Suggested per-result fields:

- `source`
- `source_confidence`
- `title`
- `authors`
- `published_date`
- `year`
- `venue`
- `abstract`
- `url`
- `doi`
- `arxiv_id`
- `query`
- `retrieved_at`
- `evidence_snippet`
- `match_reason`

## 6. ReAct Workflow

Use a lightweight ReAct-style loop, but make the research phases explicit.

Recommended loop:

1. Interpret the user question
2. Build a search plan
3. Search scholarly sources
4. Search broader web sources if needed
5. Deduplicate and rank results
6. Fetch abstracts or page content
7. Extract evidence
8. Synthesize findings
9. Verify citations and answer

This should be implemented as a controlled loop rather than free-form prompting only.

Suggested agent states:

- `PLAN`
- `SEARCH`
- `FETCH`
- `READ`
- `SYNTHESIZE`
- `VERIFY`
- `ANSWER`

## 7. Memory Design

Memory is worth adding, but only after the retrieval pipeline is stable.

### 7.1 Short-term memory

Store per-session research context:

- user intent
- current topic
- search queries already tried
- retrieved papers
- failed searches
- selected evidence

### 7.2 Long-term memory

Store stable preferences:

- preferred disciplines
- preferred output format
- preferred sources
- excluded sources
- citation style

### 7.3 Cache memory

Use a cache to avoid repeated searches during the same session or between near-duplicate queries.

Recommended cache keys:

- normalized query
- source
- date range
- language

## 8. Skills

The `skills/` directory should be used for reusable research procedures, not for raw code logic.

Good skill examples:

- how to do a literature review
- how to search for recent papers in a domain
- how to summarize a paper
- how to produce a comparison table
- how to generate a reading list

Recommended skill file contract:

- `skill.md`
- optional `examples/`
- optional `config.json`

Suggested skill contents:

- purpose
- trigger conditions
- inputs
- outputs
- step-by-step procedure
- failure modes
- examples

## 9. MCP vs Native Tools

Use native tools first.

Recommended approach:

- Keep core retrieval as native Python tools in this repo.
- Use MCP later when you need many external systems or standardized connectors.

Good MCP candidates later:

- browser automation
- Zotero
- Notion
- file systems outside the repo
- remote PDF services
- vector databases

For the current stage, MCP is optional, not required.

## 10. Multi-Agent Readiness

Even if you start with one agent, define interfaces that can later be split.

Suggested future roles:

- Planner agent
- Retriever agent
- Reader agent
- Synthesizer agent
- Verifier agent

Suggested shared interfaces:

- `ResearchTask`
- `SearchResult`
- `PaperRecord`
- `EvidenceChunk`
- `ResearchReport`

Keep these as plain dataclasses or Pydantic models so they can be reused across single-agent and multi-agent setups.

## 11. Implementation Phases

### Phase 1: Source connectors

Implement:

- arXiv search
- Crossref metadata lookup
- OpenAlex search
- SerpApi web search

### Phase 2: Normalized evidence

Implement:

- common result schema
- confidence scoring
- deduplication
- citation normalization

### Phase 3: Research workflow

Implement:

- query planning
- iterative search
- evidence extraction
- synthesis prompt

### Phase 4: Memory and caching

Implement:

- session memory
- query cache
- preferred source profile

### Phase 5: Optional advanced features

Implement:

- PDF fetching and parsing
- DOI resolution
- reference expansion
- citation graph exploration
- multi-agent split
- MCP connectors

## 12. What Needs to Be Prepared

Please prepare the following before implementation:

- SerpApi account and API key
- arXiv usage confirmation
- OpenAlex API key if you want higher throughput than the free limit
- Crossref usage expectations
- Any preferred citation format
- A target output style for the research report

Optional but useful:

- Zotero library
- a list of trusted journals/conferences
- a list of ignored sources
- a list of target disciplines

## 13. Suggested Default Source Policy

Use this default policy if no user preference is given:

1. Search arXiv first for recent scholarly content.
2. Search OpenAlex and Crossref for metadata validation.
3. Search SerpApi for broader discovery and fresh web signals.
4. Prefer sources with direct scholarly metadata over secondary pages.
5. Cite every claim that depends on retrieved evidence.

## 14. Suggested Agent Instruction

The research agent should be instructed to behave like this:

> Search broadly, but rank scholarly sources above web search. Prefer arXiv for recent technical work. Use web search for discovery, verification, and context. Never present an unsupported claim as fact. When evidence is thin, say so explicitly. Always return a compact source list and a short explanation of why each source was selected.

## 15. Codebase Touchpoints

When you are ready to implement, the likely touchpoints in this repo are:

- `agent_framework/agent.py`
- `agent_framework/tools.py`
- `agent_framework/builtin_tools.py`
- `agent_framework/models/`
- a future `agent_framework/research/` package
- `skills/`
- `README.md`

## 16. Preferred Next Step

The best next step is to implement Phase 1 and Phase 2 first, then wire them into a dedicated `research` mode.
