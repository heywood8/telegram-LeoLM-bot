# Makefile for Telegram LLM Bot

.PHONY: help install dev test lint format clean docker-build docker-up docker-down migrate

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	poetry install

dev: ## Install development dependencies
	poetry install --with dev

test: ## Run tests
	poetry run pytest -v --cov=bot --cov-report=term-missing

test-fast: ## Run tests without coverage
	poetry run pytest -v

lint: ## Run linters
	poetry run ruff check bot tests
	poetry run mypy bot

format: ## Format code
	poetry run black bot tests
	poetry run ruff check --fix bot tests

clean: ## Clean up cache and build files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name htmlcov -exec rm -rf {} +
	find . -type f -name .coverage -delete

docker-build: ## Build Docker image
	docker-compose build

docker-up: ## Start services with Docker Compose
	docker-compose up -d

docker-down: ## Stop services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f bot

migrate: ## Run database migrations
	poetry run alembic upgrade head

migrate-create: ## Create a new migration
	@read -p "Enter migration message: " msg; \
	poetry run alembic revision --autogenerate -m "$$msg"

run: ## Run the bot
	poetry run python -m bot.main

.DEFAULT_GOAL := help
