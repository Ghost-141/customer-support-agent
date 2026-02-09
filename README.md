# Support Agent

A WhatsApp/Telegram/WebSocket customer support agent that answers product questions using a PostgreSQL-backed catalog and a tool-augmented LLM graph.

## Highlights
- LangGraph + LangChain orchestration with tool retrieval via Chroma.
- PostgreSQL product catalog with category browsing and review summaries.
- Conversation memory stored in Postgres with rolling summaries.
- Ollama or Groq LLM provider selection via env (`LLM_PROVIDER`).

## How It Works
- The agent runs a LangGraph state machine with preprocess, tool retrieval, optional summarization, assistant, and tool nodes.
- The assistant uses the system prompt in `prompts.py` to enforce tool usage and response rules.
- Tools in `tools/qa.py` query the database via `data/db.py`.
- Conversation state is stored in Postgres using the LangGraph Postgres checkpointer.
- Tool retrieval uses a Chroma vector store built from tool descriptions in `tools/vectorize_tools.py` and stored in `data/chroma_db`.
- Summarization keeps recent turns and rolls older context into a stored summary.

## Project Structure
- `api/app.py` configures FastAPI and registers routers.
- `api/routers/` contains `telegram.py`, `whatsapp.py`, and `websocket.py`.
- `api/services/` contains messaging helpers, dependency wiring, and the WebSocket manager.
- `api/schemas.py` defines LangGraph state and response models.
- `api/uvicorn_loop.py` forces selector event loop on Windows for psycopg.
- `agent.py` runs the agent logic and CLI loop.
- `graph_builder.py` wires the LLM, tools, tool retrieval, and graph routing.
- `prompts.py` contains the system prompt and tool usage rules.
- `tools/qa.py` exposes database-backed tools to the LLM.
- `tools/vectorize_tools.py` builds the Chroma tool-retrieval index.
- `data/db.py` provides database access and helpers.
- `data/db_pool.py` builds the async Postgres pool used by the API and agent.
- `data/load_data.py` loads or updates data into the database.
- `data/products.json` is the seed dataset.
- `data/chroma_db/` stores the persisted tool-retrieval index.
- `utils/llm_provider.py` selects Ollama or Groq based on env.
- `frontend/` contains the React UI for local WebSocket testing.

## Requirements
- Python 3.11+
- A running PostgreSQL instance (Supabase or local)
- Ollama running locally/remote, or a Groq API key

## Setup
1. Create a virtual environment and install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r <(python - <<'PY'
import tomllib
from pathlib import Path
pyproject = tomllib.loads(Path('pyproject.toml').read_text())
print('\n'.join(pyproject['project']['dependencies']))
PY
)
```

If you use `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -r <(python - <<'PY'
import tomllib
from pathlib import Path
pyproject = tomllib.loads(Path('pyproject.toml').read_text())
print('\n'.join(pyproject['project']['dependencies']))
PY
)
```

2. Copy `.env.example` to `.env` and update values.

```bash
cp .env.example .env
```

3. Build the tool-retrieval index for Chroma.

```bash
uv run -m tools.vectorize_tools
```

## Configuration
These environment variables are used by the agent and loader.

- `LLM_PROVIDER` (`ollama` or `groq`)
- `OLLAMA_MODEL`
- `OLLAMA_EMBEDDING_MODEL`
- `OLLAMA_BASE_URL`
- `OLLAMA_TEMPERATURE`
- `OLLAMA_NUM_PREDICT`
- `OLLAMA_NUM_CTX`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GROQ_TEMPERATURE`
- `GROQ_MAX_TOKENS`
- `SUPASEBASE_DB_URL` or all of:
- `SUPASEBASE_DB_HOST`
- `SUPASEBASE_DB_NAME`
- `SUPASEBASE_DB_USER`
- `SUPASEBASE_DB_PASSWORD`
- `SUPASEBASE_DB_PORT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` (optional but recommended)
- `WHATSAPP_API_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `MAX_MESSAGE_LENGTH` (shared limit for inbound messages)
- `SUMMARY_TRIGGER_TURNS` (turns before summarization)
- `SUMMARY_KEEP_TURNS` (recent turns to keep verbatim)
- `SUMMARY_MAX_CHARS` (summary character cap)
- `LANGCHAIN_API_KEY` (optional for tracing)
- `LANGCHAIN_ENDPOINT` (optional for tracing)
- `CREATE_TABLES` (used by `data/load_data.py`)
- `LOG_LEVEL` (used by `data/load_data.py`)

Note: The code expects the `SUPASEBASE_` prefix exactly as shown.

## Database Setup
You have two ways to create and seed the database. Both expect `products.json` in the `data/` directory.

Option 1: Use `data/db.py` helpers (drops and recreates tables).

```bash
cd data
python db.py
```

Option 2: Use the data loader.

```bash
cd data
python load_data.py
```

Set `CREATE_TABLES=1` in your environment to create tables automatically.

## Run The Agent
Start the local interactive loop:

```bash
python agent.py
```

- You can type `/clear` to remove conversation history for the current user.
- Use `quit`, `exit`, or `q` to leave the session.

## Run The API Server
Start FastAPI for webhooks and WebSocket connections:

```bash
python main.py
```

The default port is `80` (see `main.py`). Update it if you want a different port.

## Local Testing
You have two local testing options.

1. CLI testing

```bash
python agent.py
```

2. WebSocket testing

- Backend endpoint: `ws://localhost:80/ws/{client_id}`
- Send plain text or JSON:

```json
{"text": "Hello", "stream": true}
```

The WebSocket server streams responses as JSON messages:

```json
{"type": "chunk", "text": "partial"}
{"type": "done"}
```

## Frontend (Local UI)
The `frontend/` React app connects to the WebSocket endpoint for local testing.

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Run the dev server:

```bash
npm run dev
```

3. Open the URL shown by Vite and set the Server URL to match your API port.

## Integrations

### Telegram
Use Telegram to send user messages to the agent via webhook.

1. Create a bot with BotFather and copy the token.
2. Set the env vars in `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_SECRET=your_secret_value
MAX_MESSAGE_LENGTH=1000
```

3. Run the FastAPI server:

```bash
python main.py
```

4. Expose your server over HTTPS (Telegram requires a public HTTPS URL).
5. Register the webhook URL (replace with your public domain):

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://YOUR_DOMAIN/telegram/webhook\",\"secret_token\":\"$TELEGRAM_WEBHOOK_SECRET\"}"
```

6. Verify the webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

The webhook handler is in `api/routers/telegram.py` and calls `run_agent()` to generate responses.

### WhatsApp
Use WhatsApp Cloud API to send user messages to the agent via webhook.

1. Create a WhatsApp app in Meta and copy the API token and phone number ID.
2. Set the env vars in `.env`:

```bash
WHATSAPP_API_TOKEN=your_api_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=your_verify_token
MAX_MESSAGE_LENGTH=1000
```

3. Run the FastAPI server:

```bash
python main.py
```

4. Expose your server over HTTPS (Meta requires a public HTTPS URL).
5. Configure the webhook URL (replace with your public domain):

- Verify URL: `https://YOUR_DOMAIN/webhook`
- Callback URL: `https://YOUR_DOMAIN/webhook`
- Verify token: use `WHATSAPP_VERIFY_TOKEN`

The webhook handler is in `api/routers/whatsapp.py` and sends responses with the Cloud API.

## Available Tools
These are exposed to the LLM via LangChain tools in `tools/qa.py`.

- `get_product_by_name` fetches product details by title (with fallback search).
- `get_product_reviews` returns recent reviews with a short summary.
- `get_tag_categories` lists categories.
- `get_products_in_category` lists products by category.

## Prompt Rules
The assistant behavior is governed by `prompts.py`.

- The first message begins with a fixed greeting.
- Tool usage is mandatory after the first message.
- If a tool returns no items, the assistant must ask for clarification.
- All product or category results are shown as Markdown lists.

## Troubleshooting
- If the agent returns empty results, verify the database is seeded.
- If tools fail, confirm `SUPASEBASE_DB_URL` or the split `SUPASEBASE_DB_*` variables.
- If the model fails to respond, check `LLM_PROVIDER` and the provider-specific env vars.
- If tool retrieval returns no tools, rebuild the index with `uv run -m tools.vectorize_tools`.

## License
See `LICENSE`.
