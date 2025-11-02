#!/bin/bash
# Quick start script for development

set -e

echo "🚀 Starting Telegram LLM Bot Setup..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your Telegram bot token and other settings!"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
poetry install

# Start services
echo "🐳 Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Start bot
echo "🤖 Starting bot..."
poetry run python -m bot.main
