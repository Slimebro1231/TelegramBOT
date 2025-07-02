# Detailed Bitdeer AI Studio Setup Guide
*Exact step-by-step instructions for the Telegram AI Bot migration*  
_Created: 26 Jun 2025_

---

## Current Status Check

**Where you are now**: Bitdeer AI Studio page with your project  
**What we need to do**: Set up AI model access and get API credentials  
**Goal**: Replace local Ollama with Bitdeer cloud AI API

---

## Step 1: Model Selection for Your Use Case 🎯

### **Your Bot's Requirements Analysis:**
- **Financial market analysis** (gold, RWA trends)
- **News relevance scoring** (1-10 scale analysis) 
- **Business development opportunity identification**
- **Bullet-point formatted responses** (3-4 concise points)
- **Reasoning and market insight generation**
- **~100 requests/day current usage**

### **Recommended Model: DeepSeek-V3**
**Why this model for your bot:**
- **Superior reasoning** for financial analysis
- **Excellent at structured outputs** (bullet points, scoring)
- **Cost-effective** for your usage volume
- **Fast response times** (<2 seconds typically)
- **Strong business/financial domain knowledge**

### **Alternative Models to Consider:**
1. **DeepSeek-Coder** - If you need technical analysis capabilities
2. **GPT-4 Turbo** - If available, but more expensive
3. **Claude-3.5-Sonnet** - If available, excellent for analysis

---

## Step 2: Navigating Bitdeer AI Studio Interface

### **What you should see on your AI Studio page:**

**Tell me what options you see under these sections:**
1. **Left sidebar menu** - What options are listed?
2. **Main dashboard area** - Any cards or sections visible?
3. **Top navigation** - Any tabs like "Models", "Deployments", "API Keys"?

### **Common Bitdeer AI Studio Layout Options:**

**Option A: If you see "Model Gallery" or "Browse Models":**
1. Click on **"Model Gallery"** or **"Browse Models"**
2. Look for **"DeepSeek"** models in the list
3. Click on **"DeepSeek-V3"** or **"DeepSeek-Chat"**
4. Click **"Deploy"** or **"Create Endpoint"**

**Option B: If you see "Deployments" or "Create Deployment":**
1. Click **"Create Deployment"** or **"New Deployment"**
2. Select **"Text Generation"** or **"Chat Completion"**
3. Choose **"DeepSeek-V3"** from model dropdown
4. Configure deployment settings

**Option C: If you see "API Services" or "Inference":**
1. Navigate to **"API Services"** → **"Inference"**
2. Click **"Create New Service"**
3. Select **"Language Model"** category
4. Choose **"DeepSeek"** provider

---

## Step 3: Detailed Model Deployment Setup

### **When you find the DeepSeek model, configure these settings:**

#### **A. Basic Configuration:**
```
Model Name: deepseek-v3-chat
Deployment Name: telegram-bot-ai
Instance Type: [Select smallest GPU option - likely A10 or T4]
```

#### **B. Scaling Configuration:**
```
Min Replicas: 1
Max Replicas: 3
Auto-scaling: Enabled
Target Utilization: 70%
```

#### **C. API Configuration:**
```
API Type: OpenAI Compatible (preferred)
Authentication: API Key
Rate Limiting: 100 requests/minute
Timeout: 30 seconds
```

#### **D. Advanced Settings:**
```
Temperature: 0.7
Max Tokens: 1000
Top P: 0.9
Frequency Penalty: 0.1
```

---

## Step 4: Get Your API Credentials

### **After deployment is complete, you need:**

#### **A. API Endpoint URL:**
- Should look like: `https://api.bitdeer.com/v1/deployments/YOUR_DEPLOYMENT_ID`
- Or: `https://YOUR_PROJECT.bitdeer.com/v1/chat/completions`

#### **B. API Key:**
1. Look for **"API Keys"** section
2. Click **"Generate New Key"** or **"Create API Key"**
3. Name it: `telegram-bot-production`
4. Copy and save the key securely
5. **Important**: Save this immediately - you may not see it again

#### **C. Model Identifier:**
- Note the exact model name (e.g., `deepseek-v3-chat`)
- This goes in your API calls

---

## Step 5: Test Your API Access

### **Run this test from your local machine:**

```bash
# Replace with your actual credentials
export BITDEER_API_KEY="your_actual_api_key_here"
export BITDEER_ENDPOINT="your_actual_endpoint_here"

# Test basic connectivity
curl -X POST "$BITDEER_ENDPOINT/chat/completions" \
  -H "Authorization: Bearer $BITDEER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3-chat",
    "messages": [
      {
        "role": "user", 
        "content": "Analyze the gold market and provide 3 bullet points about current trends."
      }
    ],
    "max_tokens": 500,
    "temperature": 0.7
  }'
```

### **Expected successful response:**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1640995200,
  "model": "deepseek-v3-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "• Gold prices remain supported by central bank purchases and inflation hedging demand\n• Technical indicators suggest consolidation phase with potential for upward breakout\n• Geopolitical tensions continue to drive safe-haven flows into precious metals"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 75,
    "total_tokens": 100
  }
}
```

---

## Step 6: Integration Code for Your Bot

### **Create the Bitdeer AI client:**

```python
# bitdeer_ai_client.py
import aiohttp
import asyncio
import os
import json
from typing import Dict, List, Optional

class BitdeerAIClient:
    def __init__(self, api_key: str, endpoint: str, model: str = "deepseek-v3-chat"):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip('/')  # Remove trailing slash
        self.model = model
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Dict:
        """Send chat completion request to Bitdeer AI API."""
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False
        }
        
        url = f"{self.endpoint}/chat/completions"
        
        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"Bitdeer API error {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling Bitdeer API: {str(e)}")
    
    async def simple_chat(self, prompt: str, context: str = "") -> str:
        """Simplified chat method that returns just the response text."""
        
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        messages = [{"role": "user", "content": full_prompt}]
        
        result = await self.chat_completion(messages)
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            raise Exception("No response generated from Bitdeer AI")

# Test the client
async def test_bitdeer_client():
    api_key = os.getenv("BITDEER_API_KEY")
    endpoint = os.getenv("BITDEER_ENDPOINT")
    
    if not api_key or not endpoint:
        print("❌ Missing BITDEER_API_KEY or BITDEER_ENDPOINT environment variables")
        return
    
    async with BitdeerAIClient(api_key, endpoint) as client:
        try:
            response = await client.simple_chat(
                "Analyze gold market trends and provide exactly 3 bullet points."
            )
            print("✅ Bitdeer AI Test Successful:")
            print(response)
            
        except Exception as e:
            print(f"❌ Bitdeer AI Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_bitdeer_client())
```

---

## Step 7: Update Your Bot Code

### **Modify bot.py to use Bitdeer instead of Ollama:**

```python
# Add these imports at the top of bot.py
import aiohttp
from bitdeer_ai_client import BitdeerAIClient

# Add environment detection and configuration
IS_CLOUD = os.getenv("DEPLOYMENT_ENV") == "cloud"

if IS_CLOUD:
    BITDEER_API_KEY = os.getenv("BITDEER_API_KEY")
    BITDEER_ENDPOINT = os.getenv("BITDEER_ENDPOINT") 
    BITDEER_MODEL = os.getenv("BITDEER_MODEL", "deepseek-v3-chat")
    
    if not BITDEER_API_KEY or not BITDEER_ENDPOINT:
        raise RuntimeError("❌ Missing Bitdeer API credentials in cloud environment")
    
    print(f"✅ Cloud mode: Using Bitdeer API with {BITDEER_MODEL}")
else:
    print(f"🔧 Local mode: Using Ollama with {MODEL_NAME}")

# Replace the get_ai_response function
async def get_ai_response(prompt: str, context: str = "", command: str = "chat") -> str:
    """Get response from AI model - Bitdeer cloud or local Ollama."""
    try:
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        print(f"🧠 [{command.upper()}] AI Processing...")
        print(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        
        if IS_CLOUD:
            # Use Bitdeer AI API
            print("⚡ Sending request to Bitdeer AI...")
            
            async with BitdeerAIClient(BITDEER_API_KEY, BITDEER_ENDPOINT, BITDEER_MODEL) as client:
                ai_response = await client.simple_chat(full_prompt)
            
            print(f"✅ Bitdeer API response: {len(ai_response)} chars")
            
        else:
            # Existing local Ollama code
            print("⚡ Sending request to local Ollama...")
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None, 
                lambda: ollama.chat(
                    model=MODEL_NAME,
                    messages=[{'role': 'user', 'content': full_prompt}]
                )
            )
            
            ai_response = response['message']['content']
            print(f"✅ Ollama response: {len(ai_response)} chars")
        
        # Same response processing for both cloud and local
        ai_response = extract_final_response(ai_response)
        
        # Truncate if too long
        if len(ai_response) > MAX_MESSAGE_LENGTH:
            original_length = len(ai_response)
            ai_response = ai_response[:MAX_MESSAGE_LENGTH-50] + "...\n\n[Response truncated]"
            print(f"✂️ Truncated response: {original_length} → {len(ai_response)} chars")
            
        print(f"✅ Clean response ready ({len(ai_response)} chars)")
        bot_status.log_ai_response()
        return ai_response
        
    except Exception as e:
        bot_status.log_error()
        error_msg = str(e)
        print(f"❌ AI Error Details: {error_msg}")
        print(f"🔧 Falling back to curated content for {command}")
        return None  # Will trigger fallback responses
```

---

## Step 8: Environment Variables Setup

### **Create .env.cloud file for testing:**

```bash
# .env.cloud (for local testing with Bitdeer API)
DEPLOYMENT_ENV=cloud
BOT_TOKEN=your_telegram_bot_token

# Bitdeer AI Configuration
BITDEER_API_KEY=your_actual_bitdeer_api_key
BITDEER_ENDPOINT=your_actual_bitdeer_endpoint
BITDEER_MODEL=deepseek-v3-chat

# Bot Configuration (unchanged)
CHANNEL_ID=@Matrixdock_News
NEWS_INTERVAL=1800
```

### **Test locally with Bitdeer API:**

```bash
# Load cloud environment for testing
export $(cat .env.cloud | xargs)

# Test the bot locally with Bitdeer API
python bitdeer_ai_client.py  # Test the client first
python bot.py                # Then test the full bot
```

---

## Step 9: Troubleshooting Common Issues

### **Issue 1: "Model not found" error**
**Solution**: Check exact model name in Bitdeer console
```bash
# List available models (if API supports it)
curl -X GET "$BITDEER_ENDPOINT/models" \
  -H "Authorization: Bearer $BITDEER_API_KEY"
```

### **Issue 2: Authentication errors**
**Solution**: Verify API key format and permissions
```bash
# Test authentication
curl -X GET "$BITDEER_ENDPOINT/health" \
  -H "Authorization: Bearer $BITDEER_API_KEY"
```

### **Issue 3: Timeout errors**
**Solution**: Increase timeout in client configuration
```python
# In BitdeerAIClient.__aenter__
self.session = aiohttp.ClientSession(
    timeout=aiohttp.ClientTimeout(total=60),  # Increase to 60 seconds
    headers={"Authorization": f"Bearer {self.api_key}"}
)
```

### **Issue 4: Rate limiting**
**Solution**: Add retry logic with exponential backoff
```python
import asyncio
from random import uniform

async def retry_api_call(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + uniform(0, 1)
                print(f"⏳ Rate limited, waiting {wait_time:.1f}s before retry {attempt + 2}/{max_retries}")
                await asyncio.sleep(wait_time)
            else:
                raise
```

---

## Next Steps

**After you complete the above setup:**

1. **Tell me exactly what you see** in your Bitdeer AI Studio interface
2. **Share any error messages** you encounter during API testing  
3. **Confirm which model options** are available to you
4. **Test the API connection** using the curl command above
5. **Run the bot locally** with Bitdeer API before cloud deployment

**Once API is working locally, we'll proceed to:**
- Database migration to Bitdeer PostgreSQL
- Full application deployment to Bitdeer compute
- Production webhook configuration

---

This guide gives you the exact, detailed steps without simplification. Let me know what you see in your Bitdeer interface and we'll walk through it step by step! 