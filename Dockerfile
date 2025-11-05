# Multi-stage build to reduce image size
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies in a virtual environment
RUN poetry config virtualenvs.create true \
    && poetry install --no-interaction --no-ansi --no-root --only main \
    && poetry export -f requirements.txt --output requirements.txt --without-hashes

# Production stage - only the runtime dependencies
FROM python:3.11-slim AS production

# Add a build argument for the version
ARG BOT_VERSION=unknown
ENV BOT_VERSION=${BOT_VERSION}

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy only the requirements.txt from builder
COPY --from=builder /app/requirements.txt ./

# Install only the necessary Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot/ ./bot/

# Create non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app && \
    mkdir -p /app/data /tmp/bot_workspace && \
    chown -R botuser:botuser /app/data /tmp/bot_workspace

USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "bot.main"]
