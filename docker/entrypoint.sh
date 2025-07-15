#!/bin/bash

# Docker entrypoint script for social trend agent

set -e

echo "Starting Social Trend Agent..."

# Wait for any external dependencies if needed
echo "Checking dependencies..."

# Initialize database if needed
echo "Initializing database..."
python -c "
import asyncio
from trend_graph.database import init_database
asyncio.run(init_database())
print('Database initialized successfully')
"

# Run database migrations if any
echo "Running database migrations..."

# Start the application
echo "Starting application..."
exec "$@"

