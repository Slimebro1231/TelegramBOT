#!/bin/bash

echo "🚀 Starting Telegram Bot with Enhanced Conflict Resolution"
echo "⚡ Command-Only Mode: Bot responds only to /commands"
echo "============================================================"

# Function to kill all bot processes aggressively
cleanup_processes() {
    echo "🧹 Killing all existing bot processes..."
    
    # Kill all Python processes with bot.py
    pkill -9 -f "python.*bot.py" 2>/dev/null || true
    pkill -9 -f "bot.py" 2>/dev/null || true
    
    # Kill any processes using the bot token or telegram
    pkill -9 -f "telegram" 2>/dev/null || true
    pkill -9 -f "BOT_TOKEN" 2>/dev/null || true
    
    # Kill any Python processes in this directory
    for pid in $(ps aux | grep "python.*$(pwd)" | grep -v grep | awk '{print $2}'); do
        kill -9 $pid 2>/dev/null || true
    done
    
    echo "✅ Process cleanup complete"
}

# Function to clear Telegram webhook
clear_webhook() {
    echo "🧹 Clearing Telegram webhook..."
    
    if [ -f ".env" ]; then
        source .env
        if [ ! -z "$BOT_TOKEN" ]; then
            curl -s "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook" > /dev/null
            curl -s "https://api.telegram.org/bot$BOT_TOKEN/getUpdates?offset=-1" > /dev/null
            echo "✅ Webhook cleared"
        else
            echo "⚠️ BOT_TOKEN not found in .env"
        fi
    else
        echo "⚠️ .env file not found"
    fi
}

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️ Virtual environment not found (.venv)"
fi

# Enhanced cleanup sequence
echo "🔄 Starting enhanced cleanup sequence..."
for i in {1..3}; do
    echo "🔄 Cleanup round $i/3"
    cleanup_processes
    sleep 3
    clear_webhook
    sleep 2
    
    # Check if any bot processes are still running
    if pgrep -f "bot.py" > /dev/null; then
        echo "⚠️ Bot processes still detected, continuing cleanup..."
        sleep 5
    else
        echo "✅ No bot processes detected"
        break
    fi
done

# Wait for system to stabilize
echo "⏳ Waiting for system stabilization..."
sleep 5

# Final check and force kill if needed
if pgrep -f "bot.py" > /dev/null; then
    echo "🚨 Force killing remaining processes..."
    pkill -9 -f "bot.py" 2>/dev/null || true
    sleep 3
fi

echo "🎯 Starting bot with conflict-resistant configuration..."
echo "⌨️  Remember: Use 'next' to trigger immediate news, 'stop' to halt scheduler"
echo "============================================================"

# Start the bot with error handling
python bot.py 