#!/bin/bash

# Update script for Social Trend Agent

set -e

echo "🔄 Updating Social Trend Agent..."

# Pull latest changes (if using git)
if [ -d .git ]; then
    echo "📥 Pulling latest changes..."
    git pull
fi

# Rebuild and restart services
echo "🔨 Rebuilding Docker images..."
docker-compose build --no-cache

echo "🔄 Restarting services..."
docker-compose down
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check health
echo "🔍 Checking service health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Update successful! Social Trend Agent is healthy."
else
    echo "❌ Update failed! Service is not responding."
    echo "Check logs with: docker-compose logs trend-agent"
    exit 1
fi

echo "🎉 Update complete!"

