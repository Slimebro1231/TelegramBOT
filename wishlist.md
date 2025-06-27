# Bitdeer Cloud Migration: Telegram AI Bot Infrastructure  
*High-level requirements for cloud hosting discussion*  
_Last updated: 26 Jun 2025_

---

## Project Overview  

We are migrating our **Telegram AI Bot** from local infrastructure to Bitdeer cloud. The bot serves as an intelligent news analysis and market insights platform for our community.

### What the Bot Does:
- **Automated News Publishing**: Posts curated market news to our Telegram channel every 30 minutes
- **AI-Powered Analysis**: Provides real-time market analysis for gold, RWA (Real World Assets), and partnership opportunities  
- **Interactive Commands**: Responds to user queries with intelligent insights using a 14B parameter AI model
- **News Intelligence**: Scrapes 14+ sources, filters for relevance, prevents duplicates, and provides market context

---

## High-Level Requirements

### 1. **Compute Resources**
| Need | Purpose | Performance Expectation |
|------|---------|------------------------|
| **AI Model Hosting** | Run 14B parameter language model for real-time responses | Sub-1 second response time, 24/7 availability |
| **Bot Application Server** | Host the main Telegram bot application | Small VM, reliable uptime, handles ~100 messages/day |
| **Background Processing** | News scraping, article analysis, automated posting | Periodic CPU bursts, consistent background operation |

### 2. **Storage & Data**
| Need | Purpose | Growth Expectation |
|------|---------|-------------------|
| **Model Storage** | Store AI model files and dependencies | ~50GB initial, minimal growth |
| **News Archive** | Store scraped articles and analysis history | ~200GB growing to ~1TB over 12 months |
| **Application Data** | Bot configuration, user data, logs | ~10GB with steady growth |

### 3. **Networking & Security**
| Need | Purpose | Requirements |
|------|---------|-------------|
| **Public Access** | Telegram bot API connectivity | Reliable internet, static IP preferred |
| **Internal Communication** | Bot ↔ AI model ↔ data storage | Low latency internal networking |
| **Security** | Protect API keys, user data, model access | Basic firewall, secure environment variables |

### 4. **Operational Requirements**
| Need | Purpose | Expectation |
|------|---------|-------------|
| **Uptime** | 24/7 bot availability | 99%+ uptime target |
| **Monitoring** | Track performance, costs, errors | Basic alerting when issues occur |
| **Backup & Recovery** | Protect against data loss | Daily backups, quick restore capability |

---

## Success Metrics

- **Response Time**: AI responses under 1 second
- **Availability**: Bot online 99%+ of the time  
- **Cost Efficiency**: Predictable monthly costs under $500
- **Scalability**: Handle 10x message volume growth

---

## Migration Timeline

- **Week 1**: Infrastructure setup and testing
- **Week 2**: Bot deployment and validation  
- **Week 3**: Live migration and monitoring
- **Week 4**: Optimization and documentation

---

## Key Questions for Discussion

1. **AI Model Hosting**: What's the best approach for hosting a 14B parameter model with sub-1s response times?
2. **Cost Optimization**: How can we balance performance with cost-effectiveness?
3. **Scalability**: What happens if our user base grows 10x?
4. **Backup Strategy**: What's your recommended approach for data protection?
5. **Monitoring**: What tools do you provide for tracking performance and costs?

---

## Future Expansion

We're planning a **second AI project** for social media automation that would require:
- Larger AI models (70B+ parameters)  
- Higher compute capacity for training
- More storage for social media data (~5TB)
- This would be a separate discussion once the bot migration is successful

---

> **Meeting Goal**: Get Bitdeer's recommendations for service selection, estimated costs, and next steps for a smooth migration within 3-4 weeks.

---

# Technical Q&A Preparation  
*Detailed answers for deep-dive questions during the meeting*

---

## AI Model & Performance Details

**Q: What specific AI model are you using?**  
A: DeepSeek R1-14B parameter model, currently hosted via Ollama. It's optimized for reasoning and analysis tasks with excellent performance on financial/market content.

**Q: What are your current performance metrics?**  
A: 
- Average response time: 2-3 seconds locally
- Target cloud response time: <1 second
- Current daily usage: ~100 user messages + 48 automated news posts
- Peak concurrent users: ~10-15
- Model memory requirements: ~30GB VRAM for inference

**Q: How do you handle AI model serving?**  
A: Currently using Ollama for local inference. Open to managed inference services or containerized deployment. Model needs to support:
- Concurrent requests (up to 10 simultaneous)
- Custom prompt templates
- Response streaming/chunking for long responses
- Stateless operation (no conversation memory required)

---

## Application Architecture Details

**Q: What's the technical stack?**  
A: 
- **Language**: Python 3.11+
- **Bot Framework**: python-telegram-bot v22.1 (async)
- **AI Interface**: Ollama Python client
- **Dependencies**: aiohttp, requests, beautifulsoup4, feedparser, pytz
- **Configuration**: Environment variables (.env file)
- **Data**: JSON file storage (news_tracker.json, relevance_checklist.json)

**Q: How does the bot communicate with Telegram?**  
A: 
- Uses Telegram Bot API via HTTPS webhooks or long-polling
- Current: Long-polling for development (can switch to webhooks for production)
- Requires outbound HTTPS (443) to api.telegram.org
- Handles concurrent updates asynchronously
- Built-in retry logic and error handling

**Q: What are the bot's main functions?**  
A:
- **Interactive Commands**: /gold, /rwa, /bd, /meaning, /summary, /status
- **News Processing**: Scrapes 14+ sources every 30 minutes
- **Content Analysis**: AI-powered relevance checking and duplicate detection
- **Channel Publishing**: Automated posts to @Matrixdock_News
- **User Chat**: Natural language Q&A with AI responses

---

## Data & Storage Specifics

**Q: What data do you store and how much?**  
A:
- **News Archive**: ~200GB currently, growing ~50GB/month
  - Article content, metadata, analysis results
  - Duplicate detection hashes
  - Source tracking and statistics
- **Application Logs**: ~5GB/month (can be rotated)
- **Model Cache**: ~50GB (model files + embeddings)
- **Configuration**: <1GB (bot settings, API keys, checklists)

**Q: What's your backup strategy?**  
A: Currently file-based backups. Need:
- Daily automated backups
- Point-in-time recovery for news database
- Configuration backup before deployments
- Retention: 30 days standard, 1 year for compliance

**Q: Do you need a database?**  
A: Currently using JSON files. Open to managed database for:
- Better concurrent access
- Query performance improvements
- Automated backups
- Scaling beyond single-instance

---

## Network & Security Requirements

**Q: What are your networking requirements?**  
A:
- **Outbound**: HTTPS (443) to api.telegram.org, news sources
- **Internal**: Bot ↔ AI model (low latency preferred)
- **Management**: SSH (22) restricted to admin IPs
- **No inbound public access required** (except SSH for management)

**Q: How do you handle secrets/API keys?**  
A:
- BOT_TOKEN (Telegram Bot API token)
- Environment variables (.env file)
- Need secure secret management service
- Rotation capability for tokens

**Q: What are your security requirements?**  
A:
- Basic firewall (restrict inbound except SSH)
- Secure environment variable storage
- Regular security updates
- SSL/TLS for all external communications
- No PII storage (Telegram handles user data)

---

## Scalability & Performance

**Q: How will you handle traffic spikes?**  
A: Current bottlenecks and scaling needs:
- **AI Model**: Can handle ~10 concurrent requests
- **Bot Instance**: Single instance sufficient for current load
- **News Scraping**: CPU-bound during scraping cycles (every 30min)
- **Target Scale**: 10x growth = ~1,000 messages/day + same news frequency

**Q: What happens if the AI model is unavailable?**  
A: Built-in fallback system:
- Curated responses for common commands
- Graceful degradation with user notification
- Error tracking and alerting
- Automatic retry logic

**Q: How do you monitor performance?**  
A: Currently basic logging. Need:
- Response time monitoring
- Error rate tracking
- Resource utilization (CPU, memory, disk)
- Cost monitoring and alerts
- User activity metrics

---

## Migration & Deployment

**Q: What's your current deployment process?**  
A:
- Manual deployment via git pull + restart
- Environment variable configuration
- Dependency installation via pip/requirements.txt
- Single-instance deployment

**Q: What do you need for cloud deployment?**  
A:
- Container support (Docker) or direct Python deployment
- Environment variable injection
- Automated restarts on failure
- Log aggregation
- Blue/green deployment capability preferred

**Q: How will you test the migration?**  
A:
- Parallel deployment (test bot + production bot)
- Gradual traffic migration
- Response quality validation
- Performance benchmark comparison
- Rollback plan if issues occur

---

## Specific Technical Questions

**Q: Do you need GPU for the bot application?**  
A: No, only the AI model needs GPU. Bot application is CPU-only (2 vCPU, 4GB RAM sufficient).

**Q: Can you containerize the application?**  
A: Yes, we can create Docker containers. Current considerations:
- Base image: python:3.11-slim
- Multi-stage build for smaller images
- Health check endpoints needed
- Log output to stdout/stderr

**Q: What about CI/CD integration?**  
A: Currently manual. Would like:
- GitHub Actions integration
- Automated testing pipeline
- Deployment triggers
- Environment promotion (dev → staging → prod)

**Q: How do you handle downtime during updates?**  
A: Currently service interruption. Would prefer:
- Rolling updates with zero downtime
- Health checks before switching traffic
- Automatic rollback on deployment failure
- Maintenance windows if needed

---

## Cost & Budget Planning

**Q: What's your current infrastructure cost?**  
A: Currently running on local hardware. Estimating cloud costs:
- Target budget: $300-500/month
- Primary cost driver: GPU for AI model
- Secondary: Storage for news archive
- Willing to pay premium for reliability and managed services

**Q: How do you want to handle cost optimization?**  
A:
- Prefer predictable monthly costs over pay-per-use
- Open to reserved instances for consistent workloads
- Need cost alerts at $400/month threshold
- Auto-scaling down during low usage periods preferred

---

## Current Parallel Processing & Multi-Instance Scaling

**Q: How does your current parallel processing work?**  
A: **Current Architecture - Advanced Concurrent Processing:**

### **Async Event Loop Foundation**
- **Framework**: Python asyncio with async/await throughout
- **Telegram Integration**: python-telegram-bot v22+ (fully async)
- **AI Processing**: Thread pool execution to prevent blocking
- **Background Tasks**: Concurrent news generation + user interactions

### **Current Parallel Operations:**

**1. Multi-User Concurrent Handling**
```
User 1: /gold ──────► Thread Pool ──────► AI Model ──────► Response
User 2: /rwa  ──────► Thread Pool ──────► AI Model ──────► Response  
User 3: /meaning ───► Thread Pool ──────► AI Model ──────► Response
Timeline: All processed simultaneously, ~2-3s each
```

**2. Background vs Interactive Processing**
```python
# Concurrent task management
news_task = asyncio.create_task(news_scheduler())      # 30min intervals
console_task = asyncio.create_task(console_monitor())  # Admin commands
polling_task = application.updater.start_polling()     # User messages

# All run simultaneously without blocking each other
```

**3. News Pipeline Parallelization**
```python
# RSS feed fetching (8 concurrent workers)
with ThreadPoolExecutor(max_workers=8) as executor:
    tasks = [fetch_rss_feed(name, url) for name, url in RSS_FEEDS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

# Content extraction also parallelized
tasks = [scraper.get_article_with_content(article) for article in articles]
articles_with_content = await asyncio.gather(*tasks)
```

**Q: Can you run multiple bot instances for horizontal scaling?**  
A: **Current Limitations & Multi-Instance Readiness:**

### **✅ What Works with Multiple Instances:**
- **User Command Processing**: Stateless, can distribute across instances
- **AI Model Calls**: Each instance can call AI independently
- **Individual User Sessions**: No shared state between user interactions

### **❌ Current Bottlenecks for Multi-Instance:**

**1. Shared File Storage**
```python
# Currently uses local JSON files - single instance only
news_tracker.json     # Article duplicate tracking
relevance_checklist.json   # AI evaluation criteria
```

**2. Channel News Publishing**
```python
# Only ONE instance should post to channel
news_task_running = True
async def news_scheduler():
    while news_task_running:
        await asyncio.sleep(NEWS_INTERVAL)  # 30 minutes
        await post_to_channel()  # ← CONFLICT if multiple instances
```

**3. Telegram API Conflicts**
```python
# Bot token can only have ONE active polling connection
await application.updater.start_polling()  # ← Telegram enforces single connection
```

### **🔧 Multi-Instance Architecture Design:**

**Option 1: Role Separation (Recommended)**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  News Publisher │    │   User Handler   │    │  User Handler   │
│   (Single)      │    │   (Instance 1)   │    │   (Instance 2)  │
│                 │    │                  │    │                 │
│ • Channel posts │    │ • User commands  │    │ • User commands │
│ • News scraping │    │ • AI responses   │    │ • AI responses  │
│ • Deduplication │    │ • /gold, /rwa    │    │ • /gold, /rwa   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────────┐
                    │   Shared Database   │
                    │ • News articles     │
                    │ • Duplicate tracking│
                    │ • User metrics      │
                    └─────────────────────┘
```

**Option 2: Load Balancer + Shared Backend**
```
                    ┌─────────────────┐
                    │ Load Balancer   │
                    │ (Telegram Bot)  │
                    └─────────┬───────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼─────┐ ┌───────▼───────┐ ┌────▼──────────┐
    │  Bot Handler  │ │  Bot Handler  │ │ News Publisher│
    │  Instance 1   │ │  Instance 2   │ │   (Dedicated) │
    └───────┬───────┘ └───────┬───────┘ └───────────────┘
            │                 │                     │
            └─────────────────┼─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   AI Model Pool   │
                    │ (Shared/Managed)  │
                    └───────────────────┘
```

**Q: What changes are needed for cloud multi-instance deployment?**  
A: **Required Modifications:**

### **1. Shared Database Migration**
```python
# Replace JSON files with cloud database
# Before: news_tracker.json (local file)
# After: PostgreSQL/MongoDB (shared state)

class CloudNewsTracker:
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def is_duplicate(self, article_hash) -> bool:
        # Query shared database instead of local file
        return await self.db.exists('articles', {'hash': article_hash})
```

### **2. Instance Role Configuration**
```python
# Environment-based role assignment
INSTANCE_ROLE = os.getenv("INSTANCE_ROLE", "user_handler")  # or "news_publisher"

if INSTANCE_ROLE == "news_publisher":
    # Start news generation tasks
    news_task = asyncio.create_task(news_scheduler())
elif INSTANCE_ROLE == "user_handler":
    # Only handle user commands, no news generation
    pass
```

### **3. Distributed Lock System**
```python
# Prevent multiple instances from posting simultaneously
async def post_to_channel():
    async with DistributedLock("channel_posting", timeout=300):
        if await should_post_news():
            await generate_and_post_news()
```

### **4. Webhook vs Polling for Load Balancing**
```python
# Switch from polling to webhooks for multi-instance
# Before: Long polling (single connection)
await application.updater.start_polling()

# After: Webhook distribution
await application.updater.start_webhook(
    listen="0.0.0.0",
    port=8443,
    webhook_url=f"https://your-domain.com/{TOKEN}"
)
```

**Q: What's the scaling capacity with multiple instances?**  
A: **Performance Projections:**

### **Current Single Instance:**
- **User Commands**: ~10 concurrent (limited by AI model)
- **Daily Messages**: ~100 handled efficiently
- **Channel News**: 48 posts/day (every 30 minutes)

### **Multi-Instance Scaling:**
```
2 User Handler Instances:
• 20 concurrent user commands
• 400+ daily messages capacity
• Same news posting frequency (single publisher)

5 User Handler Instances:
• 50 concurrent user commands  
• 1,000+ daily messages capacity
• Horizontal AI model scaling needed

10 User Handler Instances:
• 100 concurrent user commands
• 2,000+ daily messages capacity
• Requires managed AI inference service
```

### **Bottleneck Analysis:**
1. **AI Model**: Currently single Ollama instance (30GB VRAM)
2. **News Generation**: Single instance by design (prevents duplicates)
3. **Database**: Scales with managed cloud database
4. **Network**: Telegram API rate limits (~30 requests/second)

**Q: How would you implement auto-scaling?**  
A: **Cloud Auto-Scaling Strategy:**

### **Horizontal Pod Autoscaler (HPA)**
```yaml
# Kubernetes HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: telegram-bot-user-handlers
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bot-user-handlers
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: active_user_sessions
      target:
        type: AverageValue
        averageValue: "5"
```

### **Scaling Triggers:**
- **CPU Usage > 70%**: Scale up user handlers
- **Active Sessions > 5/pod**: Add more instances  
- **Response Time > 2s**: Horizontal scaling
- **Queue Length > 10**: Emergency scaling

### **Cost-Optimized Scaling:**
```
Low Usage (Night): 1-2 instances
Normal Usage: 2-3 instances  
Peak Usage: 5-8 instances
Emergency: 10+ instances (cost alerts)
```

This multi-instance architecture enables handling 10x-100x more users while maintaining the same response quality and news generation reliability.