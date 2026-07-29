# Quickstart

## Full pipeline

```bash
# 1. Fetch RBI documents
bfsi-rbi fetch

# 2. Ingest into Elasticsearch (with vision fallback for scanned PDFs)
bfsi-rbi ingest

# 3. Set up ELSER inference endpoint
bfsi-rbi setup-inference

# 4. Deploy Agent Builder tools
bfsi-rbi deploy-tools

# 5. Deploy the agent
bfsi-rbi deploy-agent

# 6. Smoke-test the MCP connection
bfsi-rbi smoke-mcp

# 7. Run the evaluation
bfsi-rbi eval

# 8. Generate the Markdown report
bfsi-rbi report reports/results.jsonl

# 9. Launch the Streamlit demo
bfsi-rbi demo
```

## Library use

```python
from bfsi_rbi import get_settings
from bfsi_rbi.agent import make_agent
from bfsi_rbi.models import RBIAnswer

settings = get_settings()
agent = make_agent(grounded=True, settings=settings)

result = await agent.run("What is the LCR for NBFCs?")
answer: RBIAnswer = result.output
print(answer.answer)
for c in answer.citations:
    print(f"  [{c.circular_id}] {c.circular_title}: {c.source_url}")
```
