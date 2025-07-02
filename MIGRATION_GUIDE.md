# Bitdeer Cloud Migration Guide
*Step-by-step guide for migrating the Telegram AI Bot to Bitdeer cloud*  
_Updated: 26 Jun 2025_

---

## Migration Overview

**Current State**: Local development with Ollama + R1-14B model  
**Target State**: Bitdeer cloud with managed DeepSeek AI API + scalable bot deployment  
**Migration Strategy**: Blue/Green deployment (parallel systems, gradual cutover)

**✅ Simplifications:**
- **No model migration needed** - Using Bitdeer's managed DeepSeek API
- **GitHub already exists** - Deploy directly from repository
- **Faster migration** - No large model files to upload

---

## Phase 1: Pre-Migration Setup (Day 1)

### 1.1 Local Environment Preparation
```bash
# 1. Backup current system
cp -r TelegramBOT TelegramBOT_backup_$(date +%Y%m%d)

# 2. Create cloud deployment branch
git checkout -b cloud-deployment

# 3. Export current news database
cp news_tracker.json news_tracker_backup.json
python -c "
import json
with open('news_tracker.json', 'r') as f:
    data = json.load(f)
print(f'Articles to migrate: {len(data.get(\"posted_articles\", {}))}')
"

# 4. Commit current state to GitHub
git add . && git commit -m "Pre-migration backup"
git push origin cloud-deployment
```

### 1.2 Bitdeer Account Setup
1. **Access Bitdeer Console**: Log into your Bitdeer dashboard
2. **Create Project**: Set up new project "telegram-ai-bot"  
3. **Configure Billing**: Set up budget alerts at $400/month
4. **AI API Access**: Navigate to **AI Services** → **DeepSeek API**
   - Enable DeepSeek model access
   - Generate API token for bot usage
   - Note the API endpoint URL

### 1.3 GitHub Integration Setup
```bash
# Set up Bitdeer integration with your existing GitHub repo
# 1. In Bitdeer Console → DevOps → GitHub Integration
# 2. Connect your GitHub account
# 3. Select your TelegramBOT repository  
# 4. Configure deployment triggers (push to main/cloud-deployment)
```

---

## Phase 2: AI Service Configuration (Day 1) ⚡ SIMPLIFIED

### 2.1 Bitdeer AI API Setup
1. **Navigate to AI Services** → **Model APIs** → **DeepSeek**
2. **Create API Key**: Generate production API key
3. **Test API Access**:
```bash
# Test Bitdeer's DeepSeek API
curl -X POST https://api.bitdeer.com/ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_BITDEER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Test response for migration"}],
    "max_tokens": 100
  }'
```

### 2.2 Model Selection & Configuration
**Available DeepSeek Models on Bitdeer:**
- `deepseek-chat` - General conversation (recommended)
- `deepseek-coder` - Code-focused
- `deepseek-math` - Math/reasoning focused

**Choose model based on your needs:**
- For financial analysis: `deepseek-chat` (best reasoning)
- For mixed content: `deepseek-chat` (most versatile)

### 2.3 Performance & Pricing Check
```bash
# Test response times and pricing
time curl -X POST https://api.bitdeer.com/ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_BITDEER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Analyze gold market trends"}]
  }'
```

---

## Phase 3: Database Migration (Day 1-2)

### 3.1 Database Service Setup
1. **Create Database**: PostgreSQL instance on Bitdeer
   - **Size**: Small instance (can scale later)
   - **Location**: Same region as your compute
   - **Backup**: Enable daily automated backups

```sql
-- PostgreSQL schema (unchanged from original)
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    hash VARCHAR(32) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source VARCHAR(255),
    url TEXT,
    content TEXT,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    category VARCHAR(100),
    is_duplicate BOOLEAN DEFAULT FALSE,
    similarity_reason TEXT,
    relevance_score INTEGER
);

CREATE INDEX idx_articles_hash ON articles(hash);
CREATE INDEX idx_articles_posted_at ON articles(posted_at);
```

### 3.2 Data Migration Script (Same as before)
```python
# migrate_data.py - Run this from your local machine
import json
import asyncio
import asyncpg
from datetime import datetime

async def migrate_news_tracker():
    # Load local data
    with open('news_tracker.json', 'r') as f:
        data = json.load(f)
    
    # Connect to Bitdeer database
    conn = await asyncpg.connect(
        host="your-db.bitdeer.com",
        database="telegram_bot",
        user="bot_user",
        password="your_db_password"
    )
    
    # Migrate articles
    articles = data.get('posted_articles', {})
    for hash_key, article in articles.items():
        await conn.execute("""
            INSERT INTO articles (hash, title, source, url, posted_at, published_at, category, is_duplicate, similarity_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (hash) DO NOTHING
        """, 
        hash_key, article['title'], article.get('source'), article.get('url'),
        datetime.fromisoformat(article['posted_at']), 
        datetime.fromisoformat(article['published_at']) if article.get('published_at') else None,
        article.get('category'), article.get('is_duplicate', False), article.get('similarity_reason')
        )
    
    await conn.close()
    print(f"Migrated {len(articles)} articles to cloud database")

if __name__ == "__main__":
    asyncio.run(migrate_news_tracker())
```

---

## Phase 4: Code Updates for Bitdeer API (Day 2) ⚡ SIMPLIFIED

### 4.1 Update AI Client for Bitdeer DeepSeek API
```python
# cloud_ai_client.py - Replace Ollama with Bitdeer API
import aiohttp
import asyncio
import os

class BitdeerAIClient:
    def __init__(self, api_key: str, base_url: str = "https://api.bitdeer.com/ai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = "deepseek-chat"  # or deepseek-coder
    
    async def chat(self, messages: list, max_tokens: int = 1000) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions", 
                headers=headers, 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"Bitdeer API error {response.status}: {error_text}")
```

### 4.2 Update bot.py for Cloud Environment
```python
# Add to bot.py - Cloud configuration detection
import os

# Cloud environment detection
IS_CLOUD = os.getenv("DEPLOYMENT_ENV") == "cloud"

# AI Configuration
if IS_CLOUD:
    BITDEER_API_KEY = os.getenv("BITDEER_API_KEY")
    BITDEER_API_URL = os.getenv("BITDEER_API_URL", "https://api.bitdeer.com/ai/v1")
    
    # Database configuration
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME") 
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
else:
    # Local development settings (unchanged)
    MODEL_NAME = "r1-assistant"

# Update get_ai_response function
async def get_ai_response(prompt: str, context: str = "", command: str = "chat") -> str:
    """Get response from AI model - cloud or local."""
    try:
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        if IS_CLOUD:
            # Use Bitdeer DeepSeek API
            ai_client = BitdeerAIClient(BITDEER_API_KEY, BITDEER_API_URL)
            
            response = await ai_client.chat(
                messages=[{'role': 'user', 'content': full_prompt}],
                max_tokens=1000
            )
            
            ai_response = response['choices'][0]['message']['content']
            print(f"✅ Bitdeer API response: {len(ai_response)} chars")
            
        else:
            # Existing local Ollama code
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: ollama.chat(
                    model=MODEL_NAME,
                    messages=[{'role': 'user', 'content': full_prompt}]
                )
            )
            ai_response = response['message']['content']
        
        # Same response processing logic for both cloud and local
        ai_response = extract_final_response(ai_response)
        
        if len(ai_response) > MAX_MESSAGE_LENGTH:
            ai_response = ai_response[:MAX_MESSAGE_LENGTH-50] + "...\n\n[Response truncated]"
            
        bot_status.log_ai_response()
        return ai_response
        
    except Exception as e:
        bot_status.log_error()
        print(f"❌ AI Error: {e}")
        return None  # Fallback content will be used
```

### 4.3 Update requirements.txt
```txt
# Add to requirements.txt
python-telegram-bot==22.1
python-dotenv==1.0.1
requests==2.31.0
aiohttp==3.10.10
psutil==5.9.8
feedparser==6.0.11
beautifulsoup4==4.12.3
lxml==5.3.0
pytz==2024.1
asyncpg==0.29.0  # For PostgreSQL
```

### 4.4 Update Database Integration
```python
# Add to bot.py - Cloud database integration
if IS_CLOUD:
    from cloud_database import CloudNewsTracker
    
    # Initialize cloud database
    DB_CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    news_tracker = CloudNewsTracker(DB_CONNECTION_STRING)
    
    async def initialize_cloud_database():
        await news_tracker.initialize()
        print("✅ Cloud database connected")
```

---

## Phase 5: Deployment Configuration (Day 2-3)

### 5.1 Environment Variables for Bitdeer
```bash
# .env.cloud (for reference - don't commit to GitHub)
DEPLOYMENT_ENV=cloud
BOT_TOKEN=your_telegram_bot_token

# Bitdeer AI API
BITDEER_API_KEY=your_bitdeer_api_key
BITDEER_API_URL=https://api.bitdeer.com/ai/v1

# Database (Bitdeer will provide these)
DB_HOST=your-postgres.bitdeer.com
DB_NAME=telegram_bot
DB_USER=bot_user
DB_PASSWORD=secure_password

# Bot Configuration
CHANNEL_ID=@Matrixdock_News
NEWS_INTERVAL=1800
INSTANCE_ROLE=user_handler  # or news_publisher
```

### 5.2 Dockerfile for Bitdeer Deployment
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables will be injected by Bitdeer
ENV DEPLOYMENT_ENV=cloud

# Health check endpoint (add to bot.py)
EXPOSE 8080

# Start bot
CMD ["python", "bot.py"]
```

### 5.3 GitHub Actions for Bitdeer Deployment (Optional)
```yaml
# .github/workflows/deploy-bitdeer.yml
name: Deploy to Bitdeer

on:
  push:
    branches: [ main, cloud-deployment ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and deploy to Bitdeer
      run: |
        # Use Bitdeer CLI or API to deploy
        # This will be configured based on Bitdeer's deployment method
        echo "Deploying to Bitdeer..."
```

---

## Phase 6: Testing & Validation (Day 3)

### 6.1 Local Testing with Bitdeer API
```bash
# Test locally with Bitdeer API before deploying
export DEPLOYMENT_ENV=cloud
export BITDEER_API_KEY=your_api_key
export BITDEER_API_URL=https://api.bitdeer.com/ai/v1

# Test locally to ensure API integration works
python bot.py
```

### 6.2 Deployment to Bitdeer Staging
1. **Deploy from GitHub**: Use Bitdeer's GitHub integration
2. **Configure Environment Variables** in Bitdeer console
3. **Test API endpoints** and database connectivity
4. **Validate bot responses** using test commands

### 6.3 Performance Comparison
```python
# Compare response times: Local Ollama vs Bitdeer API
import time
import asyncio

async def test_performance():
    start_time = time.time()
    
    # Test Bitdeer API response time
    response = await get_ai_response("Analyze gold market trends")
    
    end_time = time.time()
    print(f"Bitdeer API response time: {end_time - start_time:.2f} seconds")
    print(f"Response length: {len(response)} characters")
```

---

## Phase 7: Go-Live Migration (Day 3-4)

### 7.1 Parallel Testing Setup
```bash
# Keep local bot running while testing Bitdeer deployment
# Local bot: Continue serving users (polling mode)
# Bitdeer bot: Test mode with webhook to different endpoint

# Test Bitdeer bot with specific test commands
curl -X POST https://api.telegram.org/bot$BOT_TOKEN/sendMessage \
  -d "chat_id=YOUR_TEST_CHAT_ID" \
  -d "text=/status - Testing Bitdeer deployment"
```

### 7.2 Migration Strategy (Simplified)
**Recommended: Direct Cutover** (since no model files to sync)
1. **Stop local bot**: `pkill -f bot.py`
2. **Clear webhook**: `curl "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook"`
3. **Set webhook to Bitdeer**: Point to your Bitdeer app endpoint
4. **Monitor performance**: Watch for any issues

### 7.3 Webhook Configuration for Production
```bash
# Set webhook to point to your Bitdeer deployment
curl -X POST https://api.telegram.org/bot$BOT_TOKEN/setWebhook \
  -d "url=https://your-bot-app.bitdeer.com/webhook" \
  -d "drop_pending_updates=true"

# Verify webhook is working
curl https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo
```

---

## Simplified Migration Checklist ✅

### Pre-Migration (Day 1)
- [ ] ✅ Backup current system and push to GitHub
- [ ] ✅ Set up Bitdeer account and AI API access  
- [ ] ✅ Test Bitdeer DeepSeek API connectivity
- [ ] ✅ Create PostgreSQL database on Bitdeer

### Core Migration (Day 2)
- [ ] ✅ Update bot code for Bitdeer API integration
- [ ] ✅ Migrate news database to PostgreSQL
- [ ] ✅ Configure environment variables
- [ ] ✅ Test locally with Bitdeer API

### Deployment (Day 3)
- [ ] ✅ Deploy to Bitdeer from GitHub
- [ ] ✅ Configure production environment variables
- [ ] ✅ Test all bot commands in staging
- [ ] ✅ Performance validation

### Go-Live (Day 3-4)
- [ ] ✅ Set webhook to Bitdeer endpoint
- [ ] ✅ Monitor for 24 hours
- [ ] ✅ Validate all functions working
- [ ] ✅ Shutdown local system

---

## Success Metrics (Updated)

**Performance Targets:**
- **Response time**: <2 seconds (Bitdeer API + network latency)
- **Uptime**: >99.5% (Bitdeer SLA)
- **Concurrent users**: 50+ (auto-scaling)
- **Cost**: <$400/month (API usage + compute + database)

**Cost Breakdown Estimate:**
- Bitdeer DeepSeek API: ~$100-200/month (based on usage)
- Compute instances: ~$100-150/month 
- Database: ~$50-75/month
- Network/Load Balancer: ~$25-50/month
- **Total**: ~$275-475/month

---

This updated migration is **much simpler and faster** since you're using Bitdeer's managed AI API instead of migrating model files! 🚀 