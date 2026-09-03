# Research Result Export

Each `research_literature` call creates a new topic directory under the project root's `research_results/` directory.

```text
research_results/
  topic__20260828_153012_123456/
    report.md
    report.json
    references.md
    references.json
    metadata.json
```

The current phase creates reports and reference links only. It does not download paper files.

- `report.md`: readable Markdown report
- `report.json`: structured research report
- `references.md`: reference list and URLs
- `references.json`: metadata for the top ranked results
- `metadata.json`: query, sources, result counts, and export information

An export failure does not discard completed search results. The returned `artifacts` field then contains `status=error` and the failure reason.
