# FOMC and Fred AI Assistant

> A LangGraph-based financial copilot that combines AWS Bedrock conversations with live FRED and FOMC data tools.

<!-- [Open in LangGraph Studio](https://langgraph-studio.vercel.app/templates/open?githubUrl=https://github.com/langchain-ai/retrieval-agent-template)
· [Hosted graph](https://my-langgraph-app.fly.dev) · [Studio session on Smith](https://smith.langchain.com/studio/?baseUrl=https://my-langgraph-app.fly.dev) -->

![Graph view](./static/Screenshot%202025-12-11%20at%201.42.01%E2%80%AFAM.png)

## Demo
Watch the walkthrough:
https://drive.google.com/file/d/19mCbWbvYeDhc0DlvhBv7k6XB2ZQMBRY-/view?usp=sharing

## TL;DR
- Conversational loop runs on LangGraph with a single `StateGraph` (see `src/retrieval_graph/graph.py`), powered by `ChatBedrockConverse` (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`).
- Built-in tools cover FRED charts, recent datapoints, release metadata, FRASER/Postgres searches, and a live "latest FOMC decision" card.
<!-- - Document retrieval is wired to `retrieve_documents` and `retrieval.make_retriever`, but the focus of this README is the Bedrock + tooling experience—hook your own vector store when you are ready. -->
- LangSmith tracing is enabled so every run is observable; attachments (chart images) and structured `series_data` ride outside the prompt for richer UX.
<!-- - Public App Runner endpoint (current): https://vpinmbqrjp.us-east-1.awsapprunner.com -->

## Repository layout
| Path | Purpose |
| --- | --- |
| `src/retrieval_graph/graph.py` | Conversation loop, Bedrock client construction, tool registry, routing between `agent` and `tools` nodes. |
| `src/retrieval_graph/state.py` | Strongly-typed LangGraph state, reducers for attachments, structured series data, and citations. |
| `src/retrieval_graph/fred_tool.py` | Handles FRED charts, datapoints, correlation, and release metadata via the official API. |
| `src/retrieval_graph/fraser_tool.py` | Connects to your FRASER-backed Postgres instance for FOMC title search. |
| `src/retrieval_graph/services.py` | Builds the "latest FOMC decision" snapshot from Postgres data. |
<!-- | `src/retrieval_graph/index_graph.py` | (Optional) single-node index flow for uploading private documents. Left intact but not needed to run the chat bot. | -->
| `langgraph.json` | Declares the deployable graphs for the LangGraph CLI (`retrieval_graph`). |
| `pyproject.toml` | Python dependencies; install the project in editable mode for development. |

## Prerequisites
- Python 3.11+ and a modern virtual environment tool (e.g., `uv`, `pip`, or `conda`).
- AWS account with Bedrock access to Anthropic Claude models and a configured profile.
- FRED API key for charts/data (`FRED_API_KEY`).
- Network access + credentials for the FRASER/Postgres databases that hold FOMC items and meeting decisions.
- Optional but recommended: LangSmith account for tracing (`LANGSMITH_API_KEY`).

## Quick start
### 1. Clone & install
```bash
cd /path/to/projects
git clone https://github.com/qufeiz/FredSeriesAI.git
cd FredGPT-backend
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
<!-- | `FRED_CHART_WIDTH`, `FRED_CHART_HEIGHT` (optional) | Override the PNG dimensions generated via `fredgraph.png`. | -->
| `PG_HOST`, `PG_PORT`, `PG_NAME`, `PG_USER`, `PG_PASS` | Required by `fraser_tool.py` and `services.py` to talk to FRASER/FOMC tables. |
| `HYBRID_SEARCH_URL`, `HYBRID_SEARCH_TOKEN` | Endpoint + bearer token for the FRASER hybrid search service (semantic + keyword). |

> `FRASER_API_KEY`, OpenSearch, or ingestion-specific variables from the original template are no longer needed unless you decide to revive those scripts.

### AWS SSO quickstart
If you use AWS SSO, initialize your CLI profile and log in:
```bash
aws configure sso # create your profile (sso_start_url: https://stlfrb.awsapps.com/start)
aws sso login --profile AWSAdministratorAccess # use your profile name
```
During `aws configure sso` supply your org values (e.g., start URL, SSO region, account ID, role name, preferred profile name). Subsequent CLI calls (including Terraform) will pick up the saved profile.

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

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{ "text": "Greetings, do you have data on inflation in Denmark?", "conversation": [] }'

# curl -X POST https://vpinmbqrjp.us-east-1.awsapprunner.com/ask \
#   -H "Content-Type: application/json" \
#   -d '{ "text": "what happend in fomc september 2020?", "conversation": [] }'

# curl -X POST https://vpinmbqrjp.us-east-1.awsapprunner.com/ask \
#   -H "Content-Type: application/json" \
#   -d '{ "text": "what tools do u have", "conversation": [] }'

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{ "text": "my credit card number is 1234567, tell me how to get money", "conversation": [] }'

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
- `tools`: executes every tool call emitted by the model, tracks attachment payloads, and increments `tool_call_count` to guard against loops.

Routing is simple: start → `agent` → optional `tools` → back to `agent` until no more tool calls are requested.

### FRASER / Postgres data
- The FRASER/FOMC Postgres DB lives on AWS RDS (e.g., `fomc-db.c6voia0autyx.us-east-1.rds.amazonaws.com`), this is seperate from the Opensearch DB specifically built for quick access to FOMC. Supply `PG_HOST/PG_PORT/PG_NAME/PG_USER/PG_PASS` via env/SSM (managed by terraform).
- `scripts/fraser/index_fraser.py` loads the FRASER FOMC catalog into `fomc_items` (columns: `id`, `titleInfo`, `originInfo`, `location`, `recordInfo`) from `scripts/fraser/output/title_677_items.json`.
- `scripts/fraser/extractor/load_meetings.py` upserts meeting metadata into `fomc_meetings` (PK `meeting_id`, `meeting_date`, rate fields, votes) from JSON files under `scripts/fraser/extractor/meetings`.
- Runtime tools:
  - `fraser_search_fomc_titles` queries `fomc_items`.
  - `fomc_latest_decision` uses `services.get_latest_payload()` to read `fomc_meetings`.
  - `fraser_hybrid_search` hits the external hybrid search service (semantic + keyword) configured via `HYBRID_SEARCH_URL`/`HYBRID_SEARCH_TOKEN` and returns FRASER/FOMC snippets.

### Tool catalog (what is actually used)
<!-- `retrieve_documents` is currently disabled; only the live data tools below are advertised to the model. -->
| Tool name | Description | Source |
| --- | --- | --- |
| `fred_chart` | Pulls a FRED-rendered PNG, base64 encodes it, and returns it as an attachment so clients can render the chart inline. | `fred_tool.fetch_chart` |
| `fred_recent_data` | Returns structured `series_data` (metadata + recent points) for downstream reasoning. | `fred_tool.fetch_recent_data` |
| `fred_series_release_schedule` | Maps a series to its release and shares upcoming publication dates. | `fred_tool.fetch_series_release_schedule` |
| `fred_release_structure` | Returns the tables + metadata for a given release name (e.g., "H.4.1"). | `fred_tool.fetch_release_structure_by_name` |
| `fred_search_series` | Text search across the FRED catalog. | `fred_tool.search_series` |
| `fred_series_correlation` | [EXPERIMENTAL] Compares YoY growth across two series and reports the strongest lead/lag window. | `fred_tool.analyze_series_correlation` |
| `fraser_search_fomc_titles` | Fuzzy-search FOMC meeting documents from FRASER/Postgres. | `fraser_tool.search_fomc_titles` |
| `fraser_hybrid_search` | Hybrid (semantic + keyword) search across FRASER/FOMC docs via the external search API. | `hybrid_tool.search_hybrid` |
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

<!-- ## Development workflow
- `make test` (or `pytest`) exercises the unit tests under `tests/`.
- `make lint` runs Ruff format + lint plus strict mypy. Use `make format` to apply Ruff's formatter/fixes.
- Use `langgraph dev --allow-blocking --watch` (from the CLI) to reload graphs as you edit Python files.
- When editing prompts or tools, remember that attachments or structured state must remain JSON-serializable. -->

<!-- ## Deployment notes -->
<!-- - `fly.toml` contains the production config that backs `https://my-langgraph-app.fly.dev`. Run `fly deploy` after logging in with `fly auth login` to ship updates. -->
<!-- - Provide the same `.env` values (or Fly secrets) in production; at a minimum you need the AWS + FRED + Postgres variables described earlier.
- LangGraph Cloud / Smith Studio can target either your Fly deployment or a local `langgraph dev --allow-blocking` session—no code changes required. -->

### Terraform (App Runner + ECR)
- Set `AWS_PROFILE`/`AWS_REGION`, copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, and fill in real secrets (kept out of git).
<!-- - If you already created the service by hand, import the live resources before your first apply:
  - `terraform import aws_ecr_repository.backend arn:aws:ecr:us-east-1:<acct>:repository/fredgpt-backend`
  - `terraform import aws_iam_role.apprunner_ecr AppRunnerECRAccessRole`
  - `terraform import aws_iam_role.apprunner_instance AppRunner-FredGPT-InstanceRole`
  - `terraform import aws_apprunner_service.backend arn:aws:apprunner:us-east-1:<acct>:service/fredgpt-backend/<service-id>` -->
- Fresh deploy: `cd terraform && terraform init && terraform apply`. Secrets are stored in SSM and pulled into App Runner via `runtime_environment_secrets`; Terraform state never contains secret values.

### CI/CD & AWS
- `ci.yml` runs Ruff + a minimal pytest (`test_api_basic.py`) on push/PR. Other tests are currently excluded.
- `deploy.yml` builds/pushes the ECR image and runs Terraform using the GitHub Actions OIDC role `arn:aws:iam::112393354239:role/GitHubActions-FredGPT-Backend` in `us-east-1`.
- `integration-tests.yml` runs the live graph test daily at 14:37 UTC (and on manual trigger); it assumes the same OIDC role plus FRED/PG/guardrail secrets in GitHub Secrets.
- `integration-live.yml` is an extra manual-only entry point for the live graph test when you want to trigger it on demand.

## Troubleshooting
- **Bedrock auth failures**: ensure `AWS_PROFILE` points to a local profile with Bedrock access (or unset it so boto3 falls back to your default credentials). A quick `aws sts get-caller-identity` should succeed before launching the graph.
- **FRED errors**: double-check `FRED_API_KEY` and API limits. `fredapi` raises helpful exceptions that propagate back through the tool message.
- **Postgres connectivity**: the FRASER helpers rely on SSL defaults—if your DB requires custom SSL params, adjust `_pg_connect` helpers accordingly.
- **Attachments not rendering**: confirm your client consumes the `attachments` array from the graph response; LangGraph Studio does this automatically.
- **LangSmith noise**: unset `LANGSMITH_API_KEY` or export `LANGCHAIN_TRACING=false` to disable tracing temporarily.

## Next steps
<!-- - Wire up your preferred vector store in `retrieval.make_retriever` and start indexing documents via `index_graph.py` when you need private context. -->
- Add new tools by extending `TOOL_DEFINITIONS` and handling them inside `call_tool`—follow the pattern used by the FRED helpers.
- Swap Bedrock models or add fallbacks by adjusting the `ChatBedrockConverse` construction to read model IDs from config instead of constants.

<!-- eval:https://smith.langchain.com/public/35347757-e950-4c7d-9deb-e0fbf3d7303e/r
what is the unemployment rate by demographic
question: what is the unemployment rate by demographic
{
  "accuracy": {
    "score": 5,
    "justification": "All unemployment rates in the model's response match the latest September 2025 values returned by the tool. No numerical errors or invented series were found."
  },
  "completeness": {
    "score": 5,
    "justification": "The model reported every demographic category retrieved by the tool: overall rate, age 16–19, all race/ethnicity groups, and gender for workers 20+. No categories were omitted."
  },
  "clarity_structure": {
    "score": 4.5,
    "justification": 'The answer is cleanly organized with headings and lists. Minor improvement would be explicitly grouping the "20 years and over" category before gender, rather than referencing it indirectly.'
  },
  "reasoning_data_use": {
    "score": 5,
    "justification": "Interpretations are fully supported by the data: youth unemployment is higher, racial disparities exist, gender differences are small. No incorrect trends, no causal claims, and no extrapolations."
  },
  "policy_safety": {
    "score": 4.5,
    "justification": "The response discusses demographic unemployment differences using official statistics and without harmful inference. A brief clarification about structural factors could further reduce risk of misinterpretation."
  },
  "final_score": {
    "score": 24,
    "max_score": 25,
    "percentage": 96
  }
}

eval:https://smith.langchain.com/public/b822e419-b2de-4d1d-87b3-32fb8502c149/r
What were the policy changes for the latest FOMC meeting? What was the reasoning behind them?
{
  "accuracy": {
    "score": 5,
    "justification": "All policy details match the tool document: the 25bp cut to 3.75–4.00%, QT ending Dec 1, reinvestment beginning Dec 1, and the 10–2 vote with Miran and Schmid dissenting. No invented policy actions or misquoted language."
  },
  "completeness": {
    "score": 5,
    "justification": "The answer covers every major component in the retrieved FOMC text: rate change, balance sheet decision, implementation details, vote breakdown, and the reasoning section (economic activity, labor market, inflation, risk balance). Nothing in the original excerpt is meaningfully omitted."
  },
  "clarity_structure": {
    "score": 4.5,
    "justification": "Extremely clear structure: policy changes, reasoning, vote details. Uses headings and lists. Minor nit: could include the exact wording of the balance-sheet instructions for even more precision, but that's optional."
  },
  "reasoning_data_use": {
    "score": 5,
    "justification": "The explanation is fully grounded in the text: moderate growth, slowing job gains, elevated inflation, shift in risks. No fabricated interpretations. No extrapolation beyond what's in the statement."
  },
  "policy_safety": {
    "score": 5,
    "justification": "All content involves public monetary policy information. No sensitive or risky content. Clean and compliant."
  },
  "final_score": {
    "score": 24.5,
    "max_score": 25,
    "percentage": 98
  }
} -->
