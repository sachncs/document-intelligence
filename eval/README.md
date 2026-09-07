# Evaluation Dataset

40 hand-curated Q/A pairs sourced from RBI Master Directions, official
FAQs, and public RBI circular references.

## Topic distribution

| Topic | Count |
|---|---|
| factual | 14 |
| procedural | 8 |
| cross_circular | 8 |
| date_bounded | 6 |
| trap | 4 |
| **Total** | **40** |

## Format

YAML list of objects with these fields:

```yaml
- name: <unique-id>
  inputs: <question text>
  expected_output: <gold answer text>
  metadata:
    topic: factual | procedural | cross_circular | date_bounded | trap
    domain: <e.g. kyc, npa, monetary_policy>
    year: <optional>
    source_faq_url: <RBI FAQ URL where applicable>
    source_circular_ids: [<RBI circular IDs>]
    expected_refusal: <true for trap questions>
```

## Adding new cases

1. Append a new entry to `dataset.yaml`.
2. Use a unique `name` (lowercase, snake_case).
3. Source every gold answer from an official RBI document.
4. For trap questions, set `expected_refusal: true` and word the gold
   answer as a refusal.
