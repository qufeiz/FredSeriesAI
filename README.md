# My LangGraph App

> A LangGraph-based financial copilot that combines AWS Bedrock conversations with live FRED and FOMC data tools.

[Open in LangGraph Studio](https://langgraph-studio.vercel.app/templates/open?githubUrl=https://github.com/langchain-ai/retrieval-agent-template)
· [Hosted graph](https://my-langgraph-app.fly.dev) · [Studio session on Smith](https://smith.langchain.com/studio/?baseUrl=https://my-langgraph-app.fly.dev)

![Graph view in LangGraph studio UI](./static/studio_ui.png)

## TL;DR
- Conversational loop runs on LangGraph with a single `StateGraph` (see `src/retrieval_graph/graph.py`), powered by `ChatBedrockConverse` (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`).
- Built-in tools cover FRED charts, recent datapoints, release metadata, FRASER/Postgres searches, and a live "latest FOMC decision" card.
- Document retrieval is wired to `retrieve_documents` and `retrieval.make_retriever`, but the focus of this README is the Bedrock + tooling experience—hook your own vector store when you are ready.
- LangSmith tracing is enabled so every run is observable; attachments (chart images) and structured `series_data` ride outside the prompt for richer UX.
- Ships with a Fly.io manifest (`fly.toml`) so you can deploy the same runtime that Studio uses.
- Public App Runner endpoint (current): https://vpinmbqrjp.us-east-1.awsapprunner.com

## Repository layout
| Path | Purpose |
| --- | --- |
| `src/retrieval_graph/graph.py` | Conversation loop, Bedrock client construction, tool registry, routing between `agent` and `tools` nodes. |
| `src/retrieval_graph/state.py` | Strongly-typed LangGraph state, reducers for attachments, structured series data, and citations. |
| `src/retrieval_graph/fred_tool.py` | Handles FRED charts, datapoints, correlation, and release metadata via the official API. |
| `src/retrieval_graph/fraser_tool.py` | Connects to your FRASER-backed Postgres instance for FOMC title search. |
| `src/retrieval_graph/services.py` | Builds the "latest FOMC decision" snapshot from Postgres data. |
| `src/retrieval_graph/index_graph.py` | (Optional) single-node index flow for uploading private documents. Left intact but not needed to run the chat bot. |
| `langgraph.json` | Declares the deployable graphs for the LangGraph CLI (`indexer` and `retrieval_graph`). |
| `pyproject.toml` | Python dependencies; install the project in editable mode for development. |

## Prerequisites
- Python 3.9+ and a modern virtual environment tool (e.g., `uv`, `pip`, or `conda`).
- AWS account with Bedrock access to Anthropic Claude models and a configured profile (the code references `AWSAdministratorAccess-112393354239`—change it or expose the same profile on your machine).
- FRED API key for charts/data (`FRED_API_KEY`).
- Network access + credentials for the FRASER/Postgres databases that hold FOMC items and meeting decisions.
- Optional but recommended: LangSmith account for tracing (`LANGSMITH_API_KEY`).

## Quick start
### 1. Clone & install
```bash
cd /path/to/projects
git clone https://github.com/langchain-ai/retrieval-agent-template my-langgraph-app
cd my-langgraph-app
python -m venv .venv && source .venv/bin/activate
pip install -e .
```
(Use `uv pip install -e .` or your preferred toolchain if you already have one.)

### 2. Configure environment
```bash
cp .env.example .env
```
Fill in the values you actually use today:

| Variable | Why it matters |
| --- | --- |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | Enables tracing + dataset logging in LangSmith; disable or leave blank if you prefer local-only runs. |
| `AWS_PROFILE`, `AWS_REGION` | Profile/region with Bedrock access. `graph.py` reads `AWS_PROFILE` directly (falling back to the default boto3 credential chain if unset). |
| `FRED_API_KEY` | Needed for every tool implemented in `fred_tool.py` (charts, datapoints, metadata, correlation). |
| `FRED_CHART_WIDTH`, `FRED_CHART_HEIGHT` (optional) | Override the PNG dimensions generated via `fredgraph.png`. |
| `PG_HOST`, `PG_PORT`, `PG_NAME`, `PG_USER`, `PG_PASS` | Required by `fraser_tool.py` and `services.py` to talk to FRASER/FOMC tables. |

> `FRASER_API_KEY`, OpenSearch, or ingestion-specific variables from the original template are no longer needed unless you decide to revive those scripts.

### 3. Launch LangGraph Dev or Studio bridge
The CLI reads `langgraph.json` to learn about available graphs.
```bash
langgraph dev --allow-blocking
```
This exposes the graphs locally (default `http://127.0.0.1:8123`). Open LangGraph Studio and point it at your dev server, or paste the URL into the hosted Studio link in the hero section to talk to your local run.

## FastAPI bridge
Prefer a REST-style entry point? Launch the bundled FastAPI server:
```bash
uvicorn src.api_server:app --reload
```
- `POST /ask` accepts `{"text": ..., "conversation": [...]}`. Each request resets `tool_call_count` to `0`, so every user turn gets a fresh tool budget.
- Responses include the assistant text plus any `attachments`, `series_data`, `sources`, and the final `tool_call_count`.


### Manual API tests
Once the server is running, try a few `curl` calls:
```bash
# Latest FOMC decision (services.py)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{ "text": "Show me the latest FOMC decision", "conversation": [] }'

# Follow-up question with prior context (conversation replay + tool reset)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
        "text": "What about unemployment now?",
        "conversation": [
          { "role": "user", "content": "Compare CPI and unemployment trends." },
          { "role": "assistant", "content": "Here is the CPI info…" }
        ]
      }'

# FRASER title lookup (Postgres connectivity)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{ "text": "Find the January 2010 FOMC minutes.", "conversation": [] }'
```
Inspect the responses to verify attachments, series data, sources, and tool counts are present end-to-end.

### Response schema
Each `/ask` response returns:
```json
{
  "response": "<assistant markdown/text>",
  "attachments": [
    {
      "type": "image",
      "source": "data:image/png;base64,...",
      "title": "CPI chart",
      "series_id": "CPIAUCSL",
      "chart_url": "https://fred.stlouisfed.org/graph/fredgraph.png?id=CPIAUCSL"
    }
  ],
  "series_data": [
    {
      "series_id": "UNRATE",
      "title": "Unemployment Rate",
      "units": "Percent",
      "frequency": "Monthly",
      "notes": "...",
      "points": [
        { "date": "2025-01-01", "value": 4.0 },
        { "date": "2025-02-01", "value": 4.1 }
      ]
    }
  ],
  "sources": [
    {
      "tool": "fred_recent_data",
      "series_id": "UNRATE",
      "series_data": [ { "series_id": "UNRATE", "points": [...] } ]
    }
  ],
  "tool_call_count": 2
}
```
- `attachments`, `series_data`, and `sources` are optional arrays; omit them when empty.
- `tool_call_count` is the number of tools the agent used during that turn.
- Render `response` as markdown, display attachments/structured data inline, and use `sources` as lightweight citations in your frontend.

## Architecture
### Conversation loop
`graph.py` defines a `StateGraph` with two nodes:
- `agent`: builds a prompt from `Configuration.response_system_prompt`, injects retrieved docs + timestamps, and calls Claude Sonnet 4.5 on Bedrock. Tools are bound via the native Bedrock function-calling API exposed through `ChatBedrockConverse`.
- `tools`: executes every tool call emitted by the model, tracks attachment payloads, and increments `tool_call_count` to guard against loops (max 20 invocations per turn).

Routing is simple: start → `agent` → optional `tools` → back to `agent` until no more tool calls are requested.

### Tool catalog (what is actually used)
| Tool name | Description | Source |
| --- | --- | --- |
| `retrieve_documents` | Optional call into your chosen retriever (Pinecone by default). Configure later—this README focuses on the live data tools. | `retrieval.make_retriever` |
| `fred_chart` | Pulls a FRED-rendered PNG, base64 encodes it, and returns it as an attachment so clients can render the chart inline. | `fred_tool.fetch_chart` |
| `fred_recent_data` | Returns structured `series_data` (metadata + recent points) for downstream reasoning. | `fred_tool.fetch_recent_data` |
| `fred_series_release_schedule` | Maps a series to its release and shares upcoming publication dates. | `fred_tool.fetch_series_release_schedule` |
| `fred_release_structure` | Returns the tables + metadata for a given release name (e.g., "H.4.1"). | `fred_tool.fetch_release_structure_by_name` |
| `fred_search_series` | Text search across the FRED catalog. | `fred_tool.search_series` |
| `fred_series_correlation` | Compares YoY growth across two series and reports the strongest lead/lag window. | `fred_tool.analyze_series_correlation` |
| `fraser_search_fomc_titles` | Fuzzy-search FOMC meeting documents from FRASER/Postgres. | `fraser_tool.search_fomc_titles` |
| `fomc_latest_decision` | Builds an easy-to-read card for the latest (and previous) meeting from the Postgres table defined in `services.py`. | `services.get_latest_payload` |

### Attachments, `series_data`, and sources
Attachments (chart images) and structured datapoints never enter the LLM prompt—they are returned alongside text so your UI can render them without additional work. `state.Series_data` accumulates JSON blocks from FRED data tools, while `sources` captures lightweight records about each tool call (IDs, query text, release info). If you log runs to LangSmith you can inspect these fields under the run metadata to debug conversations.

### Observability
Set `LANGSMITH_API_KEY` and (optionally) `LANGSMITH_PROJECT` to stream every run into LangSmith. `graph.py` prints the API key and project on startup so you know tracing is working. You can still disable tracing entirely for offline experimentation.

<!-- ## Configuration reference
Beyond `.env`, LangGraph lets you pass configuration via `--config` or Studio. Useful keys:

| Config key | Default | Purpose |
| --- | --- | --- |
| `configurable.user_id` | `<required>` | Filters document retrieval and tags stored docs. Required even if you are only using FRED/FOMC tools. |
| `configurable.embedding_model` | `openai/text-embedding-3-small` | Only used once you configure document ingestion. |
| `configurable.retriever_provider` | `pinecone` | Placeholder; swap to whatever vector store you wire up later. |
| `configurable.response_system_prompt` | See `prompts.py` | Governs assistant tone + behavior. |
| `configurable.response_model` | `openai/gpt-4.1` | Template default; the runtime actually pins Bedrock Claude via code—update `graph.py` if you want to make this configurable again. | -->

## Development workflow
- `make test` (or `pytest`) exercises the unit tests under `tests/`.
- `make lint` runs Ruff format + lint plus strict mypy. Use `make format` to apply Ruff's formatter/fixes.
- Use `langgraph dev --allow-blocking --watch` (from the CLI) to reload graphs as you edit Python files.
- When editing prompts or tools, remember that attachments or structured state must remain JSON-serializable.

## Deployment notes
- `fly.toml` contains the production config that backs `https://my-langgraph-app.fly.dev`. Run `fly deploy` after logging in with `fly auth login` to ship updates.
- Provide the same `.env` values (or Fly secrets) in production; at a minimum you need the AWS + FRED + Postgres variables described earlier.
- LangGraph Cloud / Smith Studio can target either your Fly deployment or a local `langgraph dev --allow-blocking` session—no code changes required.

### Terraform (App Runner + ECR)
- Set `AWS_PROFILE`/`AWS_REGION`, copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, and fill in real secrets (kept out of git).
<!-- - If you already created the service by hand, import the live resources before your first apply:
  - `terraform import aws_ecr_repository.backend arn:aws:ecr:us-east-1:<acct>:repository/fredgpt-backend`
  - `terraform import aws_iam_role.apprunner_ecr AppRunnerECRAccessRole`
  - `terraform import aws_iam_role.apprunner_instance AppRunner-FredGPT-InstanceRole`
  - `terraform import aws_apprunner_service.backend arn:aws:apprunner:us-east-1:<acct>:service/fredgpt-backend/<service-id>` -->
- Fresh deploy: `cd terraform && terraform init && terraform apply`. Secrets are stored in SSM and pulled into App Runner via `runtime_environment_secrets`; Terraform state never contains secret values.

## Troubleshooting
- **Bedrock auth failures**: ensure `AWS_PROFILE` points to a local profile with Bedrock access (or unset it so boto3 falls back to your default credentials). A quick `aws sts get-caller-identity` should succeed before launching the graph.
- **FRED errors**: double-check `FRED_API_KEY` and API limits. `fredapi` raises helpful exceptions that propagate back through the tool message.
- **Postgres connectivity**: the FRASER helpers rely on SSL defaults—if your DB requires custom SSL params, adjust `_pg_connect` helpers accordingly.
- **Attachments not rendering**: confirm your client consumes the `attachments` array from the graph response; LangGraph Studio does this automatically.
- **LangSmith noise**: unset `LANGSMITH_API_KEY` or export `LANGCHAIN_TRACING_V2=false` to disable tracing temporarily.

## Next steps
- Wire up your preferred vector store in `retrieval.make_retriever` and start indexing documents via `index_graph.py` when you need private context.
- Add new tools by extending `TOOL_DEFINITIONS` and handling them inside `call_tool`—follow the pattern used by the FRED helpers.
- Swap Bedrock models or add fallbacks by adjusting the `ChatBedrockConverse` construction to read model IDs from config instead of constants.
