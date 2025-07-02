#!/bin/bash
set -e

echo "🚀 Starting Bitdeer VPC Deployment for Telegram AI Bot"
echo "================================================="

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-pip python3.11-venv git htop screen curl nano ufw

# Create bot user and directory
echo "👤 Setting up bot user and directory..."
sudo useradd -m -s /bin/bash telegram-bot || echo "User already exists"
sudo mkdir -p /opt/telegram-bot
sudo chown telegram-bot:telegram-bot /opt/telegram-bot

# Clone repository (you'll need to update the URL)
echo "📥 Cloning repository..."
cd /opt/telegram-bot
if [ ! -d ".git" ]; then
    echo "Please manually clone your repository:"
    echo "sudo su - telegram-bot"
    echo "cd /opt/telegram-bot"
    echo "git clone https://github.com/YOUR_USERNAME/TelegramBOT.git ."
fi

# Set up Python environment
echo "🐍 Setting up Python environment..."
sudo su - telegram-bot -c "cd /opt/telegram-bot && python3.11 -m venv .venv"
sudo su - telegram-bot -c "cd /opt/telegram-bot && source .venv/bin/activate && pip install --upgrade pip"

# Install requirements if they exist
if [ -f "/opt/telegram-bot/requirements.txt" ]; then
    echo "📋 Installing Python dependencies..."
    sudo su - telegram-bot -c "cd /opt/telegram-bot && source .venv/bin/activate && pip install -r requirements.txt"
fi

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/telegram-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram AI Bot
After=network.target

[Service]
Type=simple
User=telegram-bot
WorkingDirectory=/opt/telegram-bot
Environment=PATH=/opt/telegram-bot/.venv/bin
ExecStart=/opt/telegram-bot/.venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable service (but don't start yet - need environment variables)
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot

# Set up basic firewall
echo "🔒 Configuring firewall..."
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow out 443
echo "⚠️  Remember to allow SSH from your IP: sudo ufw allow from YOUR_IP to any port 22"

# Create environment template
echo "📝 Creating environment template..."
sudo su - telegram-bot -c "cat > /opt/telegram-bot/.env.template << 'EOF'
BOT_TOKEN=your_telegram_bot_token_here
DEEPSEEK_API_KEY=your_bitdeer_api_key_here
CHANNEL_ID=@your_channel_id_here
DEBUG_MODE=false
ENVIRONMENT=production
EOF"

echo "✅ Deployment setup complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Configure environment variables:"
echo "   sudo su - telegram-bot"
echo "   cd /opt/telegram-bot"
echo "   cp .env.template .env"
echo "   nano .env  # Add your real credentials"
echo ""
echo "2. Start the bot:"
echo "   sudo systemctl start telegram-bot"
echo "   sudo systemctl status telegram-bot"
echo ""
echo "3. Monitor logs:"
echo "   sudo journalctl -u telegram-bot -f"
echo ""
echo "4. Set up SSH access from your local machine (replace YOUR_IP):"
echo "   sudo ufw allow from YOUR_IP to any port 22" 