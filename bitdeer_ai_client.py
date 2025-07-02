# bitdeer_ai_client.py
import aiohttp
import asyncio
import os
import json
from typing import Dict, List, Optional

class BitdeerAIClient:
    def __init__(self, api_key: str, model: str = "deepseek-ai/DeepSeek-R1"):
        self.api_key = api_key
        self.endpoint = "https://api-inference.bitdeer.ai/v1/chat/completions"
        self.model = model
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 300,
        temperature: float = 0.7,
        top_p: float = 1.0,
        frequency_penalty: float = 0.2,
        presence_penalty: float = 0.0,
        stream: bool = False
    ) -> Dict:
        """Send chat completion request to Bitdeer AI API."""
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stream": stream
        }
        
        try:
            async with self.session.post(self.endpoint, json=payload) as response:
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
        
        messages = []
        
        if context:
            messages.append({"role": "system", "content": context})
        
        messages.append({"role": "user", "content": prompt})
        
        result = await self.chat_completion(messages)
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            raise Exception("No response generated from Bitdeer AI")

# Test the client
async def test_bitdeer_client():
    api_key = os.getenv("DEEPSEEK_API")
    
    if not api_key:
        print("❌ Missing DEEPSEEK_API environment variable")
        return
    
    print(f"🔑 Using API key: {api_key[:20]}...")
    
    async with BitdeerAIClient(api_key) as client:
        try:
            print("⚡ Testing Bitdeer DeepSeek-R1 API...")
            
            # Test with your bot's style
            response = await client.simple_chat(
                "Analyze current gold market trends. Provide exactly 3 concise bullet points (maximum 25 words each). Use format: • Point 1 • Point 2 • Point 3",
                "You are a financial analysis assistant. Provide concise, actionable market insights."
            )
            
            print("✅ Bitdeer AI Test Successful:")
            print("-" * 50)
            print(response)
            print("-" * 50)
            print(f"📊 Response length: {len(response)} characters")
            
        except Exception as e:
            print(f"❌ Bitdeer AI Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_bitdeer_client()) 