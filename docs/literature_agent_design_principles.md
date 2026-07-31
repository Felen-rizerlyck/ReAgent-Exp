# Literature Research Agent Design Principles

This document defines the design principles and implementation constraints for the literature research agent before coding begins.

## 1. Design Goals

The agent should be optimized for:

- High-quality literature discovery
- Evidence-backed synthesis
- Transparent source attribution
- Extensibility to more sources and more agents
- Low-friction maintenance over time

The system should not be optimized for only one-shot chat answers. It should behave like a research workflow engine with LLM support.

## 2. Core Principles

### 2.1 Separate reasoning from retrieval

The model should not be responsible for both search and truth. Search must be done by tools or providers, and the model should reason over retrieved evidence.

Implication:

- Do not ask the model to invent citations.
- Do not let the model summarize sources that were never fetched.
- Do not mix raw search output and final synthesis in the same structure.

### 2.2 Separate evidence from conclusions

All claims in the final response should be traceable to evidence objects.

Implication:

- Store evidence chunks independently from the answer.
- Keep a link between each claim and the source that supports it.
- When evidence is weak, say so explicitly.

### 2.3 Prefer composable modules

Each part of the system should have one responsibility.

Recommended modules:

- Query planning
- Source retrieval
- Evidence normalization
- Reading and summarization
- Citation formatting
- Memory and cache
- Task orchestration

### 2.4 Keep source adapters replaceable

Every source connector should be swappable without changing the rest of the system.

Implication:

- arXiv, OpenAlex, Crossref, SerpApi, and later sources should implement the same adapter shape.
- The research workflow should consume normalized records, not source-specific payloads.

### 2.5 Preserve future multi-agent compatibility

Even if the first version is single-agent, the interfaces must allow later splitting into planner, retriever, reader, and verifier roles.

Implication:

- Use shared typed data models.
- Avoid putting orchestration logic directly into tool handlers.
- Keep task state serializable.

## 3. Proposed System Layers

### 3.1 Interface layer

The interface layer receives the user request, decides whether it is a literature task, and routes it to the research workflow.

Responsibilities:

- Intent detection
- Task type routing
- Session selection
- Top-level output formatting

### 3.2 Planning layer

The planning layer converts a user question into a research plan.

Responsibilities:

- Identify the topic
- Detect date sensitivity
- Decide source priority
- Generate search queries
- Decide whether the task needs deep reading or broad scanning

### 3.3 Retrieval layer

The retrieval layer queries external sources.

Responsibilities:

- Search scholarly databases
- Search the general web when needed
- Fetch abstracts, metadata, and optionally PDFs
- Normalize results into a shared schema

### 3.4 Evidence layer

The evidence layer stores and ranks retrieved content.

Responsibilities:

- Deduplication
- Confidence scoring
- Relevance scoring
- Evidence chunking
- Citation linking

### 3.5 Synthesis layer

The synthesis layer produces the final summary.

Responsibilities:

- Compare sources
- Identify themes
- Extract representative papers
- Summarize state of the field
- Highlight gaps and future directions

### 3.6 Verification layer

The verification layer checks whether the final answer is grounded.

Responsibilities:

- Citation completeness check
- Claim-to-evidence alignment
- Source quality review
- Missing-evidence detection

## 4. Required Data Models

Use explicit data models instead of ad-hoc dictionaries wherever possible.

### 4.1 `ResearchTask`

Represents one user literature request.

Suggested fields:

- `task_id`
- `user_query`
- `topic`
- `scope`
- `time_range`
- `source_preferences`
- `output_style`
- `status`

### 4.2 `SearchQuery`

Represents one query sent to a source.

Suggested fields:

- `query_text`
- `source`
- `language`
- `filters`
- `priority`
- `reason`

### 4.3 `SearchResult`

Represents one raw result from a source.

Suggested fields:

- `source`
- `source_id`
- `title`
- `authors`
- `published_date`
- `venue`
- `abstract`
- `url`
- `doi`
- `arxiv_id`
- `raw_payload`

### 4.4 `EvidenceItem`

Represents a normalized and ranked evidence object.

Suggested fields:

- `evidence_id`
- `source`
- `title`
- `summary`
- `supporting_snippet`
- `confidence`
- `relevance`
- `retrieved_at`
- `citations`

### 4.5 `ResearchReport`

Represents the final answer.

Suggested fields:

- `executive_summary`
- `research_questions`
- `key_findings`
- `important_papers`
- `open_problems`
- `method_notes`
- `limitations`
- `sources`

## 5. Source Policy

### 5.1 Primary source ranking

Default ranking policy:

1. arXiv
2. OpenAlex
3. Crossref
4. Publisher or conference page
5. SerpApi-discovered web pages
6. Blogs, labs, repositories, and secondary pages

### 5.2 Source confidence

Each source should have a confidence profile.

Suggested weights:

- arXiv: high
- OpenAlex: high
- Crossref: high
- Publisher page: high if metadata matches
- SerpApi search result: medium
- Blog or repo page: low to medium

### 5.3 Verification rule

If a result comes from a lower-confidence source, try to verify it using a higher-confidence source before presenting it as a key paper.

## 6. Search Planning Rules

The planner should generate different strategies based on the task type.

### 6.1 Topic discovery

If the user asks about "current hot topics" or "latest directions":

- Search recent arXiv preprints first
- Search broad web sources for emerging signals
- Search OpenAlex for related clusters and citations

### 6.2 Paper comparison

If the user asks to compare methods:

- Search representative papers
- Fetch abstracts or full text if available
- Compare dataset, method, evaluation, and conclusions

### 6.3 Survey generation

If the user asks for a literature review or survey:

- Expand from the core topic to adjacent subtopics
- Collect representative papers from different years
- Include seminal work and recent work

### 6.4 Very recent trend detection

If the user asks about very recent research:

- Increase weight for arXiv
- Include conference pages and lab pages
- Treat general web results as discovery leads only

## 7. ReAct and Control Loop Design

Use a bounded ReAct loop.

Recommended loop:

1. Plan
2. Search
3. Inspect results
4. Fetch content
5. Read evidence
6. Decide if more search is needed
7. Synthesize
8. Verify
9. Answer

Important constraints:

- The loop must have a step limit.
- Every tool call should be recorded.
- The model should be able to stop early if confidence is sufficient.
- The system should support iterative refinement, not infinite searching.

## 8. Memory Strategy

Memory should be added in layers.

### 8.1 Session memory

Stores the current research task.

Use for:

- already-searched queries
- retrieved papers
- selected evidence
- user feedback

### 8.2 Project memory

Stores the current long-lived research project.

Use for:

- topic scope
- target output format
- source preferences
- previous conclusions

### 8.3 Global preference memory

Stores user preferences across tasks.

Use for:

- preferred citation style
- preferred depth
- preferred disciplines
- preferred trust sources

### 8.4 Cache

Use cache for:

- repeated searches
- fetched abstracts
- normalized metadata
- PDF text extraction results

## 9. Skill Strategy

Skills should encode procedures, not state.

Recommended skill types:

- literature search skill
- paper reading skill
- survey writing skill
- comparison table skill
- citation cleanup skill

Skill contents should include:

- purpose
- trigger conditions
- expected inputs
- expected outputs
- step-by-step procedure
- caveats
- examples

Skills should remain small and focused. They should not contain source adapters or data storage logic.

## 10. Tooling Strategy

### 10.1 Native tools first

Implement source connectors as native Python tools before introducing MCP.

### 10.2 MCP later

Add MCP only if the project starts depending on many external systems or standardized connectors.

### 10.3 Tool design rules

- Keep tool parameters explicit
- Return structured output
- Avoid large untyped blobs when possible
- Do not let tools hide critical errors

## 11. Extension Readiness

The system should already reserve space for future features.

Recommended reserved extensions:

- multi-agent orchestration
- browser automation
- PDF ingestion
- citation graph traversal
- vector search
- long-term memory store
- session export/import

## 12. Safety and Quality Constraints

The research agent must obey the following constraints:

- Never fabricate a citation
- Never present an unverified claim as a fact
- Always distinguish preprints from peer-reviewed work
- Always keep source provenance
- Always surface uncertainty when evidence is weak
- Prefer breadth first, then depth
- Avoid endless tool loops

## 13. Suggested Repository Boundaries

When implementation starts, prefer these package boundaries:

- `agent_framework/research/` for research workflow logic
- `agent_framework/sources/` for external source adapters
- `agent_framework/memory/` for session and long-term memory
- `agent_framework/schema/` for shared data models
- `skills/` for procedural skills
- `docs/` for design and operating guidance

## 14. Implementation Order

Recommended order:

1. Define data models
2. Define source adapter interface
3. Implement arXiv and OpenAlex connectors
4. Add search planning
5. Add evidence normalization
6. Add synthesis and report formatting
7. Add session memory and caching
8. Add verification
9. Add optional SerpApi and broader web search
10. Add multi-agent split if needed

## 15. Final Design Rule

If a future change makes the system harder to test, harder to explain, or harder to verify, prefer a simpler design even if it is less ambitious.

