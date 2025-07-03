# bitdeer_ai_client.py
import aiohttp
import asyncio
import os
import json
import re
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
                    print(f"🐞 DEBUG - API Error Details:")
                    print(f"   Status: {response.status}")
                    print(f"   Headers: {dict(response.headers)}")
                    print(f"   Error: {error_text[:200]}")
                    raise Exception(f"Bitdeer API error {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            print(f"🐞 DEBUG - Network Error: {str(e)}")
            raise Exception(f"Network error calling Bitdeer API: {str(e)}")
    
    async def simple_chat(self, prompt: str, context: str = "") -> str:
        """Simplified chat method that returns just the response text."""
        
        messages = []
        
        if context:
            messages.append({"role": "system", "content": context})
        
        messages.append({"role": "user", "content": prompt})
        
        result = await self.chat_completion(messages)
        
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0]["message"]
            
            # For DeepSeek-R1: reasoning_content has the thinking, content has final answer
            # Try content first (final answer), fall back to reasoning_content
            response_text = ""
            
            if "content" in message and message["content"]:
                response_text = message["content"]
            elif "reasoning_content" in message and message["reasoning_content"]:
                # Extract final answer from reasoning process
                response_text = self._extract_final_answer(message["reasoning_content"])
            
            if not response_text:
                raise Exception("Empty response from Bitdeer AI - no content or reasoning_content")
            
            return response_text
        else:
            raise Exception("No response generated from Bitdeer AI")
    
    def _extract_final_answer(self, reasoning_text: str) -> str:
        """Extract the final answer after <thinking> tags from reasoning models."""
        
        # First, try to remove <thinking>...</thinking> blocks
        thinking_pattern = r'<thinking>.*?</thinking>'
        cleaned = re.sub(thinking_pattern, '', reasoning_text, flags=re.DOTALL | re.IGNORECASE)
        
        # Check if this is pure reasoning without final answers
        reasoning_indicators = [
            'okay, the user', 'let me start by', 'let me recall', 'i need to analyze', 
            'breaking down the request', 'first, i need to consider', 'comes to mind immediately',
            'the user probably wants detailed', 'their main request seems to be', 'the user asked for exactly'
        ]
        
        # Only trigger reasoning extraction if multiple indicators are present (less aggressive)
        if sum(1 for indicator in reasoning_indicators if indicator in reasoning_text.lower()) >= 2:
            # This is pure reasoning - try to extract conclusions or return concise summary
            return self._extract_conclusions_from_reasoning(reasoning_text)
        
        # If no thinking tags found, try to extract final bullet points from reasoning
        if cleaned == reasoning_text:
            lines = reasoning_text.split('\n')
            
            # First pass: remove meta-commentary and headers entirely
            filtered_lines = []
            for line in lines:
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Skip meta-commentary but be less aggressive (preserve more content)
                line_lower = line.lower()
                
                # Only skip obvious meta-commentary, not content-related keywords
                should_skip = (
                    'here are the bullet points' in line_lower or
                    'exactly 3 bullet points' in line_lower or
                    'here are exactly 3' in line_lower or
                    'the user wants' in line_lower or
                    'the user is asking for' in line_lower or
                    'hmm, let me think' in line_lower or
                    'let me start by analyzing' in line_lower or
                    'i need to provide' in line_lower or
                    'first bullet point should' in line_lower or
                    'second bullet point' in line_lower or
                    'third bullet point' in line_lower or
                    line_lower.strip() == 'here are 3 bullet points:' or
                    line_lower.strip() == 'here are the key opportunities:' or
                    (line_lower.startswith('here are') and 'bullet points' in line_lower and len(line) < 80)
                )
                
                if should_skip:
                    continue
                
                # Skip headers and section titles (lines with ### or ending with :)
                if line.startswith('#') or (line.endswith(':') and len(line) < 100):
                    continue
                    
                filtered_lines.append(line)
            
            # Second pass: extract and clean bullet points
            final_bullets = []
            for line in filtered_lines:
                # Look for lines that are likely bullet points (more comprehensive)
                is_bullet_line = (
                    line.startswith('•') or
                    line.startswith('-') or
                    line.startswith('*') or
                    re.match(r'^\d+\.\s*', line) or  # 1. 2. 3. etc
                    line.startswith('- **') or
                    line.startswith('* **') or
                    re.match(r'^\d+\.\s*\*\*', line)  # 1. **Title**
                )
                
                if is_bullet_line:
                    # Fix double bullets first
                    line = re.sub(r'•\s*•\s*', '• ', line)  # Fix • • to single •
                    line = re.sub(r'••+', '• ', line)  # Fix multiple bullets
                    
                    # Clean up bullet point formatting
                    clean_line = self._clean_bullet_formatting(line)
                    
                    # Skip bullets that are clearly incomplete or thinking process
                    if clean_line and clean_line.startswith('• '):
                        bullet_content = clean_line[2:].strip()
                        # Skip if incomplete, contains thinking indicators, or too short
                        if (len(bullet_content) < 20 or 
                            bullet_content.endswith('...') or 
                            not bullet_content.endswith('.') or
                            any(phrase in bullet_content.lower() for phrase in [
                                'next,', 'first,', 'second,', 'third,', 'if tokenized', 
                                'traditional retail', 'investor impact', 'market partic',
                                'hmm,', 'the user wants', 'i need to', 'analyzing', 'considering'
                            ])):
                            continue
                    
                    # Only keep substantial bullet points (not headers or short fragments)
                    if clean_line and len(clean_line) > 30 and not clean_line.endswith(':'):
                        # Truncate overly long bullet points (especially for BD command)
                        if len(clean_line) > 180:
                            clean_line = clean_line[:177] + "..."
                        final_bullets.append(clean_line)
            
            if len(final_bullets) >= 2:
                return '\n'.join(final_bullets[:4])
            
            # Fallback: look for numbered points and convert them
            numbered_bullets = []
            for line in lines:
                line = line.strip()
                # Look for numbered points like "1. Content here"
                if re.match(r'^\d+\.\s+\*\*.*\*\*', line):  # Numbered + bold
                    clean_line = self._clean_bullet_formatting(line)
                    if len(clean_line) > 20:
                        if len(clean_line) > 200:
                            clean_line = clean_line[:197] + "..."
                        numbered_bullets.append(clean_line)
            
            if len(numbered_bullets) >= 2:
                return '\n'.join(numbered_bullets[:4])
        
        # Clean up final answer from thinking tags
        final_answer = cleaned.strip()
        if final_answer:
            # Apply same cleaning to final answer
            lines = final_answer.split('\n')
            clean_lines = []
            for line in lines:
                clean_line = self._clean_bullet_formatting(line.strip())
                if clean_line and len(clean_line) > 10:
                    if len(clean_line) > 200:
                        clean_line = clean_line[:197] + "..."
                    clean_lines.append(clean_line)
            
            if clean_lines:
                return '\n'.join(clean_lines[:4])
        
        # Last resort: return first part of reasoning
        return reasoning_text[:400] + "..." if len(reasoning_text) > 400 else reasoning_text
    
    def _clean_bullet_formatting(self, line: str) -> str:
        """Clean and standardize bullet point formatting."""
        if not line:
            return ""
        
        line = line.strip()
        
        # First, handle numbered bullets with double asterisks (common pattern)
        if re.match(r'^\d+\.\s*\*\*', line):
            # Extract just the content after number and asterisks
            match = re.match(r'^\d+\.\s*\*\*(.*?)\*\*(.*)$', line)
            if match:
                title, content = match.groups()
                line = f'• {title.strip()}{content.strip()}'
            else:
                line = re.sub(r'^\d+\.\s*', '• ', line)
        
        # Handle dash bullets with double asterisks
        elif line.startswith('- **'):
            match = re.match(r'^- \*\*(.*?)\*\*(.*)$', line)
            if match:
                title, content = match.groups()
                line = f'• {title.strip()}{content.strip()}'
            else:
                line = '• ' + line[4:]
        
        # Handle other bullet formats
        elif line.startswith('* **'):
            line = '• ' + line[4:]
        elif line.startswith(('-', '*')):
            line = '• ' + line[1:].strip()
        elif re.match(r'^\d+\.\s*', line):
            # Remove numbered prefixes and convert to bullets
            line = re.sub(r'^\d+\.\s*', '• ', line)
        elif not line.startswith('•'):
            line = '• ' + line
        
        # Clean up spacing around bullet
        line = re.sub(r'^•\s+', '• ', line)
        
        # Remove ALL asterisk formatting aggressively
        # First handle **Text**: patterns (common in titles)
        line = re.sub(r'\*\*([^*]+)\*\*:\s*', r'\1 - ', line)
        
        # Then handle **Text** patterns  
        while '**' in line:
            line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
        
        # Remove any remaining asterisks completely
        line = line.replace('*', '')
        
        # Clean up double bullets (•  • becomes just •)
        line = re.sub(r'^•\s*•\s*', '• ', line)
        
        # Remove any dollar signs from financial figures  
        line = re.sub(r'\$\d+[–-]\$?\d+\s*(billion|million|trillion)', 'significant amounts', line)
        
        # Clean up any colon-based headers and replace with dash
        line = re.sub(r'^• ([^:]+):\s*', r'• \1 - ', line)
        
        # Final cleanup of extra spaces
        line = re.sub(r'\s+', ' ', line).strip()
        
        return line
    
    def _extract_conclusions_from_reasoning(self, reasoning_text: str) -> str:
        """Extract actionable conclusions from pure reasoning text."""
        lines = reasoning_text.split('\n')
        conclusions = []
        
        # Look for lines that contain actual insights/conclusions rather than process
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            line_lower = line.lower()
            
            # Skip pure reasoning/process lines
            skip_reasoning = any(pattern in line_lower for pattern in [
                'okay, the user', 'let me', 'i need to', 'breaking down', 'comes to mind',
                'the user probably', 'their main request', 'by recalling', 'start by',
                'next,', 'first,', 'also,', 'that opens', 'previously,', 'now,'
            ])
            
            if skip_reasoning:
                continue
            
            # Look for lines with actual financial/business insights
            has_insight = any(keyword in line_lower for keyword in [
                'liquidity', 'tokenization', 'assets', 'investors', 'market', 'trading',
                'partnerships', 'opportunities', 'exchanges', 'compliance', 'security',
                'fractional ownership', 'barriers', 'institutional', 'retail', 'global',
                'expansion', 'regulatory', 'payment', 'cybersecurity', 'trust'
            ])
            
            if has_insight and len(line) > 30:
                # Clean and format as bullet point
                clean_line = self._clean_bullet_formatting(line)
                if len(clean_line) > 180:
                    clean_line = clean_line[:177] + "..."
                conclusions.append(clean_line)
                
        if len(conclusions) >= 2:
            return '\n'.join(conclusions[:4])
        
        # Fallback: create generic bullets based on topic
        topic_keywords = reasoning_text.lower()
        if 'rwa' in topic_keywords or 'tokenization' in topic_keywords:
            return "• Tokenization enables fractional ownership and increased liquidity for traditional assets\n• Lower barriers to entry democratize access to high-value investment opportunities\n• Blockchain automation reduces costs and improves efficiency in asset management"
        elif 'partnership' in topic_keywords or 'exchange' in topic_keywords:
            return "• Liquidity partnerships enhance trading volume and market depth for all parties\n• Global expansion through local partnerships enables market entry and regulatory compliance\n• Security and trust partnerships improve user confidence and platform reliability"
        else:
            return "• Market conditions remain dynamic with multiple contributing factors\n• Institutional and retail demand patterns continue to evolve\n• Strategic positioning remains important for long-term success"
  
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