# Telegram LLM Bot with MCP Integration

A highly extensible Telegram bot powered by open-source LLMs with a plugin-based MCP (Model Context Protocol) architecture.

## Features

- 🤖 **LLM-Powered Conversations**: Natural language understanding using GPT-OSS 120B (swappable)
- 🔌 **MCP Extensibility**: Plugin architecture for adding custom context providers
- 👥 **Multi-User Support**: Concurrent user handling with isolated contexts
- 💾 **Context Management**: Conversation history and session management
- 📁 **Rich Media Support**: Text, images, documents, and voice messages
- 🛡️ **Rate Limiting**: Protection against abuse
- 🔐 **Admin Controls**: Management interface for bot operators

## Architecture

See [DESIGN.md](./DESIGN.md) for comprehensive design documentation.

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Poetry (for dependency management)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd telegram-llm-bot
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize the database**:
   ```bash
   poetry run alembic upgrade head
   ```

5. **Run the bot**:
   ```bash
   poetry run python -m bot.main
   ```

## Configuration

### Environment Variables

Key configuration options in `.env`:

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from [@BotFather](https://t.me/botfather)
- `LLM_BASE_URL`: URL of your LLM server (e.g., vLLM)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string

See `.env.example` for all available options.

### MCP Configuration

Enable/disable MCPs in `.env`:

```bash
MCP_FILESYSTEM_ENABLED=true
MCP_DATABASE_ENABLED=false
MCP_WEBSEARCH_ENABLED=false
```

### Available MCP Plugins

The bot ships with a growing set of built‑in MCP plugins you can selectively enable:

| MCP | Purpose | Typical Tools |
|-----|---------|---------------|
| FileSystemMCP | Safe, sandboxed file workspace operations | `read_file`, `write_file`, `list_directory` |
| DatabaseMCP | Read‑only SQL querying and schema introspection | `query_database`, `get_schema` |
| WebSearchMCP | Lightweight web search + page content extraction | `web_search`, `fetch_webpage` |

WebSearchMCP provides basic search results and page fetching. For a more feature‑rich standalone MCP server (multi‑engine search, summaries, full content extraction), see the external project: `mrkrsl/web-search-mcp` → https://github.com/mrkrsl/web-search-mcp

Additional environment variables (optional) for tuning web search:
```
MCP_WEBSEARCH_SEARCH_ENGINE=duckduckgo   # duckduckgo | bing | brave (depends on implementation)
WEB_SEARCH_MAX_RESULTS=5                 # Default maximum results for built-in plugin
WEB_SEARCH_TIMEOUT_MS=6000              # Timeout per search request
WEB_SEARCH_CONTENT_LIMIT=50000          # Max characters when extracting page content
```

#### External Advanced Web Search MCP Service

To run the external TypeScript server alongside the bot:

1. Clone the repository:
```bash
mkdir -p external
git clone https://github.com/mrkrsl/web-search-mcp external/web-search-mcp
```
2. Add a service to `docker-compose.yml` (example):
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
3. Bring up the service:
```bash
docker-compose up -d mcp_web_search
```
4. Create an adapter MCP plugin (e.g. `external_websearch.py`) that forwards tool calls to the external server.

**Note:** The built-in Web Search MCP has been removed. Currently, all MCP plugins are disabled (0 registered). To use MCPs, you'll need to enable them in `bot/main.py` or implement external MCP services.

To implement your own plugin, place a module in `bot/mcp/plugins/` or configure a dynamic load path and follow the template shown below in "Creating Custom MCPs".

## Development

### Project Structure

```
telegram-llm-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── handlers/            # Telegram bot handlers
│   ├── session/             # Session management
│   ├── llm/                 # LLM integration
│   ├── mcp/                 # MCP framework
│   ├── models/              # Database models
│   ├── security/            # Security components
│   └── utils/               # Utilities
├── mcps/                    # Custom MCP plugins
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── docker/                  # Docker configurations
├── kubernetes/              # Kubernetes manifests
├── DESIGN.md               # Design documentation
├── pyproject.toml          # Python dependencies
└── README.md               # This file
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=bot --cov-report=html

# Run specific test file
poetry run pytest tests/test_session_manager.py
```

### Code Quality

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .

# Type checking
poetry run mypy bot
```

## Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop services
docker-compose down
```

### Using Kubernetes

```bash
# Apply configurations
kubectl apply -f kubernetes/

# Check status
kubectl get pods -l app=telegram-bot

# View logs
kubectl logs -f deployment/telegram-bot
```

## Creating Custom MCPs

## Running the real LLM model (gpt-oss-20b)

If you want the bot to use the real gpt-oss-20b model (instead of the mock server), place the model files at `./models/gpt-oss-20b` and run an OpenAI-compatible model server in the same Docker network.

Steps to run the model with Docker Compose:

1. Ensure the model artifacts are available locally:

```bash
# ./models/gpt-oss-20b should contain the model files (weights, tokenizer, config, etc.)
ls -la ./models/gpt-oss-20b
```

2. Update `.env.docker-compose` to point the bot at the llm service (this repository uses `llm_server` as the service name):

```bash
# set the base URL used by the bot
sed -i '' 's|^LLM_BASE_URL=.*|LLM_BASE_URL=http://llm_server:8000/v1|' .env.docker-compose
```

3. Replace or enable the `llm_server` service in `docker-compose.yml`. Example (CPU-only / vLLM-compatible runtime):

```yaml
llm_server:
   image: vllm/vllm-openai:latest
   environment:
      MODEL_NAME: gpt-oss-20b
   volumes:
      - ./models:/models
   networks:
      - bot-network
   restart: unless-stopped
   expose:
      - "8000"
```

Note: the example above assumes the image supports an OpenAI-compatible HTTP server exposing `/v1` endpoints. If you use a different runtime (e.g., a custom container or host process), adjust `LLM_BASE_URL` accordingly (for example `http://host.docker.internal:8000/v1`).

4. Start the LLM server and bring the bot up (or restart the bot so it picks up the new LLM URL):

```bash
docker-compose up -d llm_server
docker-compose up -d --no-deps --build bot
```

5. Verify the model server and that the bot can reach it:

```bash
# Check LLM server logs
docker-compose logs -f llm_server

# From a container in the same network test the health endpoint
docker run --rm --network telegram-llm-bot_bot-network curlimages/curl:8.10.1 -sS http://llm_server:8000/health

# Tail the bot logs to see LLM requests/responses
docker-compose logs -f bot
```

Notes and tips
- CPU-only runs of 20B models are possible but may be too slow and memory-heavy for practical use. If you have GPUs available, prefer an image that supports CUDA and restore any GPU device reservation you removed earlier.
- If your model server runs on the host machine instead of in Docker, use `host.docker.internal` as the hostname in `LLM_BASE_URL` (macOS/Windows Docker Desktop). Example: `http://host.docker.internal:8000/v1`.
- If you keep the mock LLM (`dev/mock_llm.py`) in the compose file, remove or disable it to avoid port/name conflicts.
- If the runtime uses authentication (API keys), set `LLM_API_KEY` in your `.env.docker-compose` and ensure the LLM server enforces/accepts that key.

If you'd like, I can replace the mock service with a specific vLLM compose snippet configured to load `./models/gpt-oss-20b` and bring the stack up for you.

1. Create a new file in `mcps/` directory:

```python
from bot.mcp.base import BaseMCP
from typing import Dict, Any, List, Optional

class MyCustomMCP(BaseMCP):
    """My custom MCP plugin"""
    
    version = "1.0.0"
    description = "Description of what this MCP does"
    
    async def initialize(self) -> bool:
        # Initialize your MCP
        return True
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        # Define your tools
        return []
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        # Execute tool logic
        pass
    
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        # Provide context to LLM
        return {}
```

2. Register your MCP in the configuration

3. The bot will automatically load and initialize your MCP

## Bot Commands

- `/start` - Start conversation with the bot
- `/help` - Show help message
- `/reset` - Clear conversation history
- `/stats` - Show usage statistics (admin only)

## Group Chat Behavior

The bot will only respond in group or supergroup chats when it is explicitly addressed to reduce noise:

Addressing methods:

1. Mention the bot username: `@YourBotName What is the capital of France?`
2. Reply to a previous bot message (threaded follow-up)
3. Prefix the message with the bot's first name followed by a separator (`:`, `,`, `-`, `—`): `YourBotName: summarize the last discussion`

Anything else is ignored silently. This keeps group conversations clean and avoids accidental model usage.

Tip: In Telegram you can enable "Always show username suggestions" so typing `@` quickly brings up the bot.

If you would like the bot to respond to all messages in a specific group, remove the guard logic in `bot/handlers.py` (search for `_is_addressed_in_group`) or adapt it to your preferred heuristics.

## API Documentation

When running, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Monitoring

### Metrics

Prometheus metrics available at: http://localhost:8000/metrics

Key metrics:
- `bot_messages_total` - Total messages processed
- `llm_request_duration_seconds` - LLM response time
- `bot_active_sessions` - Active user sessions
- `mcp_tool_calls_total` - MCP tool usage

### Health Check

Health check endpoint: http://localhost:8000/health

## Troubleshooting

### Common Issues

**Bot not responding:**
- Check if the bot token is correct
- Verify LLM server is running
- Check database connection
- Review logs for errors

**LLM errors:**
- Verify LLM server URL is correct
- Check if model is loaded
- Increase timeout if needed

**Database errors:**
- Ensure PostgreSQL is running
- Run migrations: `poetry run alembic upgrade head`
- Check connection string

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run code quality checks
6. Submit a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

## License

[Add your license here]

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: [DESIGN.md](./DESIGN.md)

## Roadmap

See [DESIGN.md - Development Roadmap](./DESIGN.md#development-roadmap) for planned features and timeline.

## Running with Mistral-Small-24B-Instruct-2501-3bit (MLX)

1. **Host requirements:** MacOS with Apple Silicon (M1/M2/M3).
2. **Build and run MLX FastAPI server:**
   ```bash
   cd docker/llm_mlx
   docker build -t llm_mlx_server .
   docker run --rm -p 8000:8000 -e MODEL_ID=mlx-community/Mistral-Small-24B-Instruct-2501-3bit llm_mlx_server
   ```
3. **Configure bot:** In `.env.docker-compose`:
   ```
   LLM_BASE_URL=http://llm_mlx_server:8000/v1
   LLM_MODEL_NAME=Mistral-Small-24B-Instruct-2501-3bit
   ```
4. **Restart bot container.**

**Note:** MLX models only run on MacOS/Apple Silicon. For Linux, use a Hugging Face transformers-compatible model.

## Automatic Tool Calling

- The bot passes available MCP tools to the LLM if the model supports OpenAI function calling.
- If the model does not support tools, a fallback heuristic triggers web search for queries like "search for ...".
- See `tests/test_tool_calling.py` for examples of both flows.
