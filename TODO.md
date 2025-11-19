# TODO: Bot Improvements

This document tracks improvements identified during the code review and their implementation status.

## ✅ Completed

### P0: Add Comprehensive Test Coverage
**Status:** ✅ Complete (Implemented 2024)

- [x] Create test infrastructure (pytest.ini, conftest.py)
- [x] Write unit tests for rate limiter (11 tests, 98% coverage)
- [x] Write unit tests for session manager (16 tests, 60% coverage)
- [x] Write unit tests for LLM service (17 tests, 95% coverage)
- [x] Write unit tests for MCP manager (21 tests, 96% coverage)
- [x] Write unit tests for bot handlers (22 tests)
- [x] Write integration tests for database (15 tests, 100% model coverage)
- [x] Create comprehensive test documentation (tests/README.md)
- [x] Add aiosqlite dependency for test database

**Result:** 102 tests, 25% baseline coverage, 88-100% on critical components

---

## 🔴 P1: High Priority Improvements

### 1. Refactor Monolithic `handle_message` Function
**File:** `bot/handlers.py:159-618`
**Priority:** P1
**Effort:** Medium
**Impact:** High

**Current Issue:**
- `handle_message` is 459 lines long with 10+ responsibilities
- Handles system prompts, rate limiting, session management, LLM calls, tool execution, response formatting
- Complex nested conditionals make it difficult to test, debug, and maintain

**Tasks:**
- [ ] Extract `_handle_system_prompt_update()` method (lines 167-227)
- [ ] Extract `_clean_message_text()` method (lines 229-237)
- [ ] Extract `_check_group_chat_addressing()` method (lines 239-297)
- [ ] Extract `_check_rate_limit()` method (lines 299-308)
- [ ] Extract `_process_llm_request()` method (lines 318-548)
- [ ] Extract `_send_response()` method (lines 578-618)
- [ ] Add unit tests for each extracted method
- [ ] Verify refactoring with existing test suite

**Success Criteria:**
- `handle_message` reduced to <100 lines (orchestrator only)
- Each method has single responsibility
- Test coverage increases to 60%+

**Reference:** See TEST_IMPLEMENTATION_SUMMARY.md "Top 5 Improvements #2"

---

### 2. Improve Error Handling and Resilience
**Priority:** P1
**Effort:** Medium
**Impact:** High

**Current Issues:**

#### a) No Retry Logic for LLM Calls
**File:** `bot/llm/service.py:111-117`

- [ ] Add retry decorator using `tenacity` library
- [ ] Implement exponential backoff (3 attempts, 2s-10s wait)
- [ ] Add circuit breaker pattern (5 failures, 60s recovery)
- [ ] Log retry attempts for monitoring

#### b) Database Session Management Issues
**File:** `bot/handlers.py:134-139, 320-336`

- [ ] Refactor to reuse database session across handler lifecycle
- [ ] Pass `db` session to BotHandlers constructor
- [ ] Remove repeated `async_session_factory()` calls
- [ ] Add connection pool monitoring

#### c) Tool Call Failures Not Gracefully Handled
**File:** `bot/handlers.py:396-401`

- [ ] Implement retry strategy for failed tool calls
- [ ] Add fallback responses when all tools fail
- [ ] Log tool failures for debugging
- [ ] Add timeout enforcement for tool execution

#### d) Add Timeout Enforcement
**Files:** `bot/llm/provider.py`, `bot/handlers.py`

- [ ] Add timeout to LLM requests (config: `LLM_REQUEST_TIMEOUT=30s`)
- [ ] Add timeout to tool execution (config: `TOOL_EXECUTION_TIMEOUT=15s`)
- [ ] Use `asyncio.timeout()` context manager
- [ ] Return user-friendly timeout errors

**Dependencies:**
```bash
poetry add tenacity circuitbreaker
```

**Success Criteria:**
- LLM calls retry on transient failures
- Circuit breaker prevents cascade failures
- All async operations have timeouts
- Database sessions properly reused

**Reference:** See TEST_IMPLEMENTATION_SUMMARY.md "Top 5 Improvements #3"

---

## 🟡 P2: Medium Priority Improvements

### 3. Enhance Security and Input Validation
**Priority:** P2
**Effort:** Low-Medium
**Impact:** Medium-High

**Current Issues:**

#### a) Weak Admin Authentication
**File:** `bot/handlers.py:66-70, 87-90`

- [ ] Create `bot/auth.py` module with `AdminAuth` class
- [ ] Add session validation for admin actions
- [ ] Implement audit logging for admin commands
- [ ] Track admin sessions with timeout
- [ ] Add test suite for admin authentication

#### b) No Input Validation
**File:** `bot/handlers.py:163`

- [ ] Create `bot/validators.py` with Pydantic models
- [ ] Add `MessageInput` validator with max length (4096)
- [ ] Sanitize control characters and null bytes
- [ ] Validate message content before processing
- [ ] Add tests for input validation

#### c) SQL Injection Risk
**File:** `bot/handlers.py:201-203`

- [ ] Replace raw SQL with SQLAlchemy ORM:
  ```python
  # Replace this:
  await db.execute(text("UPDATE system_prompts SET is_active = false..."))

  # With this:
  await db.execute(
      update(SystemPrompt)
      .where(SystemPrompt.is_active == True)
      .values(is_active=False)
  )
  ```

#### d) No Rate Limiting on Admin Commands

- [ ] Add rate limiting to `/set_system_prompt` command
- [ ] Add rate limiting to `/get_system_prompt` command
- [ ] Configure separate admin rate limits
- [ ] Add config: `RATE_LIMIT_ADMIN_REQUESTS=10`
- [ ] Add config: `RATE_LIMIT_ADMIN_WINDOW=60`

**Success Criteria:**
- Admin actions require session validation + audit logging
- All user input validated with Pydantic
- No raw SQL queries in codebase
- Admin commands rate-limited
- Security tests passing

**Reference:** See TEST_IMPLEMENTATION_SUMMARY.md "Top 5 Improvements #4"

---

### 4. Add Observability and Monitoring
**Priority:** P2
**Effort:** Medium
**Impact:** Medium

**Current State:**
- Only structured logging (structlog)
- No metrics collection
- No distributed tracing
- No cost tracking
- No health checks for dependencies

**Tasks:**

#### a) Add Prometheus Metrics
- [ ] Create `bot/metrics.py` module
- [ ] Add metrics:
  - `bot_messages_total` (counter by status, chat_type)
  - `bot_llm_latency_seconds` (histogram by model, has_tools)
  - `bot_tool_calls_total` (counter by tool_name, status)
  - `bot_active_sessions` (gauge)
  - `bot_rate_limit_exceeded_total` (counter)
- [ ] Add Prometheus HTTP endpoint `/metrics`
- [ ] Add dependency: `poetry add prometheus-client`

#### b) Add Health Check Endpoints
- [ ] Create `bot/health.py` module
- [ ] Add `/health` endpoint (liveness check)
- [ ] Add `/health/ready` endpoint (readiness check)
  - Check database connectivity
  - Check Redis connectivity
  - Check LLM provider health
- [ ] Return proper HTTP status codes (200 vs 503)
- [ ] Add health check tests

#### c) Add Cost Tracking
- [ ] Create `bot/cost_tracker.py` module
- [ ] Track token usage per user
- [ ] Calculate costs based on pricing table
- [ ] Store in Redis: `costs:user:{id}`
- [ ] Add `/admin/costs` endpoint for cost report
- [ ] Log high-cost operations

#### d) Add Request Tracing
- [ ] Create `bot/tracing.py` module
- [ ] Add request ID to all log messages
- [ ] Use `contextvars` for request context
- [ ] Include request ID in error responses
- [ ] Add correlation across tool calls

**Configuration:**
```env
# Add to .env.example
METRICS_ENABLED=true
METRICS_PORT=9090
HEALTH_CHECK_ENABLED=true
COST_TRACKING_ENABLED=true
```

**Success Criteria:**
- Prometheus metrics exported on `/metrics`
- Health checks return accurate status
- Token usage tracked per user
- All requests have unique trace IDs
- Metrics visible in Grafana (optional)

**Reference:** See TEST_IMPLEMENTATION_SUMMARY.md "Top 5 Improvements #5"

---

## 🔵 P3: Nice-to-Have Improvements

### 5. Increase Test Coverage
**Priority:** P3
**Effort:** Low (incremental)

- [ ] Fix 49 test fixture dependency errors
- [ ] Fix 7 failing unit tests
- [ ] Increase handler coverage from 15% to 60%+
- [ ] Add end-to-end tests for message flow with tools
- [ ] Add performance/load tests for rate limiter
- [ ] Set up mutation testing

**Target:** 80%+ overall coverage, 95%+ test pass rate

---

### 6. CI/CD Integration
**Priority:** P3
**Effort:** Low

- [ ] Create `.github/workflows/test.yml`
- [ ] Run tests on every PR
- [ ] Run tests on every commit to main
- [ ] Generate and upload coverage reports
- [ ] Set up Codecov integration
- [ ] Add test status badge to README
- [ ] Block PRs with failing tests

---

### 7. Documentation Improvements
**Priority:** P3
**Effort:** Low

- [ ] Add docstrings to all public methods
- [ ] Generate API documentation with Sphinx
- [ ] Add architecture diagrams
- [ ] Create troubleshooting guide
- [ ] Document common error scenarios
- [ ] Add contribution guidelines for tests

---

## 📊 Progress Tracking

| Priority | Item | Status | Coverage | ETA |
|----------|------|--------|----------|-----|
| P0 | Test Coverage | ✅ Complete | 25% baseline | Done |
| P1 | Refactor Handlers | 🔴 Pending | - | TBD |
| P1 | Error Handling | 🔴 Pending | - | TBD |
| P2 | Security | 🔴 Pending | - | TBD |
| P2 | Observability | 🔴 Pending | - | TBD |
| P3 | Test Coverage 80%+ | 🔴 Pending | 25% → 80% | TBD |
| P3 | CI/CD | 🔴 Pending | - | TBD |
| P3 | Documentation | 🔴 Pending | - | TBD |

---

## 🎯 Next Steps

**Recommended Order:**
1. ✅ **P0 Complete** - Test coverage foundation
2. **P1.1** - Refactor `handle_message` (enables easier testing)
3. **P1.2** - Add error handling & resilience (improves reliability)
4. **P2.1** - Enhance security (hardens production)
5. **P2.2** - Add observability (enables monitoring)
6. **P3** - Incremental improvements (ongoing)

**Estimated Timeline:**
- P1: 2-3 days (if done together)
- P2: 2-3 days (if done together)
- P3: Ongoing (1-2 hours per improvement)

**Total estimated effort:** 1-2 weeks for P1-P2

---

## 📚 References

- **TEST_IMPLEMENTATION_SUMMARY.md** - Detailed P0 implementation report
- **tests/README.md** - Test suite documentation
- **DESIGN.md** - Architecture documentation
- **Code Review** - Original improvement recommendations

---

## 📝 Notes

- All improvements should include tests
- Update this file as items are completed
- Add new issues as they're discovered
- Link to relevant PRs when implemented

**Last Updated:** 2024 (after P0 completion)
