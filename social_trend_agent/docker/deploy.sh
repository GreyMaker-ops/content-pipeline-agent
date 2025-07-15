#!/bin/bash

# Deployment script for Social Trend Agent

set -e

echo "🚀 Deploying Social Trend Agent..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running!"
    echo "Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed!"
    echo "Please install docker-compose and try again."
    exit 1
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check health
echo "🔍 Checking service health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Social Trend Agent API is healthy!"
else
    echo "❌ Social Trend Agent API is not responding!"
    echo "Check logs with: docker-compose logs trend-agent"
fi

if curl -f http://localhost:9090 > /dev/null 2>&1; then
    echo "✅ Prometheus is running!"
else
    echo "❌ Prometheus is not responding!"
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Grafana is running!"
else
    echo "❌ Grafana is not responding!"
fi

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📊 Access points:"
echo "  • API: http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • Health: http://localhost:8000/health"
echo "  • Prometheus: http://localhost:9090"
echo "  • Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "📝 Useful commands:"
echo "  • View logs: docker-compose logs -f"
echo "  • Stop services: docker-compose down"
echo "  • Restart: docker-compose restart"
echo "  • Update: ./docker/update.sh"
echo ""

