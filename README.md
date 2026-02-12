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
cd customer-support-agent
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

## Testing (Scenario)
Scenario tests live in `tests/` and exercise the agent end-to-end with deterministic checks.


### Run Tests
Run all the scenario tests:

  ```bash
  pytest -m agent_test
  ```

Run one test file:

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

- `get_product_by_name` fetches product details by title (with fallback search).
- `get_product_reviews` returns recent reviews with a short summary.
- `get_tag_categories` lists categories.
- `get_products_in_category` lists products by category.


## Troubleshooting
- If the agent returns empty results, verify the database is seeded.
- If tools fail, confirm `SUPASEBASE_DB_URL` or the split `SUPASEBASE_DB_*` variables.
- If the model fails to respond, check `LLM_PROVIDER` and the provider-specific env vars.
- If tool retrieval returns no tools, rebuild the index with `uv run -m tools.vectorize_tools`.

## License
See `LICENSE`.
