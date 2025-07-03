#!/bin/bash
# VM Setup Helper Script
# This script helps automate the VM setup process

set -e  # Exit on any error

echo "🚀 Telegram Bot VM Setup Helper"
echo "================================="

# Function to check if running on VM or local machine
check_environment() {
    if [[ $(whoami) == "ubuntu" ]] && [[ -f /etc/lsb-release ]]; then
        echo "✅ Running on Ubuntu VM - proceeding with VM setup"
        return 0
    else
        echo "❌ This script should be run on the Ubuntu VM"
        echo "💡 Copy this script to your VM and run it there"
        exit 1
    fi
}

# Function to setup Python environment
setup_python() {
    echo "🐍 Setting up Python environment..."
    
    # Update system
    sudo apt update
    sudo apt install -y python3.11 python3.11-pip python3.11-venv git htop nano curl
    
    # Create virtual environment
    python3.11 -m venv .venv
    source .venv/bin/activate
    
    # Upgrade pip and install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo "✅ Python environment ready"
}

# Function to setup environment file
setup_env_file() {
    echo "🔧 Setting up environment file..."
    
    if [[ ! -f env_template.txt ]]; then
        echo "❌ env_template.txt not found. Make sure you've cloned the repository correctly."
        exit 1
    fi
    
    cp env_template.txt .env
    
    echo "📝 Please edit the .env file with your actual API keys:"
    echo "   nano .env"
    echo ""
    echo "Required values to replace:"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - DEEPSEEK_API"
    echo "   - TELEGRAM_CHANNEL_ID"
    echo ""
    read -p "Press Enter after you've edited the .env file..."
}

# Function to test bot
test_bot() {
    echo "🧪 Testing bot configuration..."
    
    source .venv/bin/activate
    
    echo "Starting bot test (will run for 10 seconds)..."
    timeout 10 python3 bot.py || true
    
    echo "✅ Bot test completed"
}

# Function to setup systemd service
setup_systemd() {
    echo "⚙️ Setting up systemd service..."
    
    BOT_PATH=$(pwd)
    
    sudo tee /etc/systemd/system/telegram-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram AI Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=$BOT_PATH
Environment=PATH=$BOT_PATH/.venv/bin
ExecStart=$BOT_PATH/.venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=append:$BOT_PATH/bot.log
StandardError=append:$BOT_PATH/bot.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable telegram-bot.service
    
    echo "✅ Systemd service configured"
}

# Function to setup auto-update script
setup_auto_update() {
    echo "🔄 Setting up auto-update script..."
    
    cat > ~/update_bot.sh <<'EOF'
#!/bin/bash
cd ~/TelegramBOT

echo "$(date): Starting bot update..." >> update.log

# Stop the bot
sudo systemctl stop telegram-bot.service

# Backup current .env
cp .env .env.backup

# Pull latest changes
git pull origin main

# Restore .env file
cp .env.backup .env

# Update dependencies if requirements.txt changed
source .venv/bin/activate
pip install -r requirements.txt

# Restart the bot
sudo systemctl start telegram-bot.service

echo "$(date): Bot update completed" >> update.log
EOF

    chmod +x ~/update_bot.sh
    echo "✅ Auto-update script created at ~/update_bot.sh"
}

# Function to setup monitoring
setup_monitoring() {
    echo "📊 Setting up monitoring..."
    
    cat > ~/monitor_bot.sh <<'EOF'
#!/bin/bash
SERVICE_NAME="telegram-bot.service"
LOG_FILE="~/TelegramBOT/monitor.log"

if ! systemctl is-active --quiet $SERVICE_NAME; then
    echo "$(date): Bot is down, restarting..." >> $LOG_FILE
    sudo systemctl start $SERVICE_NAME
    sleep 5
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "$(date): Bot restarted successfully" >> $LOG_FILE
    else
        echo "$(date): Failed to restart bot" >> $LOG_FILE
    fi
else
    echo "$(date): Bot is running normally" >> $LOG_FILE
fi
EOF

    chmod +x ~/monitor_bot.sh
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "*/5 * * * * ~/monitor_bot.sh") | crontab -
    
    echo "✅ Monitoring setup complete (checks every 5 minutes)"
}

# Function to start bot
start_bot() {
    echo "🚀 Starting bot..."
    
    sudo systemctl start telegram-bot.service
    sleep 3
    
    if systemctl is-active --quiet telegram-bot.service; then
        echo "✅ Bot started successfully!"
        echo ""
        echo "📊 Check status: sudo systemctl status telegram-bot.service"
        echo "📋 View logs: tail -f bot.log"
        echo "🔄 Update bot: ~/update_bot.sh"
    else
        echo "❌ Bot failed to start. Check logs:"
        echo "   sudo journalctl -u telegram-bot.service -n 20"
    fi
}

# Function to show final instructions
show_final_instructions() {
    echo ""
    echo "🎉 Setup Complete!"
    echo "=================="
    echo ""
    echo "Your bot is now running 24/7 on this VM."
    echo ""
    echo "📋 Useful commands:"
    echo "   sudo systemctl status telegram-bot.service  # Check bot status"
    echo "   sudo systemctl restart telegram-bot.service # Restart bot"
    echo "   tail -f bot.log                            # View live logs"
    echo "   ~/update_bot.sh                            # Update from GitHub"
}

# Main execution
main() {
    check_environment
    
    echo "Starting automated setup..."
    echo ""
    
    setup_python
    setup_env_file
    test_bot
    setup_systemd
    setup_auto_update
    setup_monitoring
    start_bot
    show_final_instructions
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 