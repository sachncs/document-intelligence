# Phase 3 / 4 / 5 — Atomic TODO

> Blocked on creds in `.env` (`MINIMAX_*`, `ELASTIC_*`).
> Each item is one verifiable action. No broad strokes.

---

## Phase 3 — Real network (creds in .env)

### 3.1 Validate credentials

- [ ] **Resolve ELASTIC_URL host** — `getent hosts $(echo "$ELASTIC_URL" | sed -E 's|https?://||; s|/.*||')` → IP returned
- [ ] **Verify ELASTIC_API_KEY** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/_cluster/health"` → `{"status":"green"|"yellow", ...}`
- [ ] **Verify MINIMAX_API_KEY** — `curl -sf -H "Authorization: Bearer $MINIMAX_API_KEY" "$MINIMAX_BASE_URL/models"` → JSON list (or 401 → fix key)
- [ ] **Verify ELASTIC_MCP_URL** — `bfsi-rbi smoke-mcp` → `{"ok": true, "server": {...}}`

### 3.2 Fetch RBI PDFs

- [ ] **Smoke fetch (5 docs)** — `bfsi-rbi fetch --max 5` → exits 0, prints 5 paths
- [ ] **Count PDFs after smoke** — `ls data/raw/*.pdf | wc -l` → `5`
- [ ] **Verify PDFs non-empty** — `find data/raw -name '*.pdf' -size +0c | wc -l` → `5`
- [ ] **Full fetch** — `bfsi-rbi fetch` → exits 0
- [ ] **Verify corpus size** — `ls data/raw/*.pdf | wc -l` → `≥100`
- [ ] **Verify no zero-byte files** — `find data/raw -name '*.pdf' -size 0c | wc -l` → `0`

### 3.3 ELSER setup

- [ ] **Create ELSER endpoint** — `bfsi-rbi setup-inference` → `OK`
- [ ] **Verify ELSER exists** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/_inference/.elser-2-elasticsearch"` → 200
- [ ] **Wait for model deploy** — `sleep 30` (ELSER model alloc needs time)
- [ ] **Check model allocated** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/_ml/trained_models/.elser_model_2/_stats"` → `"state":"started"`

### 3.4 Ingest

- [ ] **Smoke ingest (5 docs)** — `bfsi-rbi ingest --max 5` → JSON summary, no errors
- [ ] **Verify chunk count** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/rbi-circulars/_count"` → `{"count": N, "_shards":...}` with N ≥ 5
- [ ] **Full ingest** — `bfsi-rbi ingest` → exits 0
- [ ] **Verify full chunk count** — same `_count` call → N ≥ 200
- [ ] **Verify semantic_text indexed** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/rbi-circulars/_search?size=1&pretty"` → first hit has `semantic_text` field populated

### 3.5 Deploy Agent Builder tools

- [ ] **Deploy tools** — `bfsi-rbi deploy-tools` → 4 lines of `rbi.*: ok`
- [ ] **Verify tools** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/api/agent_builder/tools"` → results array with 4 items, IDs: `rbi.hybrid_search`, `rbi.get_circular`, `rbi.list_recent`, `rbi.compare_circulars`

### 3.6 Deploy Agent Builder agent

- [ ] **Deploy agent** — `bfsi-rbi deploy-agent` → `rbi-policy-analyst: ok`
- [ ] **Verify agent** — `curl -sf -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/api/agent_builder/agents"` → results contain id `rbi-policy-analyst`
- [ ] **Verify agent has 4 tool_ids** — inspect agent JSON, `configuration.tools[0].tool_ids` has 4 entries

---

## Phase 4 — Real eval

### 4.1 Eval smoke (single case)

- [ ] **Run 1 case** — `bfsi-rbi eval --limit 1` → exits 0
- [ ] **Verify JSONL has 1 line** — `wc -l reports/results.jsonl` → `1`
- [ ] **Inspect structure** — `head -1 reports/results.jsonl | python3 -m json.tool` → contains `case_name`, `grounded_answer`, `grounded_hallucination`, `ungrounded_answer`, `ungrounded_hallucination`

### 4.2 Eval small batch

- [ ] **Run 5 cases** — `bfsi-rbi eval --limit 5`
- [ ] **Verify 5 lines** — `wc -l reports/results.jsonl` → `5`
- [ ] **Verify all have hallucination data** — `jq -r 'select(.grounded_hallucination == null) | .case_name' reports/results.jsonl` → empty output

### 4.3 Eval full

- [ ] **Run 40 cases** — `bfsi-rbi eval --limit 40`
- [ ] **Verify 40 lines** — `wc -l reports/results.jsonl` → `40`
- [ ] **Verify rates in [0,1]** — `jq -r '.ungrounded_hallucination.hallucination_rate' reports/results.jsonl | sort -n | head -1` → `0.0`; tail → `≤ 1.0`
- [ ] **Verify both rates finite** — `jq -r '.grounded_hallucination.hallucination_rate, .ungrounded_hallucination.hallucination_rate' reports/results.jsonl | grep -c 'null'` → `0`

### 4.4 Report

- [ ] **Generate report** — `bfsi-rbi report reports/results.jsonl`
- [ ] **Verify file exists** — `ls reports/eval_report.md` → path returned
- [ ] **Verify aggregate table** — `grep -q "Aggregate metrics" reports/eval_report.md`
- [ ] **Verify per-case table** — `grep -q "Per-case" reports/eval_report.md`
- [ ] **Verify by-topic table** — `grep -q "By topic" reports/eval_report.md`
- [ ] **Verify ground rate** — `grep -q "Hallucination rate" reports/eval_report.md`
- [ ] **Read aggregate numbers** — note `grounded_hallucination_rate`, `ungrounded_hallucination_rate`, `relative_reduction` for README update

### 4.5 Integration tests

- [ ] **Run integration tests** — `pytest tests/integration -v`
- [ ] **Verify 0 failed** — exit 0, `passed` count ≥ 7
- [ ] **Verify coverage** — `pytest --cov=bfsi_rbi --cov-report=term-missing` → lines covered

---

## Phase 5 — Demo + release

### 5.1 Launch demo

- [ ] **Verify streamlit installed** — `python3 -c "import streamlit; print(streamlit.__version__)"` → version string
- [ ] **Start demo in background** — `bfsi-rbi demo --port 8501 &` (record PID)
- [ ] **Wait for boot** — `sleep 8`
- [ ] **Verify HTTP 200** — `curl -sI http://localhost:8501 | head -1` → `HTTP/1.1 200 OK`
- [ ] **Verify health endpoint** — `curl -sf http://localhost:8501/_stcore/health` → `ok`
- [ ] **Stop demo** — `kill <PID>` (or `pkill -f "streamlit run"`)

### 5.2 Update README with real numbers

- [ ] **Open README** — `eval "$(cat reports/eval_report.md | grep -E '^\|' | grep -A1 'Hallucination' | head -1)"` to extract numbers
- [ ] **Replace placeholder row** in README "Evaluation" table with extracted numbers
- [ ] **Verify replaced** — `grep -q "Hallucination rate" README.md` and `grep -qE '[0-9]+\.[0-9]+%' README.md`
- [ ] **Stage README** — `git add README.md`

### 5.3 Release commit

- [ ] **Verify clean** — `git status` → no untracked non-data files
- [ ] **Commit results** — `git commit -m "docs: populate README with eval numbers"`
- [ ] **Verify commit** — `git log --oneline -3`

### 5.4 Tag v0.1.0

- [ ] **Create annotated tag** — `git tag -a v0.1.0 -m "v0.1.0: first end-to-end eval (grounded X% vs ungrounded Y%)"`
- [ ] **Verify tag** — `git tag -l` → contains `v0.1.0`
- [ ] **Show tag details** — `git show v0.1.0 --stat | head -20`

### 5.5 Final verification

- [ ] **Run full test suite** — `pytest tests -v` → all unit pass, integration pass
- [ ] **Re-run lint** — `ruff check src tests` → clean
- [ ] **Re-run typecheck** — `mypy src/bfsi_rbi` → clean
- [ ] **Build wheel** — `python3 -m build` → produces `dist/bfsi_rbi-0.1.0-py3-none-any.whl`
- [ ] **Final log** — `git log --oneline --decorate -10` → shows v0.1.0 tag

---

## Rollback recipes

- [ ] **Drop index** — `curl -X DELETE -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/rbi-circulars"`
- [ ] **Drop tools** — `for id in rbi.hybrid_search rbi.get_circular rbi.list_recent rbi.compare_circulars; do curl -X DELETE -H "Authorization: ApiKey $ELASTIC_API_KEY" -H "kbn-xsrf: true" "$ELASTIC_URL/api/agent_builder/tools/$id"; done`
- [ ] **Drop agent** — `curl -X DELETE -H "Authorization: ApiKey $ELASTIC_API_KEY" -H "kbn-xsrf: true" "$ELASTIC_URL/api/agent_builder/agents/rbi-policy-analyst"`
- [ ] **Drop ELSER** — `curl -X DELETE -H "Authorization: ApiKey $ELASTIC_API_KEY" "$ELASTIC_URL/_inference/.elser-2-elasticsearch"`
- [ ] **Delete tag** — `git tag -d v0.1.0`