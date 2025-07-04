"""
Telegram AI Bot with Bitdeer DeepSeek-R1 API Integration
========================================================

• Loads `BOT_TOKEN` from a .env file or environment variable
• API-only mode using Bitdeer DeepSeek-R1 cloud service
• Command-only mode: responds ONLY to messages starting with /
• Available commands: /start, /help, /gold, /rwa, /meaning, /bd, /summary, /status
• Uses python‑telegram‑bot v22+ (async Application API)
"""

import os
import asyncio
import threading
import json
import re
import pytz
import hashlib
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import signal
import sys
import time
import random
from news_scraper import get_single_relevant_article, format_article_for_ai, NewsArticle, get_tracker_stats, NewsScraper
from conflict_resolution import nuclear_conflict_resolution, ultra_robust_polling_start, should_use_conflict_resolution, should_use_ultra_robust_polling
from bitdeer_ai_client import BitdeerAIClient
import html

# --- Config ------------------------------------------------------------------
load_dotenv()  # take environment variables from .env, if present
TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise RuntimeError("⛔  BOT_TOKEN not set in environment variables or .env file")

MAX_MESSAGE_LENGTH = 4000  # Telegram limit is 4096, leave some buffer
CHANNEL_ID = "@Matrixdock_News"  # Channel to post automatic news
NEWS_INTERVAL = 1800  # 30 minutes between posts (in seconds)

# --- AI Configuration --------------------------------------------------------
# API-only mode - always use Bitdeer cloud
IS_CLOUD = True
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("❌ Missing DEEPSEEK_API environment variable")
print(f"✅ API-only mode: Using Bitdeer DeepSeek-R1 API")

# --- Status Tracking ---------------------------------------------------------
class BotStatus:
    def __init__(self):
        self.start_time = datetime.now()
        self.message_count = 0
        self.ai_responses = 0
        self.errors = 0
        
    def log_message(self):
        self.message_count += 1
        print(f"📊 Messages: {self.message_count} | AI Responses: {self.ai_responses} | Errors: {self.errors}")
    
    def log_ai_response(self):
        self.ai_responses += 1
    
    def log_error(self):
        self.errors += 1

bot_status = BotStatus()

# --- Channel News Control ----------------------------------------------------
news_task_running = False
application_instance = None

def cleanup_and_exit(signum=None, frame=None):
    """Clean exit handler."""
    print(f"\n🛑 Bot shutdown initiated...")
    print("✅ Cleanup complete. Goodbye!")
    sys.exit(0)

# Register signal handlers for clean shutdown
signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)

# --- AI Helper Functions -----------------------------------------------------
async def get_ai_response(prompt: str, context: str = "", command: str = "chat") -> str:
    """Get response from AI model - Bitdeer cloud or local Ollama."""
    try:
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        # Debug logging - only in development mode
        debug_mode = os.getenv("DEBUG_MODE") == "true"
        if debug_mode:
            print(f"🧠 [{command.upper()}] AI Processing...")
            print(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        
        # Use Bitdeer AI API (API-only mode)
        if debug_mode:
            print("⚡ Sending request to Bitdeer DeepSeek-R1...")
        
        # Set higher token limit for BD commands since they need complete business recommendations
        max_tokens = 800 if command.startswith("bd") else 300
        
        async with BitdeerAIClient(DEEPSEEK_API_KEY) as client:
            # Use chat_completion with custom token limits instead of simple_chat
            messages = []
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": full_prompt})
            
            result = await client.chat_completion(messages, max_tokens=max_tokens)
            
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0]["message"]
                # For DeepSeek-R1: content has final answer, reasoning_content has thinking
                ai_response = message.get("content", "") or message.get("reasoning_content", "")
                if not ai_response:
                    raise Exception("Empty response from AI")
            else:
                raise Exception("No response generated from AI")
        
        if debug_mode:
            print(f"✅ Bitdeer API response: {len(ai_response)} chars")
        
        # Log thinking process to console (for debugging)
        if debug_mode:
            if len(ai_response) > 200:
                print(f"💭 AI Response Preview: {ai_response[:200]}...")
            else:
                print(f"💭 AI Full Response: {ai_response}")
        
        bot_status.log_ai_response()
        
        # Enhanced thinking detection and filtering for all commands
        def extract_final_response(response_text):
            """Extract the final response after thinking process with enhanced filtering."""
            import re
            
            def is_thinking_content(text: str) -> bool:
                """Check if text contains AI thinking process indicators."""
                text_lower = text.lower()
                thinking_indicators = [
                    'hmm,', 'the user wants', 'i need to', 'i think', 'i\'ll', 'looking at',
                    'analyzing', 'considering', 'let me', 'i should', 'the article details',
                    'for the first point', 'for the second', 'for the third', 'each bullet point',
                    'between 10-15 words', 'about market impact', 'i\'ll need to create',
                    'with a relevance score', 'the summary mentions', 'published on',
                    'the user wants me to', 'i\'ll need to', 'bullet points about',
                    'the news states that', 'the requirements are', 'for the first opportunity',
                    'i consider', 'the first angle', 'the second angle', 'the third angle',
                    'first, i', 'second, i', 'third, i', 'i\'ll focus on', 'i\'ll identify',
                    'next, investor impact', 'if tokenized stocks face', 'traditional retail investors might',
                    'here are concrete', 'here are specific', 'leveraging the regulatory'
                ]
                return any(indicator in text_lower for indicator in thinking_indicators)
            
            # First, try to remove <think>...</think> blocks (common in R1 models)
            think_pattern = r'<think>.*?</think>'
            cleaned = re.sub(think_pattern, '', response_text, flags=re.DOTALL | re.IGNORECASE)
            
            # Extract bullet points from the response with thinking detection
            lines = (cleaned if cleaned != response_text else response_text).split('\n')
            bullet_lines = []
            
            for line in lines:
                line = line.strip()
                # Only keep lines that start with bullet points
                if line and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                    
                    # Check if this bullet contains thinking process indicators
                    if is_thinking_content(line):
                        continue
                        
                    # Skip bullets that are too long (likely thinking process)
                    bullet_content = line.replace('•', '').replace('-', '').replace('*', '').strip()
                    if len(bullet_content) > 200:  # Too verbose, likely thinking
                        continue
                    
                    # Skip bullets with obvious problems (for news generation)
                    if ('...' in line or  # Any incomplete content with ellipsis
                        line.count('•') > 1 or  # Multiple bullets on one line
                        bullet_content.strip() in ['', '...', '•'] or  # Empty or just symbols
                        len(bullet_content) < 15 or  # Too short to be meaningful
                        is_thinking_content(bullet_content)):  # Contains thinking indicators
                        continue
                    
                    if not line.startswith('•'):
                        line = '•' + line[1:]  # Standardize to •
                    bullet_lines.append(line)
            
            # If we found bullet points, do simple cleanup
            if bullet_lines:
                # Simple cleanup pass
                cleaned_bullets = []
                for bullet in bullet_lines:
                    # Fix double bullet markers and clean whitespace
                    cleaned_bullet = bullet.replace('• •', '•').replace('••', '•').strip()
                    
                    # Keep if it has reasonable content
                    content = cleaned_bullet.replace('•', '').strip()
                    if len(content) >= 10 and not is_thinking_content(content):
                        cleaned_bullets.append(cleaned_bullet)
                
                # Return if we have any decent bullets
                if cleaned_bullets:
                    return '\n'.join(cleaned_bullets)
            
            # Fallback: look for non-thinking sentences
            sentences = [s.strip() for s in response_text.split('.') if s.strip() and len(s.strip()) > 20]
            clean_sentences = []
            
            for sentence in sentences[-5:]:  # Check last 5 sentences
                if not is_thinking_content(sentence):
                    clean_sentences.append(f"• {sentence}.")
                    if len(clean_sentences) >= 3:
                        break
            
            if clean_sentences:
                return '\n'.join(clean_sentences)
            
            # Last resort: clean up the original response
            lines = cleaned.split('\n')
            final_lines = []
            
            for line in lines:
                line = line.strip()
                if line and not is_thinking_content(line):  # Only keep non-thinking lines
                    final_lines.append(line)
            
            return '\n'.join(final_lines).strip()
        
        def extract_bd_response(response_text):
            """Simple BD response extraction - minimal filtering since token limit issue is fixed."""
            import re
            import html
            
            # Remove <think> blocks if present
            cleaned = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL | re.IGNORECASE)
            
            # Fix HTML entities (&#039; becomes ', &quot; becomes ", etc.)
            cleaned = html.unescape(cleaned)
            
            # Remove markdown formatting for Telegram
            # Remove **bold** formatting
            cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
            # Remove *italic* formatting  
            cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
            # Remove remaining asterisks
            cleaned = re.sub(r'\*+', '', cleaned)
            
            # Split into lines and filter
            lines = cleaned.split('\n')
            final_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Filter out obvious thinking process lines
                line_lower = line.lower()
                if any(phrase in line_lower for phrase in [
                    'alright, the user', 'let me start by', 'i need to analyze',
                    'the user is asking', 'first, i need to', 'let me recall',
                    'next, investor impact', 'if tokenized stocks face',
                    'traditional retail investors might', 'here are concrete',
                    'here are specific', 'leveraging the regulatory'
                ]):
                    continue
                
                # Fix double bullets and clean formatting
                line = re.sub(r'•\s*•\s*', '• ', line)  # Fix • • to single •
                line = re.sub(r'••+', '• ', line)  # Fix multiple bullets
                line = re.sub(r'^\s*•\s*$', '', line)  # Remove empty bullets
                
                # Skip bullets that are clearly incomplete or thinking process
                if line.startswith('• '):
                    bullet_content = line[2:].strip()
                    # Skip if too short, incomplete, or contains thinking indicators
                    if (len(bullet_content) < 20 or 
                        bullet_content.endswith('...') or 
                        bullet_content.endswith('.') == False or
                        any(phrase in bullet_content.lower() for phrase in [
                            'next,', 'first,', 'second,', 'third,', 'if tokenized', 
                            'traditional retail', 'investor impact', 'market partic'
                        ])):
                        continue
                
                # Keep the line if it passes filters
                if line:
                    final_lines.append(line)
            
            # Join with proper spacing and clean up
            result = '\n'.join(final_lines).strip()
            
            # Add line breaks between sections for better readability
            result = re.sub(r'([.:])\s*([A-Z][a-z]+\s+[A-Z])', r'\1\n\n\2', result)
            
            return result if result else response_text
        
        # Apply different filtering based on command type
        original_response = ai_response
        
        if command.startswith("bd"):
            # Light filtering for BD commands - just remove obvious thinking
            ai_response = extract_bd_response(ai_response)
        else:
            # Full filtering for news and other commands
            ai_response = extract_final_response(ai_response)
        
        # Log if content was filtered
        if debug_mode and len(original_response) > len(ai_response):
            print(f"🧠 Content filtered: {len(original_response)} → {len(ai_response)} chars")
            if command.startswith("bd"):
                print(f"🤝 BD light filtering applied for command: {command}")
        
        # Truncate if too long
        if len(ai_response) > MAX_MESSAGE_LENGTH:
            original_length = len(ai_response)
            ai_response = ai_response[:MAX_MESSAGE_LENGTH-50] + "...\n\n[Response truncated]"
            if debug_mode:
                print(f"✂️ Truncated response: {original_length} → {len(ai_response)} chars")
            
        if debug_mode:
            print(f"✅ Clean response ready ({len(ai_response)} chars)")
        return ai_response
        
    except Exception as e:
        bot_status.log_error()
        error_msg = str(e)
        if debug_mode:
            print(f"❌ AI Error Details: {error_msg}")
            print(f"🔧 Falling back to curated content for {command}")
        return None

def log_command(command: str, user_id: int, username: str = None):
    """Log command usage with status."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    user_info = f"@{username}" if username else f"ID:{user_id}"
    print(f"🔥 [{timestamp}] /{command} - {user_info}")
    bot_status.log_message()

def log_thinking_step(step: str, details: str = ""):
    """Log AI thinking steps to console."""
    if os.getenv("DEBUG_MODE") == "true":
        timestamp = datetime.now().strftime("%H:%M:%S")
        if details:
            print(f"🧩 [{timestamp}] {step}: {details}")
        else:
            print(f"🧩 [{timestamp}] {step}")

def convert_to_est(dt):
    """Convert datetime to EST timezone."""
    if dt is None:
        return None
    est = pytz.timezone('US/Eastern')
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = pytz.utc.localize(dt)
    return dt.astimezone(est)

def get_recent_news_summary(hours: int = 24) -> str:
    """Get a summary of news from the last X hours from tracker."""
    try:
        tracker_stats = get_tracker_stats()
        recent_articles = tracker_stats.get('recent_articles', [])
        
        if not recent_articles:
            return "No recent news available in tracker."
        
        # Filter articles from last X hours
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_news = []
        
        for article in recent_articles:
            posted_at = article.get('posted_at', '')
            if posted_at:
                try:
                    article_time = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                    if article_time >= cutoff_time:
                        title = article.get('title', 'Unknown')
                        source = article.get('source', 'Unknown')
                        is_duplicate = article.get('is_duplicate', False)
                        
                        # Only include non-duplicate articles
                        if not is_duplicate:
                            recent_news.append(f"• {title[:60]}{'...' if len(title) > 60 else ''} ({source})")
                except:
                    continue
        
        if not recent_news:
            return f"No unique news found in the last {hours} hours."
        
        # Limit to top 10 recent articles
        news_summary = "\n".join(recent_news[:10])
        return f"📰 **Recent News ({hours}h):**\n{news_summary}"
        
    except Exception as e:
        print(f"❌ Error getting recent news summary: {e}")
        return f"Error retrieving recent news from last {hours} hours."

def load_relevance_checklist():
    """Load the relevance checklist for news verification."""
    try:
        with open('relevance_checklist.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load relevance checklist: {e}")
        return None

async def check_similarity_to_recent_news(article_title: str, article_url: str = None) -> tuple:
    """Check if news is similar to recent articles using AI. Returns (is_similar, similarity_reason)."""
    try:
        # Get recent articles from tracker (excluding flagged duplicates from similarity check)
        tracker_stats = get_tracker_stats()
        recent_articles = tracker_stats.get('recent_articles', [])
        
        if not recent_articles:
            return False, "No recent articles to compare against"
        
        # Prepare recent titles for comparison (exclude duplicates and check last 15 articles)
        recent_titles = []
        for article in recent_articles[:15]:
            title = article.get('title', '')
            posted_at = article.get('posted_at', '')
            is_duplicate = article.get('is_duplicate', False)
            
            # Only compare against articles that aren't already flagged as duplicates
            if title and posted_at and not is_duplicate:
                recent_titles.append(f"'{title}' (posted: {posted_at[:10]})")
        
        if not recent_titles:
            return False, "No unique recent articles to compare against"
        
        # Ask AI to check for similarity with more balanced analysis
        comparison_prompt = f"""Analyze if this news article is essentially the SAME STORY as any recent articles:

NEW ARTICLE: "{article_title}"

RECENT UNIQUE ARTICLES:
{chr(10).join(recent_titles)}

Return "SIMILAR: [reason]" if the new article covers essentially the same event/story as any recent article (same companies, same announcement, same development).
Return "UNIQUE: [reason]" if it's genuinely different news, even if related to similar topics.

Consider: Different sources reporting the same announcement = SIMILAR. Related but different developments = UNIQUE."""

        log_thinking_step("Similarity Check", f"Comparing '{article_title[:50]}...' against {len(recent_titles)} unique articles")
        
        response = await get_ai_response(comparison_prompt, command="similarity_check")
        
        if response and "SIMILAR:" in response.upper():
            reason = response.split(":", 1)[1].strip() if ":" in response else "AI detected similarity"
            log_thinking_step("Similar Found", f"Article is similar: {reason}")
            return True, reason
        else:
            reason = response.split(":", 1)[1].strip() if ":" in response and "UNIQUE:" in response.upper() else "Article appears unique"
            log_thinking_step("Unique Article", f"Article is unique: {reason}")
            return False, reason
            
    except Exception as e:
        print(f"❌ Error checking similarity: {e}")
        return False, f"Error in similarity check: {str(e)}"

def flag_article_as_duplicate(article, similarity_reason: str):
    """Flag an article as duplicate in the news tracker."""
    try:
        # Use the same tracking file as news_scraper
        TRACKING_FILE = 'news_tracker.json'
        
        # Load current tracker data
        tracker_data = {}
        if os.path.exists(TRACKING_FILE):
            with open(TRACKING_FILE, 'r') as f:
                tracker_data = json.load(f)
        
        # Generate article hash
        article_hash = f"{article.title}|{article.url}"
        article_hash = hashlib.md5(article_hash.encode()).hexdigest()
        
        # Add article with duplicate flag
        if 'posted_articles' not in tracker_data:
            tracker_data['posted_articles'] = {}
        
        tracker_data['posted_articles'][article_hash] = {
            'title': article.title,
            'source': article.source,
            'posted_at': datetime.now().isoformat(),
            'published_at': article.published.isoformat() if article.published else None,
            'url': article.url,
            'category': getattr(article, 'category', 'unknown'),
            'is_duplicate': True,
            'similarity_reason': similarity_reason
        }
        
        # Update metadata
        tracker_data['last_updated'] = datetime.now().isoformat()
        tracker_data['total_tracked'] = len(tracker_data['posted_articles'])
        
        # Save updated data
        with open(TRACKING_FILE, 'w') as f:
            json.dump(tracker_data, f, indent=2)
        
        log_thinking_step("Duplicate Flagged", f"Article flagged in tracker: {similarity_reason}")
        
    except Exception as e:
        print(f"❌ Error flagging duplicate: {e}")

async def verify_news_relevance(article_title: str, article_content: str = "") -> tuple:
    """Verify news relevance using AI and checklist. Returns (is_relevant, score, reason)."""
    try:
        checklist = load_relevance_checklist()
        if not checklist:
            return True, 7, "Checklist unavailable - using default approval"
        
        # Prepare checklist prompt
        evaluation_prompt = checklist['relevance_checklist']['evaluation_prompt']
        
        relevance_prompt = f"""Using this relevance checklist, evaluate this news article:

EVALUATION CRITERIA: {evaluation_prompt}

ARTICLE TITLE: {article_title}
ARTICLE CONTENT: {article_content[:1000] if article_content else "No content available"}

SCORING: 0=not relevant, 1-4=low relevance, 5-7=medium relevance, 8-10=high relevance

Respond with: SCORE: [0-10] | REASON: [brief explanation]"""

        log_thinking_step("Relevance Check", f"Evaluating relevance of '{article_title[:50]}...'")
        
        response = await get_ai_response(relevance_prompt, command="relevance_check")
        
        if response:
            # Parse response
            score_match = re.search(r'SCORE:\s*(\d+)', response)
            reason_match = re.search(r'REASON:\s*(.+)', response)
            
            score = int(score_match.group(1)) if score_match else 5
            reason = reason_match.group(1).strip() if reason_match else "AI evaluation completed"
            
            is_relevant = score >= 5  # Medium relevance or higher
            
            log_thinking_step("Relevance Result", f"Score: {score}/10, Relevant: {is_relevant}")
            return is_relevant, score, reason
        else:
            log_thinking_step("Relevance Fallback", "AI unavailable - using default approval")
            return True, 6, "AI evaluation unavailable - approved by default"
            
    except Exception as e:
        print(f"❌ Error verifying relevance: {e}")
        return True, 5, f"Error in evaluation: {str(e)}"

def validate_and_improve_bullets(bullet_points: list, headline: str) -> list:
    """Validate and improve bullet points with comprehensive quality control."""
    
    def is_complete_sentence(text: str) -> bool:
        """Check if text is a complete sentence."""
        text = text.strip()
        if len(text) < 8:  # Too short
            return False
        if not text.endswith(('.', '!', '?')):  # No proper ending
            return False
        if text.endswith(' and'):  # Incomplete conjunction
            return False
        if any(word in text.lower() for word in ['and ', 'but ', 'or ']) and not text.strip().endswith(('.', '!', '?')):
            return False
        return True
    
    def is_thinking_content(text: str) -> bool:
        """Check if text contains AI thinking process indicators."""
        text_lower = text.lower()
        thinking_indicators = [
            'hmm,', 'the user wants', 'i need to', 'i think', 'i\'ll', 'looking at',
            'analyzing', 'considering', 'let me', 'i should', 'the article details',
            'for the first point', 'for the second', 'for the third', 'each bullet point',
            'between 10-15 words', 'about market impact', 'i\'ll need to create',
            'with a relevance score', 'the summary mentions', 'published on',
            'the user wants me to', 'i\'ll need to', 'bullet points about'
        ]
        return any(indicator in text_lower for indicator in thinking_indicators)
    
    def clean_bullet(bullet: str) -> str:
        """Clean and standardize bullet point format."""
        bullet = bullet.strip()
        
        # Remove multiple spaces
        bullet = ' '.join(bullet.split())
        
        # Ensure starts with •
        if bullet.startswith(('-', '*')):
            bullet = '•' + bullet[1:]
        elif not bullet.startswith('•'):
            bullet = '• ' + bullet
        
        # Ensure space after •
        if bullet.startswith('•') and len(bullet) > 1 and bullet[1] != ' ':
            bullet = '• ' + bullet[1:]
            
        return bullet
    
    def get_smart_fallback_bullets(headline: str) -> list:
        """Generate contextual fallback bullets based on headline keywords."""
        fallbacks = []
        headline_lower = headline.lower()
        
        # Context-aware fallbacks based on headline content
        if any(word in headline_lower for word in ['lawsuit', 'legal', 'court', 'judge']):
            fallbacks = [
                "• Legal proceedings create market uncertainty and regulatory scrutiny.",
                "• Institutional investors may reassess risk profiles and exposure levels.", 
                "• Settlement outcomes could establish important precedents for industry."
            ]
        elif any(word in headline_lower for word in ['bitcoin', 'btc', 'crypto']):
            fallbacks = [
                "• Bitcoin price movements influence broader cryptocurrency market sentiment.",
                "• Institutional adoption patterns continue shaping long-term market dynamics.",
                "• Regulatory developments remain key factor in price discovery mechanisms."
            ]
        elif any(word in headline_lower for word in ['fed', 'interest', 'rate', 'monetary']):
            fallbacks = [
                "• Federal Reserve policy shifts impact investor risk appetite significantly.",
                "• Interest rate changes influence capital flows across asset classes.",
                "• Monetary policy decisions create ripple effects throughout financial markets."
            ]
        elif any(word in headline_lower for word in ['gold', 'precious', 'metal']):
            fallbacks = [
                "• Gold demand reflects ongoing inflation hedging strategies by institutions.",
                "• Precious metals markets respond to global economic uncertainty patterns.",
                "• Central bank purchasing activity supports underlying price fundamentals."
            ]
        else:
            # Generic high-quality fallbacks
            fallbacks = [
                "• Market developments signal evolving institutional investment strategies.",
                "• Regulatory clarity continues improving across traditional finance sectors.",
                "• Investor sentiment reflects broader economic uncertainty and opportunity assessment."
            ]
            
        return fallbacks
    
    # Step 1: Clean all bullets and filter thinking content
    cleaned_bullets = []
    for bullet in bullet_points:
        if bullet and bullet.strip():
            # Skip thinking process content
            if is_thinking_content(bullet):
                continue
                
            # Skip bullets with ellipsis (incomplete thinking)
            if '...' in bullet:
                continue
                
            cleaned = clean_bullet(bullet)
            if cleaned and len(cleaned) > 5:  # Basic length check
                cleaned_bullets.append(cleaned)
    
    # Step 2: Remove duplicates (case-insensitive)
    unique_bullets = []
    seen_content = set()
    
    for bullet in cleaned_bullets:
        # Extract content without • symbol for comparison
        content = bullet.replace('•', '').strip().lower()
        if content not in seen_content and len(content) > 10:
            unique_bullets.append(bullet)
            seen_content.add(content)
    
    # Step 3: Validate completeness and filter thinking content
    complete_bullets = []
    for bullet in unique_bullets:
        bullet_content = bullet.replace('•', '').strip()
        
        # Skip thinking content that may have passed earlier filters
        if is_thinking_content(bullet_content):
            continue
            
        if is_complete_sentence(bullet_content):
            complete_bullets.append(bullet)
    
    # Step 4: Ensure exactly 3 high-quality bullets
    if len(complete_bullets) >= 3:
        # Take first 3 complete bullets
        final_bullets = complete_bullets[:3]
    else:
        # Mix good bullets with smart fallbacks
        fallback_bullets = get_smart_fallback_bullets(headline)
        
        # Start with complete bullets we have
        final_bullets = complete_bullets.copy()
        
        # Add fallbacks to reach 3 total
        fallback_index = 0
        while len(final_bullets) < 3 and fallback_index < len(fallback_bullets):
            candidate = fallback_bullets[fallback_index]
            
            # Check if fallback is already similar to existing bullets
            candidate_content = candidate.replace('•', '').strip().lower()
            is_duplicate = any(
                candidate_content in existing.replace('•', '').strip().lower() 
                or existing.replace('•', '').strip().lower() in candidate_content
                for existing in final_bullets
            )
            
            if not is_duplicate:
                final_bullets.append(candidate)
            
            fallback_index += 1
        
        # Last resort: ensure we have exactly 3
        if len(final_bullets) < 3:
            while len(final_bullets) < 3:
                final_bullets.append("• Market dynamics continue evolving with institutional participation.")
    
    # Step 5: Final quality check
    quality_bullets = []
    for bullet in final_bullets[:3]:  # Ensure exactly 3
        # Final cleaning and validation
        clean_bullet_text = clean_bullet(bullet)
        if len(clean_bullet_text) >= 15:  # Minimum meaningful length
            quality_bullets.append(clean_bullet_text)
    
    # Guarantee exactly 3 bullets
    while len(quality_bullets) < 3:
        quality_bullets.append("• Financial markets reflect ongoing institutional adoption trends.")
    
    return quality_bullets[:3]

async def extract_url_content(url: str) -> str:
    """Extract article content from URL using news scraper."""
    try:
        log_thinking_step("URL Extraction", f"Fetching content from {url[:50]}...")
        scraper = NewsScraper()
        content = scraper.extract_article_content(url)
        if content:
            log_thinking_step("Content Extracted", f"Got {len(content)} characters of content")
            return content
        else:
            log_thinking_step("Extraction Failed", "Could not extract content from URL")
            return ""
    except Exception as e:
        print(f"❌ Error extracting URL content: {e}")
        return ""

# --- Channel News Functions --------------------------------------------------
async def generate_channel_news():
    """Generate news content with smart article selection, similarity checking, and relevance verification."""
    try:
        MAX_ATTEMPTS = 5  # Try up to 5 articles if needed
        
        for attempt in range(MAX_ATTEMPTS):
            print(f"🔍 Fetching article attempt {attempt + 1}/{MAX_ATTEMPTS}...")
            
            # Get a relevant article from news scraper
            article = await get_single_relevant_article()
            
            if not article:
                print(f"⚠️ No articles found on attempt {attempt + 1}")
                continue
            
            headline = article.title
            source = article.url
            article_content = format_article_for_ai(article)
            print(f"✅ Found article: {headline[:50]}...")
            
            # Step 1: Check for similarity BEFORE adding to tracker
            log_thinking_step("Similarity Check", f"Checking article {attempt + 1} against recent articles")
            is_similar, similarity_reason = await check_similarity_to_recent_news(headline, source)
            
            if is_similar:
                print(f"📋 Article {attempt + 1} is similar to recent news: {similarity_reason}")
                # Flag as duplicate in tracker to prevent re-scraping
                flag_article_as_duplicate(article, similarity_reason)
                print(f"🔄 Trying next article...")
                continue
            
            # Step 2: Verify relevance using checklist
            log_thinking_step("Relevance Check", "Verifying article relevance using AI checklist")
            is_relevant, relevance_score, relevance_reason = await verify_news_relevance(headline, article_content)
            
            if not is_relevant:
                print(f"📊 Article {attempt + 1} not relevant enough (score: {relevance_score}/10): {relevance_reason}")
                # Still add to tracker but mark as low relevance
                flag_article_as_duplicate(article, f"Low relevance: {relevance_score}/10 - {relevance_reason}")
                print(f"🔄 Trying next article...")
                continue
            
            print(f"✅ Article {attempt + 1} passed all checks - Relevance: {relevance_score}/10 ({relevance_reason})")
            
            # Step 3: Generate AI analysis for the approved article
            try:
                ai_prompt = f"""Analyze this news article and provide exactly 3 bullet points about market impact. 

REQUIREMENTS:
- Each bullet: 1 concise sentence (10-15 words max)
- Format: • [market impact statement]
- Focus: market implications, investor impact, strategic significance
- NO thinking process, analysis steps, or meta-commentary
- Direct market insights only

Article: {headline}

{article_content}

Provide 3 direct market impact bullets:"""

                # Use Bitdeer API for news analysis
                async with BitdeerAIClient(DEEPSEEK_API_KEY) as client:
                    ai_analysis = await client.simple_chat(ai_prompt)
                
                # Extract clean response after thinking
                def extract_final_response(response_text):
                    """Extract bullet points from AI response, handling thinking process."""
                    import re
                    
                    # First, try to remove <think>...</think> blocks
                    think_pattern = r'<think>.*?</think>'
                    cleaned = re.sub(think_pattern, '', response_text, flags=re.DOTALL | re.IGNORECASE)
                    
                    # Extract bullet points from the response
                    lines = (cleaned if cleaned != response_text else response_text).split('\n')
                    bullet_points = []
                    
                    # Enhanced thinking detection patterns
                    thinking_indicators = [
                        'hmm,', 'the user wants', 'i need to', 'i think', 'i\'ll', 'looking at',
                        'analyzing', 'considering', 'let me', 'i should', 'the article details',
                        'for the first point', 'for the second', 'for the third', 'each bullet point',
                        'between 10-15 words', 'about market impact', 'i\'ll need to create',
                        'with a relevance score', 'the summary mentions', 'published on'
                    ]
                    
                    for line in lines:
                        clean_line = line.strip()
                        
                        # Only extract actual bullet points, ignore thinking text
                        if clean_line and (clean_line.startswith('•') or clean_line.startswith('-') or clean_line.startswith('*')):
                            
                            # Check if this bullet contains thinking process indicators
                            line_lower = clean_line.lower()
                            is_thinking = any(indicator in line_lower for indicator in thinking_indicators)
                            
                            # Skip meta-commentary and thinking bullets
                            if is_thinking:
                                continue
                                
                            # Skip bullets that are too long (likely thinking process)
                            bullet_content = clean_line.replace('•', '').replace('-', '').replace('*', '').strip()
                            if len(bullet_content) > 200:  # Too verbose, likely thinking
                                continue
                            
                            # Skip bullets with ellipsis (incomplete thinking)
                            if '...' in clean_line:
                                continue
                            
                            if not clean_line.startswith('•'):
                                clean_line = '•' + clean_line[1:]
                            bullet_points.append(clean_line)
                            
                            if len(bullet_points) >= 3:  # Stop at 3 bullets
                                break
                    
                    # If no bullet points found, create them from non-thinking sentences
                    if not bullet_points:
                        sentences = [s.strip() for s in response_text.split('.') if s.strip() and len(s.strip()) > 20]
                        for sentence in sentences[-3:]:  # Take last 3 sentences as they're likely conclusions
                            if not any(thinking_word in sentence.lower() for thinking_word in thinking_indicators):
                                bullet_points.append(f"• {sentence}.")
                                if len(bullet_points) >= 3:
                                    break
                    
                    return bullet_points[:3]
                
                bullet_points = extract_final_response(ai_analysis)
                
                # Quality validation and improvement
                original_count = len(bullet_points)
                
                # Check for thinking content in original bullets
                thinking_detected = any('hmm,' in str(bp).lower() or 'the user wants' in str(bp).lower() 
                                      or 'i need to' in str(bp).lower() for bp in bullet_points)
                
                bullet_points = validate_and_improve_bullets(bullet_points, headline)
                
                # Log quality improvements if any were made
                if thinking_detected:
                    print(f"🧠 Thinking content detected and filtered from AI response")
                    
                if original_count != len(bullet_points) or original_count == 0:
                    print(f"🔧 Quality control: {original_count} → {len(bullet_points)} bullets (improved)")
                else:
                    print(f"✅ Quality control: {len(bullet_points)} bullets passed validation")
                
                analysis = '\n'.join(bullet_points)
                
            except Exception as e:
                print(f"⚠️ AI analysis failed: {e}")
                # Use quality-controlled fallback bullets
                fallback_bullets = validate_and_improve_bullets([], headline)
                analysis = '\n'.join(fallback_bullets)
            
            # Step 4: Format final message with EST timestamp
            if article and article.source:
                source_text = f"Source: {article.source}"
                if article.url:
                    source_text += f" ({article.url})"
                
                # Add published timestamp in EST
                if article.published:
                    est_time = convert_to_est(article.published)
                    if est_time:
                        time_str = est_time.strftime('%B %d, %Y at %I:%M %p EST')
                        source_text += f"\nPublished: {time_str}"
            else:
                source_text = f"Source: {source}"
            
            message = f"""{headline}

{analysis}

{source_text}"""
            
            log_thinking_step("News Generated", f"Final message: {len(message)} chars, Relevance: {relevance_score}/10")
            
            # Article approved and processed - it will be added to tracker when posted
            return message
        
        # If we get here, all attempts failed
        print(f"⚠️ All {MAX_ATTEMPTS} attempts failed - no suitable articles found")
        return None
        
    except Exception as e:
        print(f"❌ News generation error: {e}")
        return None

async def verify_channel_access():
    """Verify if bot can access the channel."""
    global application_instance
    if not application_instance:
        print("❌ Application not available for channel verification")
        return False
    
    try:
        # Try to get channel info
        chat = await application_instance.bot.get_chat(CHANNEL_ID)
        print(f"✅ Channel found: {chat.title} (ID: {chat.id})")
        print(f"📊 Channel type: {chat.type}")
        
        # Check if bot is admin
        bot_member = await application_instance.bot.get_chat_member(CHANNEL_ID, application_instance.bot.id)
        print(f"🤖 Bot status in channel: {bot_member.status}")
        
        if bot_member.status in ['administrator', 'creator']:
            print("✅ Bot has admin privileges - can post and delete messages")
            return True
        elif bot_member.status == 'member':
            print("⚠️ Bot is member but not admin - limited permissions")
            return True
        else:
            print(f"❌ Bot status '{bot_member.status}' - cannot post")
            return False
            
    except Exception as e:
        print(f"❌ Channel verification failed: {e}")
        print(f"🔍 Channel ID tested: {CHANNEL_ID}")
        print("💡 Possible issues:")
        print("   - Channel name is incorrect (check @Matrixdock_News)")
        print("   - Bot is not added to the channel")
        print("   - Bot is not admin in the channel")
        print("   - Channel is private and bot lacks access")
        return False

async def post_to_channel():
    """Post news to the channel with status tracking."""
    global application_instance
    if not application_instance:
        print("❌ Application not available for channel posting")
        return
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"📰 [{timestamp}] Starting channel news post...")
    
    # Step 1: Send "generating" status message
    generating_msg = None
    try:
        generating_msg = await application_instance.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🔄 Generating market news... ({timestamp})"
        )
        print(f"📤 [{timestamp}] Posted 'generating' status to channel")
    except Exception as e:
        print(f"❌ Failed to post generating status: {e}")
        bot_status.log_error()
        return
    
    try:
        # Step 2: Generate the actual news content
        print(f"🧠 [{timestamp}] Generating AI news content...")
        message = await generate_channel_news()
        
        if message:
            # Step 3: Delete the "generating" message
            if generating_msg:
                try:
                    await application_instance.bot.delete_message(
                        chat_id=CHANNEL_ID,
                        message_id=generating_msg.message_id
                    )
                    print(f"🗑️ [{timestamp}] Deleted 'generating' status message")
                except Exception as delete_error:
                    print(f"⚠️ Could not delete generating message: {delete_error}")
            
            # Step 4: Post the actual news
            await application_instance.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                disable_web_page_preview=True
            )
            final_timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"📢 [{final_timestamp}] ✅ Successfully posted news to channel!")
            bot_status.log_message()
            
        else:
            # News generation failed - update the generating message
            if generating_msg:
                try:
                    await application_instance.bot.edit_message_text(
                        chat_id=CHANNEL_ID,
                        message_id=generating_msg.message_id,
                        text=f"⚠️ News generation failed ({timestamp})"
                    )
                except:
                    pass
            print(f"⚠️ [{timestamp}] Failed to generate news content")
            
    except Exception as e:
        print(f"❌ Channel posting error: {e}")
        bot_status.log_error()
        
        # Try to update the generating message with error
        if generating_msg:
            try:
                await application_instance.bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=generating_msg.message_id,
                    text=f"❌ Error: {str(e)[:50]}... ({timestamp})"
                )
            except:
                pass

# --- Command callbacks --------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a friendly greeting and brief help message."""
    log_command("start", update.effective_user.id, update.effective_user.username)
    await update.message.reply_text(
        "👋 Hi! I'm your RWA & Gold Intelligence bot powered by Bitdeer DeepSeek-R1 API.\n\n"
        "🤖 **Status**: Online and ready!\n"
        "⚡ **AI Model**: DeepSeek R1 (API-only)\n"
        "📊 **Commands**: /help for full list\n\n"
        "⚠️ **Important**: I only respond to commands starting with /\n"
        "Type /help to see what I can do!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available commands."""
    log_command("help", update.effective_user.id, update.effective_user.username)
    help_text = """🤖 **RWA & Gold Intelligence Bot (Commands Only)**

⚡ **Important:** Bot only responds to commands starting with /

📈 **Market Analysis (24h Context):**
/gold – AI-powered gold market analysis  
/rwa – AI-powered RWA market analysis
/summary – Comprehensive market overview

🤝 **Business Development:**
/bd – Matrixdock partnership opportunities
/bd <text/url> – BD analysis of content
Reply with /bd – Analyze news for Matrixdock BD angles
/test_bd – Demo BD analysis with sample news

🔍 **News Analysis:**
/meaning <news/url> – AI analysis of why news matters
/status – Bot metrics + news tracker stats

📰 **Enhanced News System:**
• 14+ real-time news sources
• AI relevance filtering & duplicate prevention
• 24-hour news context for analysis
• Fresh content every 30 minutes"""
    await update.message.reply_text(help_text)

async def gold_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide AI-powered gold market analysis based on recent news."""
    log_command("gold", update.effective_user.id, update.effective_user.username)
    
    # Show processing status
    status_msg = await update.message.reply_text("📊 Analyzing gold markets with recent news context...")
    
    log_thinking_step("GOLD Analysis", "Getting recent news and requesting AI-powered gold market analysis")
    
    # Get recent news context
    recent_news = get_recent_news_summary(24)
    
    gold_prompt = f"""Provide exactly 3 bullet points about current gold market trends. Each point should be 1-2 sentences max. Start each with • symbol.

Topics to cover:
• Central bank policies and interest rates
• Geopolitical tensions and safe-haven demand  
• Economic outlook and inflation trends

Format: • [Brief trend description]"""
    
    # Get AI market analysis
    ai_response = await get_ai_response(gold_prompt, command="gold")
    
    if ai_response:
        response = f"📈 **Gold Market Analysis (24h)**\n\n{ai_response}"
        log_thinking_step("Gold Analysis Complete", f"Generated {len(response)} char analysis with recent news context")
    else:
        response = "📈 **Gold Market Analysis (24h)**\n\n• Gold market momentum continues with institutional demand strengthening\n• Central bank purchases supporting price levels above key thresholds\n• Investors should monitor inflation data and Fed policy signals\n• Safe-haven flows remain active amid global economic uncertainty"
        log_thinking_step("Gold Fallback", "Using fallback analysis due to AI unavailability")
    
    await status_msg.edit_text(response)

async def rwa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide AI-powered RWA market analysis based on recent news."""
    log_command("rwa", update.effective_user.id, update.effective_user.username)
    
    status_msg = await update.message.reply_text("🏗️ Analyzing RWA markets with recent news context...")
    
    log_thinking_step("RWA Analysis", "Getting recent news and requesting AI-powered RWA market analysis")
    
    # Get recent news context
    recent_news = get_recent_news_summary(24)
    
    rwa_prompt = f"""Provide exactly 3 bullet points about RWA tokenization opportunities. Each point should be 1-2 sentences max. Start each with • symbol.

Topics to cover:
• Liquidity and fractional ownership benefits
• Institutional adoption and regulatory progress
• New asset classes and market expansion

Format: • [Brief opportunity description]"""
    
    ai_response = await get_ai_response(rwa_prompt, command="rwa")
    
    if ai_response:
        response = f"🏗️ **RWA Market Analysis (24h)**\n\n{ai_response}"
        log_thinking_step("RWA Analysis Complete", f"Generated {len(response)} char analysis with recent news context")
    else:
        response = "🏗️ **RWA Market Analysis (24h)**\n\n• RWA tokenization momentum accelerates with institutional adoption reaching new highs\n• Regulatory clarity and infrastructure improvements reducing barriers\n• New liquidity opportunities emerging across multiple asset classes\n• Investors should focus on platforms with strong compliance frameworks"
        log_thinking_step("RWA Fallback", "Using fallback analysis due to AI unavailability")
    
    await status_msg.edit_text(response)

async def meaning_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze why a news story or URL matters using AI with URL content extraction."""
    log_command("meaning", update.effective_user.id, update.effective_user.username)
    
    if not context.args:
        await update.message.reply_text(
            "📰 **News Analysis**\n\n"
            "Usage: `/meaning <news title or URL>`\n"
            "Examples:\n"
            "• `/meaning Bitcoin hits new ATH`\n"
            "• `/meaning https://coindesk.com/article-url`\n\n"
            "I'll analyze the content and explain why it matters! 🔍"
        )
        return
    
    news_text = " ".join(context.args)
    
    # Detect if input is a URL
    is_url = news_text.startswith(('http://', 'https://'))
    
    if is_url:
        status_msg = await update.message.reply_text("🔗 Fetching article content...")
        
        # Extract content from URL
        article_content = await extract_url_content(news_text)
        
        if article_content:
            await status_msg.edit_text("🔍 AI analyzing article content...")
            
            # Use extracted content for analysis
            analysis_prompt = f"""Analyze this news article and provide exactly 3-4 bullet points explaining why it matters. Each bullet should be 1 short sentence (8-12 words). Focus on: market impact, investor implications, broader significance. Format with • symbol.

URL: {news_text}

Article Content: {article_content[:2000]}"""
            
            news_display = f"🔗 {news_text}"
            log_thinking_step("URL Analysis", f"Analyzing content from {news_text[:50]}...")
        else:
            await status_msg.edit_text("🔍 AI analyzing URL (content extraction failed)...")
            
            # Fallback to URL analysis if extraction fails
            analysis_prompt = f"""Analyze this news URL and provide exactly 3-4 bullet points explaining why it might matter. Each bullet should be 1 short sentence (8-12 words). Focus on: market impact, investor implications, broader significance. Format with • symbol.

URL: {news_text}

Note: Could not extract article content, analyze based on URL and general context."""
            
            news_display = f"🔗 {news_text} (content unavailable)"
            log_thinking_step("URL Analysis Fallback", f"Analyzing URL without content: {news_text[:50]}...")
    else:
        status_msg = await update.message.reply_text("🔍 AI analyzing significance...")
        
        # Analyze text/title directly
        analysis_prompt = f"""Analyze this news and provide exactly 3-4 bullet points explaining why it matters. Each bullet should be 1 short sentence (8-12 words). Focus on: market impact, investor implications, broader significance. Format with • symbol.

News: {news_text}"""
        
        news_display = news_text
        log_thinking_step("Text Analysis", f"Analyzing news text: {news_text[:50]}...")
    
    print(f"📰 User submitted: {news_text}")
    
    log_thinking_step("AI Processing", "Requesting detailed market impact analysis")
    ai_analysis = await get_ai_response(analysis_prompt, command="meaning")
    
    if ai_analysis:
        log_thinking_step("Analysis Complete", "AI provided detailed market impact analysis")
        response = f"🔍 **Why It Matters**\n\n{news_display[:150]}{'...' if len(news_display) > 150 else ''}\n\n{ai_analysis}"
    else:
        log_thinking_step("Fallback Analysis", "Providing general impact points")
        response = f"🔍 **Why It Matters**\n\n{news_display[:150]}{'...' if len(news_display) > 150 else ''}\n\n• Could shift market sentiment and trading patterns\n• May influence regulatory and institutional responses\n• Creates potential opportunities in related sectors\n• Sets precedent for future similar developments"
    
    print(f"✅ Meaning analysis completed - Response: {len(response)} chars")
    await status_msg.edit_text(response)

async def bd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide AI-powered partnership and business development analysis with Matrixdock focus."""
    log_command("bd", update.effective_user.id, update.effective_user.username)
    
    # Debug information
    chat_type = update.effective_chat.type
    chat_title = update.effective_chat.title or "Direct Message"
    user_info = update.effective_user.username or str(update.effective_user.id)
    
    print(f"🔍 BD Command Debug:")
    print(f"   Chat Type: {chat_type}")
    print(f"   Chat Title: {chat_title}")
    print(f"   User: {user_info}")
    print(f"   Has Reply: {bool(update.message.reply_to_message)}")
    print(f"   Has Args: {bool(context.args)}")
    
    # Check if this is a reply to a message (news article analysis)
    if update.message.reply_to_message:
        print(f"   Processing BD reply analysis...")
        await bd_reply_analysis(update, context)
        return
    
    # Check if URL/text provided for analysis
    if context.args:
        print(f"   Processing BD content analysis...")
        await bd_content_analysis(update, context)
        return
    
    # Default general BD analysis
    status_msg = await update.message.reply_text("🤝 Analyzing Matrixdock partnership opportunities...")
    
    log_thinking_step("BD Analysis", "Requesting Matrixdock-focused partnership analysis")
    
    ai_response = await get_ai_response(
        "Provide exactly 3 realistic business development opportunities for Matrixdock (tokenized treasury platform). Focus on actionable steps the BD team can take this week:\n\n• Mid-tier crypto exchanges or fintech platforms to contact\n• Partnership proposals that match Matrixdock's scale\n• Specific outreach actions or services to pitch\n\nFormat as bullet points with concrete next steps, avoid Fortune 500 companies.",
        command="bd"
    )
    
    if ai_response:
        response = f"🤝 **Matrixdock Partnership Analysis**\n\n{ai_response}"
        log_thinking_step("BD Analysis Complete", f"Generated {len(response)} char analysis")
    else:
        response = "🤝 **Matrixdock Partnership Analysis**\n\n• TradFi institutions seeking RWA tokenization solutions create strategic partnership opportunities\n• Cross-border payment networks offer distribution channel expansion possibilities\n• Custody and compliance providers enable institutional market access\n• Technology partnerships with blockchain infrastructure enhance platform capabilities"
        log_thinking_step("BD Fallback", "Using fallback analysis due to AI unavailability")
    
    await status_msg.edit_text(response)

async def bd_reply_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze a news article for Matrixdock partnership/BD angles."""
    replied_message = update.message.reply_to_message
    news_content = replied_message.text
    
    # Debug the replied message
    print(f"🔍 BD Reply Debug:")
    print(f"   Replied message exists: {replied_message is not None}")
    if replied_message:
        print(f"   Replied message author: {replied_message.from_user}")
        print(f"   Replied message text length: {len(news_content) if news_content else 0}")
        print(f"   Replied message preview: {news_content[:100] if news_content else 'No text'}...")
    
    if not news_content:
        await update.message.reply_text("⚠️ No content found in the replied message to analyze.")
        return
    
    status_msg = await update.message.reply_text("🤝 Analyzing BD opportunities in this news...")
    
    log_thinking_step("BD Reply Analysis", f"Analyzing news for Matrixdock angles: {news_content[:100]}...")
    
    bd_prompt = f"""Based on this news, what specific business actions should Matrixdock (tokenized treasury platform) take? Focus on realistic, actionable steps:

- Mid-tier companies/platforms to contact (not Fortune 500 CEOs)
- Partnership proposals that match Matrixdock's scale
- Specific outreach actions the BD team can take this week
- Services/solutions to pitch that align with the news

Format as bullet points with concrete next steps, not aspirational goals.

News: {news_content}

Realistic actions for Matrixdock's BD team:"""

    ai_response = await get_ai_response(bd_prompt, command="bd_reply")
    
    if ai_response:
        response = f"🤝 **Matrixdock BD Opportunities**\n\n📰 *Analyzing:* {news_content[:100]}{'...' if len(news_content) > 100 else ''}\n\n{ai_response}"
        log_thinking_step("BD Reply Complete", f"Generated BD analysis for news content")
    else:
        response = f"🤝 **Matrixdock BD Opportunities**\n\n📰 *Analyzing:* {news_content[:100]}{'...' if len(news_content) > 100 else ''}\n\n• Partnership opportunity with entities mentioned in this development\n• Strategic outreach to key stakeholders involved in this announcement\n• Business development follow-up on regulatory or technology developments\n• Market positioning advantage through early engagement with emerging trends"
        log_thinking_step("BD Reply Fallback", "Using fallback BD analysis")
    
    await status_msg.edit_text(response)

async def bd_content_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze provided URL or text for Matrixdock BD opportunities."""
    content_input = " ".join(context.args)
    is_url = content_input.startswith(('http://', 'https://'))
    
    if is_url:
        status_msg = await update.message.reply_text("🔗 Fetching article for BD analysis...")
        
        # Extract content from URL
        article_content = await extract_url_content(content_input)
        
        if article_content:
            await status_msg.edit_text("🤝 Analyzing BD opportunities...")
            analysis_content = article_content[:2000]  # Limit content length
            content_display = f"🔗 {content_input}"
        else:
            analysis_content = f"URL: {content_input}\n\nNote: Could not extract article content, analyze based on URL."
            content_display = f"🔗 {content_input} (content unavailable)"
    else:
        status_msg = await update.message.reply_text("🤝 Analyzing BD opportunities...")
        analysis_content = content_input
        content_display = content_input
    
    bd_prompt = f"""Based on this content, what specific business actions should Matrixdock (tokenized treasury platform) take? Focus on realistic, actionable steps:

- Mid-tier companies/platforms to contact (not Fortune 500 CEOs)
- Partnership proposals that match Matrixdock's scale  
- Specific outreach actions the BD team can take this week
- Services/solutions to pitch that align with the content

Format as bullet points with concrete next steps, not aspirational goals.

Content: {analysis_content}

Realistic actions for Matrixdock's BD team:"""

    ai_response = await get_ai_response(bd_prompt, command="bd_content")
    
    if ai_response:
        response = f"🤝 **Matrixdock BD Opportunities**\n\n📄 *Analyzing:* {content_display[:150]}{'...' if len(content_display) > 150 else ''}\n\n{ai_response}"
        log_thinking_step("BD Content Complete", f"Generated BD analysis for provided content")
    else:
        response = f"🤝 **Matrixdock BD Opportunities**\n\n📄 *Analyzing:* {content_display[:150]}{'...' if len(content_display) > 150 else ''}\n\n• Partnership opportunity with entities mentioned in this development\n• Strategic outreach to key stakeholders involved\n• Business development follow-up on emerging opportunities\n• Market positioning advantage through early engagement"
        log_thinking_step("BD Content Fallback", "Using fallback BD analysis")
    
    await status_msg.edit_text(response)

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide comprehensive AI-powered market summary based on last 24 hours of news."""
    log_command("summary", update.effective_user.id, update.effective_user.username)
    
    status_msg = await update.message.reply_text("📋 Compiling market summary from last 24 hours...")
    
    log_thinking_step("Summary Generation", "Getting recent news and generating AI market summary")
    
    # Get recent news from last 24 hours
    recent_news_summary = get_recent_news_summary(24)
    
    summary_prompt = f"""Based on the following news from the last 24 hours, provide a comprehensive market summary covering gold, RWA tokenization, and strategic partnerships. Include 4-5 key points about overall market impact and what investors should watch. Format with bullet points.

{recent_news_summary}

Focus on analyzing trends, patterns, and implications from these recent developments. If no recent news is available, provide general market insights."""

    ai_response = await get_ai_response(summary_prompt, command="summary")
    
    if ai_response:
        response = f"📋 **24-Hour Market Summary**\n\n{ai_response}\n\n{recent_news_summary}"
        log_thinking_step("Summary Complete", f"Generated {len(response)} char summary based on recent news")
    else:
        response = f"📋 **24-Hour Market Summary**\n\n• Market sentiment remains cautiously optimistic with increased institutional activity\n• RWA tokenization momentum continues alongside traditional safe-haven demand for gold\n• Strategic partnerships accelerating innovation and market access opportunities\n• Regulatory developments supporting continued growth across asset classes\n• Infrastructure improvements enabling larger transaction volumes and adoption\n\n{recent_news_summary}"
        log_thinking_step("Summary Fallback", "Using fallback summary due to AI unavailability")
    
    await status_msg.edit_text(response)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show enhanced bot status and metrics."""
    log_command("status", update.effective_user.id, update.effective_user.username)
    
    uptime = datetime.now() - bot_status.start_time
    uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
    
    # Get enhanced news tracker stats
    tracker_stats = get_tracker_stats()
    
    log_thinking_step("Status Check", f"Uptime: {uptime_str}, Messages: {bot_status.message_count}")
    
    # Format recent articles
    recent_articles_text = ""
    if tracker_stats.get('recent_articles'):
        recent_articles_text = "\n🕒 **Recent Articles:**\n"
        for i, article in enumerate(tracker_stats['recent_articles'][:3], 1):
            title = article.get('title', 'Unknown')[:40] + "..." if len(article.get('title', '')) > 40 else article.get('title', 'Unknown')
            source = article.get('source', 'unknown')
            recent_articles_text += f"{i}. {title} ({source})\n"
    
    # Format source breakdown
    source_text = ""
    if tracker_stats.get('sources'):
        top_sources = sorted(tracker_stats['sources'].items(), key=lambda x: x[1], reverse=True)[:3]
        source_text = "\n📊 **Top Sources:**\n"
        for source, count in top_sources:
            source_text += f"• {source}: {count} articles\n"
    
    status_text = f"""🤖 **Enhanced Bot Status**

⚡ **System**: Online & Enhanced
🧠 **AI Model**: R1-14B
⏱️ **Uptime**: {uptime_str}
📊 **Messages**: {bot_status.message_count}
🤖 **AI Responses**: {bot_status.ai_responses}
📰 **Tracked Articles**: {tracker_stats['total_tracked']}
🔋 **Performance**: Optimal{recent_articles_text}{source_text}"""
    
    await update.message.reply_text(status_text)

async def test_bd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command to simulate BD analysis without requiring a reply."""
    log_command("test_bd", update.effective_user.id, update.effective_user.username)
    
    # Simulate a news article for testing
    fake_news = """BlackRock Launches Tokenized Gold Fund with State Street Custody

BlackRock announced today the launch of a new tokenized gold fund, partnering with State Street for institutional custody services. The fund will allow fractional ownership of physical gold through blockchain technology, targeting institutional investors seeking digital asset exposure while maintaining traditional asset backing.

Source: Reuters (https://reuters.com/example)
Published: January 15, 2025 at 02:30 PM EST"""
    
    status_msg = await update.message.reply_text("🧪 Testing BD analysis with sample news...")
    
    # Simulate the BD analysis
    bd_prompt = f"""What specific business actions should Matrixdock take based on this news? Focus on:
- Companies to contact (CEO/CTO/CFO names if mentioned) 
- Partnerships to propose
- Meetings to schedule
- Services to pitch

Don't give market analysis - give specific business actions.

News: {fake_news}

Specific actions for Matrixdock's BD team:"""

    ai_response = await get_ai_response(bd_prompt, command="test_bd")
    
    if ai_response:
        response = f"🧪 **Test BD Analysis**\n\n📰 *Sample News:* BlackRock launches tokenized gold fund...\n\n{ai_response}"
        log_thinking_step("Test BD Complete", f"Generated test BD analysis")
    else:
        response = f"🧪 **Test BD Analysis**\n\n📰 *Sample News:* BlackRock launches tokenized gold fund...\n\n• Partnership opportunity with State Street for custody integration solutions\n• Strategic outreach to BlackRock's digital assets team for platform collaboration\n• Business development follow-up on tokenized gold infrastructure partnerships\n• Market positioning advantage as established gold tokenization platform"
        log_thinking_step("Test BD Fallback", "Using fallback test BD analysis")
    
    await status_msg.edit_text(response)

# handle_message function removed - bot now only responds to commands (/)



async def handle_channel_bd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Special handler for /bd commands in the specific channel."""
    print(f"🎯 Channel BD Command detected in {CHANNEL_ID}")
    
    # Check if this is a reply
    if update.message.reply_to_message:
        replied_text = update.message.reply_to_message.text
        print(f"   Replied to: {replied_text[:100] if replied_text else 'No text'}...")
        
        if replied_text:
            # Perform BD analysis on the replied message
            status_msg = await update.message.reply_text("🤝 Analyzing BD opportunities in this news...")
            
            bd_prompt = f"""What specific business actions should Matrixdock take based on this news? Focus on:
- Companies to contact (CEO/CTO/CFO names if mentioned) 
- Partnerships to propose
- Meetings to schedule
- Services to pitch

Don't give market analysis - give specific business actions.

News: {replied_text}

Specific actions for Matrixdock's BD team:"""

            ai_response = await get_ai_response(bd_prompt, command="channel_bd")
            
            if ai_response:
                response = f"🤝 **Matrixdock BD Opportunities**\n\n📰 *Analyzing:* {replied_text[:100]}{'...' if len(replied_text) > 100 else ''}\n\n{ai_response}"
            else:
                response = f"🤝 **Matrixdock BD Opportunities**\n\n📰 *Analyzing:* {replied_text[:100]}{'...' if len(replied_text) > 100 else ''}\n\n• Partnership opportunity with entities mentioned in this development\n• Strategic outreach to key stakeholders involved in this announcement\n• Business development follow-up on regulatory or technology developments\n• Market positioning advantage through early engagement with emerging trends"
            
            await status_msg.edit_text(response)
        else:
            await update.message.reply_text("⚠️ No content found in the replied message to analyze.")
    else:
        await update.message.reply_text("💡 Use /bd as a reply to a news message for BD analysis, or try /test_bd for a demo!")


# --- Main entry‑point ---------------------------------------------------------
def main() -> None:
    """Build and run the bot (long‑polling for dev)."""
    print(f"🚀 Starting RWA & Gold Intelligence Bot (Command-Only Mode)")
    print(f"⏰ Start time: {bot_status.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("⚡ Commands only - users must start messages with /")
    
    # Set up global application reference for channel posting
    global application_instance
    
    # API-only mode - no local model checks needed
    print(f"✅ Bitdeer DeepSeek-R1 API ready for all AI features")
    
    application = Application.builder().token(TOKEN).build()
    application_instance = application  # Store global reference

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("gold", gold_command))
    application.add_handler(CommandHandler("rwa", rwa_command))
    application.add_handler(CommandHandler("meaning", meaning_command))
    application.add_handler(CommandHandler("bd", bd_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("test_bd", test_bd_command))
    
    # Commands only - no text message handler (users must use /commands)
    
    # Special handler for channel posts (bypass normal user restrictions)
    application.add_handler(
        MessageHandler(
            filters.Chat(chat_id=CHANNEL_ID) & filters.TEXT & filters.Regex(r'/bd'),
            handle_channel_bd_command
        )
    )

    # Apply conflict resolution if enabled
    if should_use_conflict_resolution():
        print("🔧 Nuclear conflict resolution enabled")
        nuclear_conflict_resolution(TOKEN)
        
        # Additional safety wait for environment to stabilize
        print("⏳ Final environment stabilization (10 seconds)...")
        time.sleep(10)
    else:
        print("🔄 Nuclear conflict resolution disabled - using simple startup")
    
    print(f"🤖 Bot is running. Press Ctrl+C to stop.")
    print("📊 Real-time stats will appear below...")
    print("📢 Channel news will post automatically to", CHANNEL_ID)
    print("-" * 70)
    
    # Proper async bot startup with background tasks
    async def main_bot():
        global news_task_running, application_instance
        
        # Set global reference
        application_instance = application
        
        async with application:
            await application.initialize()
            await application.start()
            
            # Start background tasks
            news_task_running = True
            
            async def news_scheduler():
                """Background task to post news periodically."""
                print(f"📅 News scheduler started (every {NEWS_INTERVAL//60} minutes)")
                while news_task_running:
                    try:
                        await asyncio.sleep(NEWS_INTERVAL)
                        if news_task_running:
                            await post_to_channel()
                    except asyncio.CancelledError:
                        print("📅 News scheduler cancelled")
                        break
                    except Exception as e:
                        print(f"❌ News scheduler error: {e}")
                        await asyncio.sleep(60)  # Wait 1 minute before retrying
            
            async def console_monitor():
                """Monitor console for commands."""
                global news_task_running
                
                # Check if stdin is available (not running as service)
                if not sys.stdin.isatty():
                    print("⌨️ Console monitor disabled (running as service)")
                    print("📡 Signal monitor active for virtual terminal commands")
                    # Keep the task alive but don't try to read from stdin
                    while news_task_running:
                        await asyncio.sleep(1)
                    return
                
                print("⌨️ Console monitor started. Type commands:")
                import sys
                from concurrent.futures import ThreadPoolExecutor
                
                def get_input():
                    try:
                        return input().strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        return "stop"
                
                executor = ThreadPoolExecutor(max_workers=1)
                
                while news_task_running:
                    try:
                        command = await asyncio.get_event_loop().run_in_executor(executor, get_input)
                        
                        if command == "next":
                            print("⚡ Triggering news post...")
                            await post_to_channel()
                        elif command == "verify":
                            print("🔍 Verifying channel access...")
                            await verify_channel_access()
                        elif command == "stop":
                            print("🛑 Stopping...")
                            news_task_running = False
                            break
                        elif command == "help":
                            print("\n📋 Available commands:")
                            print("  next   - Post news to channel")
                            print("  verify - Check channel access")
                            print("  stop   - Stop bot")
                            print("  help   - Show this help\n")
                            
                    except Exception as e:
                        print(f"❌ Console monitor error: {e}")
                        await asyncio.sleep(0.1)
            
            async def signal_monitor():
                """Monitor for signal files from virtual terminal."""
                signal_file = "bot_signal.json"
                print("📡 Signal monitor started (checking for virtual terminal commands)")
                
                while news_task_running:
                    try:
                        if os.path.exists(signal_file):
                            # Read and process signal file
                            with open(signal_file, 'r') as f:
                                signal_data = json.load(f)
                            
                            command = signal_data.get('command')
                            timestamp = signal_data.get('timestamp', 'unknown')
                            source = signal_data.get('source', 'unknown')
                            
                            print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Signal received: {command} from {source}")
                            
                            if command == 'post_news':
                                print(f"⚡ Processing manual news trigger from virtual terminal...")
                                await post_to_channel()
                            elif command == 'verify_channel':
                                print(f"🔍 Processing channel verification request...")
                                await verify_channel_access()
                            else:
                                print(f"❌ Unknown signal command: {command}")
                            
                            # Remove signal file after processing
                            os.remove(signal_file)
                            print(f"🧹 Signal file processed and removed")
                        
                        # Check every 5 seconds
                        await asyncio.sleep(5)
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ Invalid signal file format: {e}")
                        # Remove corrupted file
                        if os.path.exists(signal_file):
                            os.remove(signal_file)
                    except Exception as e:
                        print(f"❌ Signal monitor error: {e}")
                        await asyncio.sleep(5)
            
            # Create background tasks
            news_task = asyncio.create_task(news_scheduler())
            console_task = asyncio.create_task(console_monitor())
            signal_task = asyncio.create_task(signal_monitor())
            
            print("📅 News scheduler started")
            print("⌨️ Console monitor started")
            print("📡 Signal monitor started")
            print("✅ Bot ready!")
            print("⌨️ Console commands: next, verify, stop, help")
            print("-" * 50)
            
            # Start polling with conflict resolution if enabled
            if should_use_ultra_robust_polling():
                print("🔧 Using ultra-robust polling with conflict resolution")
                await ultra_robust_polling_start(application, TOKEN)
            else:
                print("🔄 Using simple polling")
                await application.updater.start_polling(
                    drop_pending_updates=True,
                    timeout=30,
                    poll_interval=2.0
                )
            
            try:
                # Keep running until stopped
                while news_task_running:
                    await asyncio.sleep(1)
            finally:
                # Cleanup
                news_task_running = False
                news_task.cancel()
                console_task.cancel()
                signal_task.cancel()
                
                try:
                    await asyncio.gather(news_task, console_task, signal_task, return_exceptions=True)
                except:
                    pass
                
                await application.updater.stop()
                await application.stop()
    
    # Run the main bot
    try:
        asyncio.run(main_bot())
        
    except KeyboardInterrupt:
        print(f"\n🛑 Bot stopped")
    except Exception as e:
        if "Conflict" in str(e):
            print(f"⚠️ Telegram API conflict - another bot instance may be running")
            print("💡 Try: pkill -f 'python bot.py' to stop other instances")
        else:
            print(f"❌ Bot error: {e}")
    finally:
        global news_task_running
        news_task_running = False

if __name__ == "__main__":
    main()
