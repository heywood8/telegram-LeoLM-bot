# Contributing to Telegram LLM Bot

Thank you for your interest in contributing to this project!

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd telegram-llm-bot
   ```

2. **Install Poetry (preferred)**:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
   If Poetry installation is not available in your environment, you can fall back to plain `pip`:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt  # Generate this with: poetry export -f requirements.txt --without-hashes > requirements.txt
   ```

3. **Install dependencies (Poetry)**:
   ```bash
   poetry install
   ```

4. **Set up pre-commit hooks**:
   ```bash
   poetry run pre-commit install
   ```

5. **Create `.env` file**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Copilot Instructions

- Avoid combining commands with pipes when using Copilot Chat (for example, `command | grep`). Copilot treats each segment after a pipe as a separate command, which triggers additional approval prompts and slows workflows. Run the primary command first, then apply any filtering separately if needed.

## Code Style

We use the following tools for code quality:

- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Run all checks:
```bash
poetry run black .
poetry run ruff check .
poetry run mypy bot
```

## Testing

Run tests:
```bash
# All tests
poetry run pytest

# With coverage (HTML report)
poetry run pytest --cov=bot --cov-report=html

# Specific test file
poetry run pytest tests/test_session.py -v

# If using pip instead of Poetry
pytest -q
```

## Creating a Custom MCP

1. Create a new file in `bot/mcp/plugins/`:

```python
from bot.mcp.base import BaseMCP
from typing import Dict, Any, List, Optional

class MyCustomMCP(BaseMCP):
    version = "1.0.0"
    description = "Description of your MCP"
    
    async def initialize(self) -> bool:
        # Initialize resources
        return True
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        # Return tool definitions
        return []
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        # Execute tool logic
        pass
    
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        # Provide context
        return {}
```

2. Register your MCP in `bot/main.py`

3. Add tests in `tests/test_mcp.py` (or create a new file `tests/test_<your_mcp>.py`)

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for new functionality
5. Run code quality checks
6. Commit your changes: `git commit -m "Add feature: description"`
7. Push to your fork: `git push origin feature/my-feature`
8. Open a Pull Request

## Pull Request Guidelines

- Write clear, descriptive commit messages
- Add tests for new features (unit + minimal integration where meaningful)
- Update documentation as needed
- Ensure all tests pass
- Keep changes focused and atomic
- Reference related issues

## Code Review

All submissions require review. We'll review your PR and may request changes.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
