# Quick Start Guide

Get your Telegram LLM Bot running in 5 minutes!

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for services)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

## Option 1: Quick Start with Docker (Recommended)

### 1. Get Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the instructions
3. Copy your bot token

### 2. Clone and Configure
```bash
git clone <repository-url>
cd telegram-llm-bot

# Copy environment file
cp .env.example .env

# Edit .env and add your bot token
nano .env  # or use your favorite editor
```

**Required settings in `.env`:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+asyncpg://botuser:changeme@postgres:5432/telegram_bot
REDIS_URL=redis://:changeme@redis:6379/0
```

### 3. Start Everything
```bash
# Start all services (PostgreSQL, Redis, Bot)
docker-compose up -d

# Check logs
docker-compose logs -f bot
```

That's it! Your bot should now be running. Open Telegram and send `/start` to your bot.

## Option 2: Local Development

### 1. Install Poetry
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

If Poetry isn't available in your environment, use a virtualenv + pip instead:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # Generate with: poetry export -f requirements.txt --without-hashes > requirements.txt
```

### 2. Setup Project
```bash
# Install dependencies
poetry install

# Copy and edit .env
cp .env.example .env
# Edit .env with your settings
```

### 3. Start Services
```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait a few seconds for services to start
sleep 5

# Run migrations
poetry run alembic upgrade head
```

### 4. Configure LLM Server

You need an LLM server running. Options:

**Option A: Use Local vLLM (requires GPU)**
```bash
# Install vLLM
pip install vllm

# Start server
python -m vllm.entrypoints.openai.api_server \
    --model <your-model> \
    --host 0.0.0.0 \
    --port 8000
```

**Option B: Use Remote API**
Update `.env`:
```bash
LLM_BASE_URL=https://your-llm-api.com/v1
LLM_API_KEY=your_api_key
```

### 5. Start Bot
```bash
poetry run python -m bot.main
```

## Testing Your Bot

1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. Try these commands:
   - `/help` - Show help
   - `/reset` - Clear conversation history
   - Ask any question naturally

### Group Chats

In group or supergroup chats the bot will only respond when explicitly addressed to avoid spamming:
1. Mention: `@YourBotName what time is it?`
2. Reply to a previous bot message
3. Name prefix: `YourBotName: summarize the last discussion`

All other messages are ignored silently.

## Enabling MCPs

Edit `.env` to enable/disable MCPs:

```bash
# File System MCP - read/write files
MCP_FILESYSTEM_ENABLED=true
MCP_FILESYSTEM_BASE_PATH=/tmp/bot_workspace

# Database MCP - query databases
MCP_DATABASE_ENABLED=false
MCP_DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Web Search MCP - search the web
MCP_WEBSEARCH_ENABLED=false
MCP_WEBSEARCH_API_KEY=your_api_key

# Advanced Option
Looking for multi‑engine search (Brave/Bing/DuckDuckGo), summaries, and configurable content extraction limits? Consider running the external MCP server `mrkrsl/web-search-mcp` (https://github.com/mrkrsl/web-search-mcp) alongside the bot and exposing its tools through a custom plugin wrapper or direct MCP connection.

### External Web Search MCP (Optional)

Add an advanced web search service to Docker Compose:
```bash
mkdir -p external
git clone https://github.com/mrkrsl/web-search-mcp external/web-search-mcp
```

Example snippet to add to `docker-compose.yml`:
```yaml
    mcp_web_search:
        image: node:20-alpine
        working_dir: /app
        volumes:
            - ./external/web-search-mcp:/app
        command: sh -c "npm install && npx playwright install && npm run build && node dist/index.js"
        environment:
            MAX_CONTENT_LENGTH: 50000
            DEFAULT_TIMEOUT: 6000
            MAX_BROWSERS: 2
            BROWSER_HEADLESS: "true"
            BROWSER_FALLBACK_THRESHOLD: 3
        networks:
            - bot-network
        restart: unless-stopped
```

Bring it up:
```bash
docker-compose up -d mcp_web_search
```

Create an adapter MCP plugin (see `MCP_WEB_SEARCH.md`) to map external tools:
| External Tool | Suggested Adapter Name |
|---------------|------------------------|
| full-web-search | full_web_search |
| get-web-search-summaries | get_web_search_summaries |
| get-single-web-page-content | get_single_web_page_content |

Decide selection logic (e.g. use external for queries containing keywords: `research`, `summarize`, `compare`).
```

Restart the bot after changing settings.

## Common Issues

### Bot not responding
- Check if bot token is correct
- Check if LLM server is running
- Check logs: `docker-compose logs bot`

### Database errors
```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres redis
sleep 5
poetry run alembic upgrade head
```

### Redis connection errors
```bash
# Restart Redis
docker-compose restart redis
```

## Next Steps

- Read [DESIGN.md](./DESIGN.md) for architecture details
- See [CONTRIBUTING.md](./CONTRIBUTING.md) for development guide
- Create custom MCPs in `bot/mcp/plugins/`
- Add more bot commands in `bot/handlers.py`

## Useful Commands

```bash
# View logs
docker-compose logs -f bot

# Restart bot
docker-compose restart bot

# Run tests
poetry run pytest

# Format code
poetry run black .

# Stop everything
docker-compose down
```

## Production Deployment

See the deployment section in [README.md](./README.md) for:
- Kubernetes deployment
- Environment variables
- Monitoring setup
- Scaling guidelines

## Support

- **Issues**: [GitHub Issues]
- **Docs**: [DESIGN.md](./DESIGN.md)
- **Contributing**: [CONTRIBUTING.md](./CONTRIBUTING.md)
