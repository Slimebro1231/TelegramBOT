#!/bin/bash

# Telegram Bot - API-Only Mode (Bitdeer DeepSeek-R1)
# Run this script to start your bot with Bitdeer DeepSeek-R1 API

echo "🚀 Starting Telegram Bot in API-Only Mode..."
echo "✅ Using Bitdeer DeepSeek-R1 API (no local dependencies)"

# Check if API key is set
if [ -z "$DEEPSEEK_API" ]; then
    echo "❌ Error: DEEPSEEK_API environment variable not set"
    echo "💡 Run: export DEEPSEEK_API=your_api_key_here"
    exit 1
fi

# Check if bot token is set
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Error: BOT_TOKEN environment variable not set"  
    echo "💡 Run: export BOT_TOKEN=your_bot_token_here"
    exit 1
fi

echo "🔑 API Key: ${DEEPSEEK_API:0:10}...${DEEPSEEK_API: -4}"
echo "🤖 Bot Token: ${BOT_TOKEN:0:10}...${BOT_TOKEN: -4}"
echo "🌐 Mode: API-Only (no local AI model required)"
echo ""
echo "💡 Available commands: /gold, /rwa, /bd, /meaning, /summary, /status"
echo "⚡ Command-only mode: Bot ignores non-command messages"
echo "📺 Channel: @Matrixdock_News (news posts every 30 minutes)"
echo ""
echo "🎯 Starting bot... (Press Ctrl+C to stop)"

# Start the bot
python bot.py 