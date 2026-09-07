# Retrieval

::: docendo.retrieval.store
    options:
      show_root_heading: true
      members:
        - Store
        - parse_blob
        - fts_escape
        - from_row
        - SCHEMA_VERSION

::: docendo.retrieval.types
    options:
      show_root_heading: true
      members:
        - Query
        - Lookup
        - Recent
        - Pair
        - Hit
        - Listing
        - Document
        - PairResult
        - Results
        - Retriever

::: docendo.retrieval.chunker
    options:
      show_root_heading: true
      members:
        - chunk
        - encode
        - tokenizer
        - reset

::: docendo.retrieval.embedder
    options:
      show_root_heading: true
      members:
        - aembed
        - cosine
        - reset

::: docendo.retrieval.record
    options:
      show_root_heading: true
      members:
        - ChunkRecord

::: docendo.retrieval.tools
    options:
      show_root_heading: true
      members:
        - search
        - fetch
        - recent
        - compare
