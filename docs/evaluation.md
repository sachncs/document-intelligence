# Evaluation

## Methodology

The eval suite runs each question through **two** agents built from the same
factory:

| Run | Configuration |
|---|---|
| **Grounded** | `MCP(url=ELASTIC_MCP_URL)` enabled. Agent can call the four `rbi.*` tools. |
| **Ungrounded** | No capabilities. Same model, same system prompt, no tools. |

Both runs use:
- MiniMax-M3 at `temperature=0.0` for determinism
- Same `RBIAnswer` output schema
- Same judge LLM for scoring

## The judge

`AtomicClaimHallucination` (in `bfsi_rbi.eval.hallucination`) is a custom
`pydantic-evals` evaluator:

1. **Decompose** the answer into atomic claims — single, falsifiable
   statements.
2. **Judge** each claim against the gold answer:
   - `supported` — explicitly in gold
   - `contradicted` — directly contradicts gold
   - `extra` — plausible but not in gold (counts as hallucination)
3. **Aggregate**:
   ```
   hallucination_rate = (contradicted + extra) / total_claims
   grounding_score    = supported / total_claims
   ```

## Metrics

| Metric | Definition |
|---|---|
| `hallucination_rate` | (contradicted + extra) / total_claims |
| `grounding_score` | supported / total_claims |
| `citation_accuracy` | fraction of cases where the agent cited ≥1 source |
| `relative_reduction` | (ungrounded_hallu - grounded_hallu) / ungrounded_hallu |

## Dataset

40 hand-curated Q/A pairs in `eval/dataset.yaml`:

| Topic | Count |
|---|---|
| factual | 14 |
| procedural | 8 |
| cross_circular | 8 |
| date_bounded | 6 |
| trap | 4 |

Every gold answer is sourced from an official RBI document (Master
Direction, FAQ, or public circular reference).

## Running

```bash
bfsi-rbi eval --limit 40
bfsi-rbi report reports/results.jsonl
```

Output:
- `reports/results.jsonl` — raw per-case results
- `reports/eval_report.md` — aggregate Markdown report
