# Customer Support Agent

![Demo Video](demo.gif)

A Real Time Customer Support Agent that answers product questions using a PostgreSQL-backed catalog and a tool-augmented LLM.

## Highlights
- LangGraph + LangChain orchestration with tool retrieval via Chroma.
- PostgreSQL product catalog with category browsing and review summaries.
- Conversation memory stored in Postgres with rolling summaries.
- Ollama or Groq LLM provider selection via env (`LLM_PROVIDER`).


## Project Structure


```text
support_agent/
├── .env
├── .gitignore
├── .python-version
├── agent.py
├── api/
│   ├── app.py
│   ├── routers/
│   │   ├── telegram.py
│   │   ├── websocket.py
│   │   └── whatsapp.py
│   ├── dependency.py
│   ├── schemas.py
│   ├── services/
│   │   ├── telegram.py
│   │   ├── websocket.py
│   │   └── whatsapp.py
│   └── uvicorn_loop.py
├── data/
│   ├── chroma_db/
│   ├── db.py
│   ├── db_pool.py
│   ├── load_data.py
│   └── products.json
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   └── vite.config.js
├── graph_builder.py
├── main.py
├── prompts.py
├── pyproject.toml
├── README.md
├── tools/
│   ├── qa.py
│   └── vectorize_tools.py
├── utils/
│   └── llm_provider.py
├── tests/
│   ├── __init__.py
│   ├── scenario_utils.py
│   ├── test_scenario_product_category.py
│   ├── test_scenario_product_info.py
│   ├── test_scenario_product_reviews.py
│   └── test_scenario_products_in_category.py
└── uv.lock
```

## Setup


Create a virtual environment and run the following commands:

```bash
cd support_agent
pip install uv
uv sync
ollama pull llama3.2:3b # agent
ollama pull embeddinggemma:300m # embedding model
```

Update the `.env.example` with API keys and variables and rename it to `.env`.


Build the tool-retrieval index for Chroma.

```bash
python -m tools.vectorize_tools
```

## Docker Deployment
You can run the full backend stack (API + Postgres) with Docker and connect it to an Ollama instance running on your host machine.

1. Prepare env:

    ```bash
    cp .env.example .env
    ```

2. In `.env`, keep these values for Docker + local Ollama:

    ```bash
    LLM_PROVIDER=ollama
    OLLAMA_MODEL=llama3.2:latest
    OLLAMA_EMBEDDING_MODEL=embeddinggemma:300m
    ```

3. Start Ollama on host (outside Docker) and pull models:

    ```bash
    ollama serve
    ollama pull llama3.2:latest
    ollama pull embeddinggemma:300m
    ```

4. Start Docker services:

    ```bash
    docker compose -f docker_compose.yml up -d --build
    ```

5. API is available at:

    ```text
    http://localhost:8000
    ```

6. Open API docs:

    ```text
    http://localhost:8000/docs
    ```

7. Verify container can reach Ollama:

    ```bash
    docker exec support-agent-api uv run python -c "import requests; print(requests.get('http://host.docker.internal:11434/api/tags', timeout=10).status_code)"
    ```

Notes:
- Container-to-host Ollama URL is set in compose as `http://host.docker.internal:11434`.
- On Linux, `extra_hosts: host.docker.internal:host-gateway` is already configured in `docker_compose.yml`.
- On first boot, the container auto-seeds Postgres and auto-builds the Chroma tool index.
- Set `AUTO_SEED_DB=0` or `AUTO_VECTORIZE_TOOLS=0` in `.env` to disable those startup steps.

### Docker + Telegram Webhook (ngrok)
1. Set Telegram values in `.env`:

    ```bash
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_WEBHOOK_SECRET=your_secret
    ```

2. Start ngrok:

    ```bash
    ngrok http 8000
    ```

3. Set webhook with helper script (recommended over manual curl escaping):

    ```bash
    python scripts/set_telegram_webhook.py --base-url https://YOUR_NGROK_DOMAIN
    ```

4. Verify current webhook:

    ```bash
    python scripts/set_telegram_webhook.py --info-only
    ```

## Configuration
These environment variables are used by the agent and loader.

```bash 
# Model Configuration
LLM_PROVIDER (ollama or groq)
OLLAMA_MODEL
OLLAMA_EMBEDDING_MODEL
OLLAMA_BASE_URL
OLLAMA_TEMPERATURE
OLLAMA_NUM_PREDICT
OLLAMA_NUM_CTX

# Groq Models Config (Under Development)

GROQ_API_KEY
GROQ_MODEL
GROQ_TEMPERATURE
GROQ_MAX_TOKENS

# Database Configuration
SUPASEBASE_DB_URL
SUPASEBASE_DB_HOST
SUPASEBASE_DB_NAME
SUPASEBASE_DB_USER
SUPASEBASE_DB_PASSWORD
SUPASEBASE_DB_PORT

# Telegram Configuration

TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET (optional but recommended)

# WhatsApp Configuration

WHATSAPP_API_TOKEN
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_VERIFY_TOKEN

# Message Configuration

MAX_MESSAGE_LENGTH (shared limit for inbound messages)
SUMMARY_TRIGGER_TURNS (turns before summarization)
SUMMARY_KEEP_TURNS (recent turns to keep verbatim)
SUMMARY_MAX_CHARS (summary character cap)

# LangSmith Configuration

LANGCHAIN_API_KEY (optional for tracing)
LANGCHAIN_ENDPOINT (optional for tracing)
CREATE_TABLES (used by `data/load_data.py`)

# LangWatch Configuration
LANGWATCH_API_KEY
```

Note: The code expects the `SUPASEBASE_` prefix exactly as shown.

## Database Setup
The agent requires PostgreSQL for:
- product catalog data
- conversation checkpoint memory

Recommended (Docker full stack):

```bash
docker compose -f docker_compose.yml up -d --build
```

This already starts Postgres and API together. On first startup, the container:
- creates checkpoint tables (if missing)
- seeds product data when `products` is empty (`AUTO_SEED_DB=1`)

Optional (run only PostgreSQL service):

```bash
docker compose -f docker_compose.yml up -d postgresql_db
```

Use this DB URL in `.env` for local app runs:

```bash
SUPASEBASE_DB_URL=postgresql://postgres:postgresql@localhost:5432/postgres?sslmode=disable
```

Notes:
- Default DB credentials from `docker_compose.yml`: 
  - user: `postgres`,
  - password: `postgresql`
  - db: `postgres`.
- pgAdmin is available at `http://localhost:8888` when started with profile `dev`.
- Manual reseed (drops and recreates product tables):

```bash
cd data
python db.py
```

## Run The Agent for Manual Testing
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


## Testing (Scenario)
Scenario tests live in `tests/` and exercise the agent end-to-end with deterministic checks.


### Run Tests
1. Run all the scenario tests:

    ```bash
    pytest -m agent_test
    ```

2. Run one test file:

    ```bash
    pytest tests/test_scenario_product_reviews.py
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

3. Start the API (local or Docker):

    ```bash
    # local
    python main.py

    # docker
    docker compose -f docker_compose.yml up -d --build
    ```

4. Expose your server over HTTPS (Telegram requires a public HTTPS URL).
5. If you use ngrok with Docker:

    ```bash
    ngrok http 8000
    ```

6. Set the webhook with the helper script (recommended):

    ```bash
    python scripts/set_telegram_webhook.py --base-url https://YOUR_DOMAIN
    ```

7. Verify the webhook:

    ```bash
    python scripts/set_telegram_webhook.py --info-only
    ```

The webhook handler is in `api/routers/telegram.py` and calls `run_agent()` to generate responses.

### WhatsApp (Under Testing)
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

- `get_product_by_name` fetches product details by title (with fallback search). If multiple similar products are found, it returns a disambiguation list so the assistant asks the user to choose the exact item.
- `get_product_reviews` returns recent reviews with a short summary.
- `get_tag_categories` lists categories.
- `get_products_in_category` lists products by category.


## Troubleshooting
- If the agent returns empty results, verify the database is seeded.
- If tools fail, confirm `SUPASEBASE_DB_URL` or the split `SUPASEBASE_DB_*` variables.
- If the model fails to respond, check `LLM_PROVIDER` and the provider-specific env vars.
- If tool retrieval returns no tools, rebuild the index with `uv run -m tools.vectorize_tools`.
- If Docker says Postgres is unhealthy with `initdb ... directory exists but is not empty`, recreate volumes (`docker compose down -v`) or use a new Postgres volume name.
- If local run fails with `password authentication failed for user "postgres"`, fix `.env` DB credentials or recreate DB volume to match `docker_compose.yml`.
- If Compose warns `version is obsolete`, remove `version:` from compose file; this warning does not block startup.

## License
See `LICENSE`.
