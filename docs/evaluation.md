# Evaluation

The eval pipeline runs the same gold Q/A pairs through a **grounded** agent
(with retrieval tools) and an **ungrounded** agent (no tools), then asks a
judge LLM to score hallucination per atomic claim.

## Pipeline

```
eval/dataset.yaml (40 Q/A pairs)
   │
   ▼
┌──────────────────────────────────────────────┐
│ grounded agent (retrieval tools)             │
│ ungrounded agent (no tools)                  │
│   run in parallel (asyncio.gather)           │
└──────────────────────────────────────────────┘
   │
   ▼
results.jsonl (one line per case, per mode)
   │
   ▼
reports/eval_report.md (Markdown aggregate)
```

Each case yields:

- `grounded_answer` (string), `grounded_citations` (list of citation dicts)
- `grounded_hallucination` (atomic-claim breakdown)
- `ungrounded_answer`, `ungrounded_hallucination`

## Hallucination judge

The judge LLM is the same MiniMax-M3 chat model. For each answer it:

1. Decomposes the answer into atomic claims (one JSON array).
2. For each claim, asks the judge to label it `supported` /
   `contradicted` / `extra` against the gold answer.
3. Aggregates: `hallucination_rate = (contradicted + extra) / total_claims`.

## CLI

```bash
bfsi-rbi eval --limit 40 --concurrency 5
bfsi-rbi report reports/results.jsonl
```

## Report contents

`reports/eval_report.md` contains:

- Aggregate metrics (ungrounded vs grounded hallucination rate, grounding
  score, citation accuracy).
- By-topic breakdown.
- Per-case table.

## Performance budget

40 cases at `bfsi_eval_concurrency=5` should complete in **under 4
minutes** on a single host (dominated by chat-model latency). See
`docs/performance.md` for the benchmark suite.
