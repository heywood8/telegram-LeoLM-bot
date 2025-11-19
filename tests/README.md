# Test Suite Documentation

This directory contains comprehensive tests for the Telegram LLM Bot.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test utilities
├── unit/                    # Unit tests (isolated component testing)
│   ├── test_rate_limiter.py
│   ├── test_session_manager.py
│   ├── test_llm_service.py
│   ├── test_mcp_manager.py
│   └── test_handlers.py
└── integration/             # Integration tests (cross-component testing)
    └── test_database.py
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Specific test file
pytest tests/unit/test_handlers.py

# Specific test function
pytest tests/unit/test_handlers.py::TestBotHandlers::test_start_command_sends_welcome_message
```

### Run with Coverage Report

```bash
# Terminal report
pytest --cov=bot --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=bot --cov-report=html
open htmlcov/index.html
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Only Fast Tests (Skip Slow Tests)

```bash
pytest -m "not slow"
```

## Test Coverage Goals

| Component | Target Coverage | Current Status |
|-----------|----------------|----------------|
| Rate Limiter | 90%+ | ✅ Comprehensive |
| Session Manager | 90%+ | ✅ Comprehensive |
| LLM Service | 85%+ | ✅ Comprehensive |
| MCP Manager | 90%+ | ✅ Comprehensive |
| Bot Handlers | 80%+ | ✅ Key paths covered |
| Database Models | 85%+ | ✅ Comprehensive |

## Test Fixtures

### Database Fixtures

- `test_db_engine` - In-memory SQLite database engine
- `test_db_session` - Async database session for testing
- `test_user` - Sample regular user
- `test_admin_user` - Sample admin user
- `test_session` - Sample conversation session
- `test_messages` - Sample conversation messages

### Telegram Fixtures

- `telegram_user` - Mock Telegram user object
- `telegram_admin_user` - Mock Telegram admin user
- `telegram_chat` - Mock private chat
- `telegram_group_chat` - Mock group chat
- `telegram_message` - Mock Telegram message
- `telegram_update` - Mock Telegram update
- `telegram_context` - Mock Telegram context

### Service Fixtures

- `mock_redis` - Mock Redis client with in-memory store
- `mock_llm_provider` - Mock LLM provider
- `mock_llm_provider_with_tools` - Mock LLM provider that returns tool calls
- `mock_mcp_plugin` - Mock MCP plugin
- `test_config` - Test configuration overrides

## Writing New Tests

### Unit Test Template

```python
import pytest

@pytest.mark.unit
class TestYourComponent:
    """Test YourComponent functionality"""

    @pytest.fixture
    def component(self):
        """Create component for testing"""
        return YourComponent()

    async def test_specific_behavior(self, component):
        """Test that component does X when Y"""
        result = await component.do_something()
        assert result == expected_value
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
class TestYourIntegration:
    """Test integration between components"""

    async def test_components_work_together(self, test_db_session):
        """Test that components A and B integrate correctly"""
        # Setup
        component_a = ComponentA(test_db_session)
        component_b = ComponentB(test_db_session)

        # Execute
        result = await component_a.process()
        final = await component_b.use_result(result)

        # Verify
        assert final == expected
```

## Test Best Practices

### 1. Test Isolation

Each test should be independent and not rely on other tests:

```python
# ✅ Good - each test creates its own data
async def test_creates_user(test_db_session):
    user = User(telegram_id=123)
    test_db_session.add(user)
    await test_db_session.commit()
    assert user.id is not None

# ❌ Bad - relies on test order
global_user = None

async def test_creates_user(test_db_session):
    global global_user
    global_user = User(telegram_id=123)
    test_db_session.add(global_user)

async def test_updates_user(test_db_session):
    global_user.username = "new"  # Depends on previous test
```

### 2. Clear Test Names

Test names should describe what is being tested:

```python
# ✅ Good - describes behavior
async def test_rate_limiter_blocks_after_exceeding_limit():
    pass

# ❌ Bad - unclear what is tested
async def test_rate_limiter():
    pass
```

### 3. Arrange-Act-Assert Pattern

```python
async def test_something():
    # Arrange - set up test data
    user = User(telegram_id=123)

    # Act - perform the action
    result = await process_user(user)

    # Assert - verify the outcome
    assert result.success is True
```

### 4. Mock External Dependencies

```python
# ✅ Good - mocks external Redis
async def test_with_mock_redis(mock_redis):
    rate_limiter = RateLimiter()
    rate_limiter._redis = mock_redis
    # Test proceeds without real Redis

# ❌ Bad - requires real Redis running
async def test_with_real_redis():
    rate_limiter = RateLimiter()
    # Connects to real Redis
```

### 5. Test Edge Cases

```python
async def test_handles_empty_input():
    """Test with empty string"""
    result = await process_message("")
    assert result is not None

async def test_handles_very_long_input():
    """Test with maximum length input"""
    long_text = "x" * 10000
    result = await process_message(long_text)
    assert result is not None

async def test_handles_special_characters():
    """Test with special characters"""
    result = await process_message("Test\n\r\t\0")
    assert result is not None
```

## Continuous Integration

Tests are automatically run on:

- Every pull request
- Every commit to main branch
- Scheduled daily runs

### CI Configuration

See `.github/workflows/test.yml` for the CI pipeline configuration.

## Debugging Failed Tests

### Verbose Output

```bash
pytest -vv tests/unit/test_handlers.py::test_specific_function
```

### Show Print Statements

```bash
pytest -s tests/unit/test_handlers.py
```

### Drop into Debugger on Failure

```bash
pytest --pdb
```

### Show Locals on Failure

```bash
pytest -l
```

## Coverage Reports

### Viewing Coverage

After running tests with coverage:

```bash
pytest --cov=bot --cov-report=html
```

Open `htmlcov/index.html` in your browser to see:
- Line-by-line coverage
- Branch coverage
- Missing lines highlighted
- Coverage by file

### Coverage Targets

- **Critical components** (handlers, session manager): 90%+
- **Core services** (LLM service, MCP manager): 85%+
- **Utilities** (rate limiter, config): 80%+

## Performance Testing

### Benchmark Tests

```bash
# Run with timing information
pytest --durations=10
```

This shows the 10 slowest tests.

### Marking Slow Tests

```python
@pytest.mark.slow
async def test_expensive_operation():
    """This test takes a while"""
    # Long-running test
```

Skip slow tests during development:

```bash
pytest -m "not slow"
```

## Testing Async Code

All async functions must use `async def` and `await`:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

The `pytest.ini` file configures `asyncio_mode = auto`, so the `@pytest.mark.asyncio` decorator is optional.

## Common Issues and Solutions

### Issue: Tests Fail Due to Database State

**Solution:** Use fixtures that reset database state:

```python
async def test_something(test_db_session):
    # test_db_session is fresh for each test
    # No cleanup needed
```

### Issue: Redis Connection Errors

**Solution:** Use `mock_redis` fixture instead of real Redis:

```python
async def test_something(mock_redis):
    rate_limiter = RateLimiter()
    rate_limiter._redis = mock_redis
```

### Issue: Flaky Tests (Pass Sometimes, Fail Sometimes)

**Solutions:**
- Check for race conditions in async code
- Ensure proper test isolation
- Mock time-dependent operations
- Use deterministic test data

### Issue: Import Errors

**Solution:** Ensure you're running pytest from the project root:

```bash
cd /path/to/telegram-LeoLM-bot
pytest
```

## Contributing Tests

When adding new features:

1. Write tests first (TDD approach)
2. Ensure new code has >80% coverage
3. Include both positive and negative test cases
4. Test edge cases and error conditions
5. Update this documentation if adding new test patterns

## Questions?

If you have questions about the test suite, please:

1. Check this documentation
2. Review existing tests for patterns
3. Ask in the development channel
4. Open an issue on GitHub
