# run_local.sh
# Run locally without Docker

#!/bin/bash

echo "🚀 Running NexusForge locally..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.example and add your GEMINI_API_KEY"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check API key
if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ GEMINI_API_KEY not set in .env"
    exit 1
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Start PostgreSQL and Redis (if not running)
echo "🗄️  Checking PostgreSQL..."
if ! pg_isready -h localhost -p 5432 &> /dev/null; then
    echo "⚠️  PostgreSQL not running. Start it with:"
    echo "   docker run -d -p 5432:5432 -e POSTGRES_USER=nexus -e POSTGRES_PASSWORD=nexusforge -e POSTGRES_DB=nexusforge postgres:15-alpine"
fi

echo "💾 Checking Redis..."
if ! redis-cli -h localhost -p 6379 ping &> /dev/null; then
    echo "⚠️  Redis not running. Start it with:"
    echo "   docker run -d -p 6379:6379 redis:7-alpine"
fi

# Run server
echo ""
echo "🚀 Starting backend server..."
echo "   API: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

