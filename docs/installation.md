# Installation

## Requirements

- Python 3.11 or newer
- [Elasticsearch Serverless](https://cloud.elastic.co/registration) (free
  trial) or Elastic Stack 9.3+
- [MiniMax](https://platform.minimax.io) API access
- `pip` or `uv`

## Install

```bash
pip install -e ".[dev]"
```

Or with `uv`:

```bash
uv pip install -e ".[dev]"
```

## Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required:

```bash
MINIMAX_API_KEY=sk-...
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_MODEL=MiniMax-M3

ELASTIC_URL=https://your-deployment.es.us-east-1.aws.elastic.cloud
ELASTIC_API_KEY=...
ELASTIC_MCP_URL=https://your-deployment.es.us-east-1.aws.elastic.cloud/api/agent_builder/mcp
```

Install pre-commit hooks:

```bash
pre-commit install
```

## Verify

```bash
bfsi-rbi --help
pytest tests/unit
```
