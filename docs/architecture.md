# Architecture

## Data flow

```
         RBI PDFs on rbi.org.in
                  │
                  ▼
        ┌─────────────────────┐
        │  rbi_scraper.py     │  httpx + BeautifulSoup
        │  download_pdf()     │
        └─────────────────────┘
                  │
                  ▼  data/raw/*.pdf
        ┌─────────────────────┐
        │  pdf.py             │  pypdf → vision fallback
        │  extract_pdf()      │  via LiteLLM → MiniMax-M3
        └─────────────────────┘
                  │
                  ▼  ExtractedDocument
        ┌─────────────────────┐
        │  pipeline.py        │  chunking + bulk index
        │  run_ingestion()    │
        └─────────────────────┘
                  │
                  ▼  Elasticsearch index
        ┌─────────────────────┐
        │  rbi-circulars      │  semantic_text + text
        │  + .elser-2-...     │  ELSER inference
        └─────────────────────┘
                  │
                  ▼  ES|QL tools
        ┌─────────────────────┐
        │  Agent Builder      │  hybrid_search, get_circular,
        │  (Kibana)           │  list_recent, compare_circulars
        └─────────────────────┘
                  │
                  ▼  MCP endpoint
        ┌─────────────────────┐
        │  Pydantic AI Agent  │  MiniMax-M3 via LiteLLM
        │  (Python)           │  output: RBIAnswer
        └─────────────────────┘
                  │
                  ▼  structured answer
        ┌─────────────────────┐
        │  Streamlit UI       │  side-by-side A/B
        │  / reports          │  Markdown
        └─────────────────────┘
```

## Key design choices

| Decision | Reason |
|---|---|
| Pydantic AI | Type-safe agents, native MCP, structured outputs |
| LiteLLM | Provider-agnostic; switch from MiniMax to OpenAI/Anthropic with one env change |
| MiniMax-M3 | Multimodal frontier model; supports both text and vision via same endpoint |
| Agent Builder | Native MCP server, ES|QL tools, Elastic hybrid search with RRF |
| Atomic-claim judge | Per-claim grading eliminates false positives from partial matches |
| `RBIAnswer` schema | Forces citations; hallucinations cannot render without source IDs |
| `ConcurrencyLimitedModel` | Bounded parallelism keeps ES free-tier rate limits in check |

## Index schema

```json
{
  "properties": {
    "circular_id": {"type": "keyword"},
    "title": {"type": "text"},
    "text": {"type": "text"},
    "semantic_text": {"type": "semantic_text", "inference_id": ".elser-2-elasticsearch"},
    "issue_date": {"type": "date"},
    "topic": {"type": "keyword"},
    "source_url": {"type": "keyword"},
    "page_count": {"type": "integer"},
    "extraction_method": {"type": "keyword"}
  }
}
```

## Tool specs

Four ES|QL tools deployed to Agent Builder:

| ID | ES|QL pattern | Purpose |
|---|---|---|
| `rbi.hybrid_search` | `FORK` (BM25) `(semantic)` `FUSE RRF` | Top hybrid hits |
| `rbi.get_circular` | `WHERE circular_id == ?id` | Full text |
| `rbi.list_recent` | `WHERE issue_date >= ?since` | Date-filtered |
| `rbi.compare_circulars` | `WHERE circular_id IN (?a, ?b)` | Side-by-side |
