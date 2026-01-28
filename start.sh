#!/bin/bash

# Bio Dashboard Start Script
# Usage: ./start.sh [port]

PORT=${1:-8501}

echo "🚀 Starting Bio Dashboard..."
echo "📍 Port: $PORT"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit not found. Installing dependencies..."
    pip install -r requirements.txt
fi

# Kill existing process on port
lsof -ti:$PORT | xargs kill -9 2>/dev/null

# Start streamlit
echo "🌐 Access at: http://localhost:$PORT"
streamlit run app.py --server.port $PORT --server.headless true
