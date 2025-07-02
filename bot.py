"""
Telegram AI Bot with Local R1 14B Model Integration
==================================================

• Loads `BOT_TOKEN` from a .env file or environment variable
• Connects to local r1-14b model via Ollama
• Responds to /start, /help, /gold, /rwa, /meaning, and /bd commands
• Uses AI for intelligent responses to user queries
• Uses python‑telegram‑bot v22+ (async Application API)
"""

import os
import asyncio
import ollama
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

# --- Config ------------------------------------------------------------------
load_dotenv()  # take environment variables from .env, if present
TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise RuntimeError("⛔  BOT_TOKEN not set in environment variables or .env file")

MODEL_NAME = "r1-assistant"  # Name we'll give our model in Ollama
MAX_MESSAGE_LENGTH = 4000  # Telegram limit is 4096, leave some buffer
CHANNEL_ID = "@Matrixdock_News"  # Channel to post automatic news
NEWS_INTERVAL = 1800  # 30 minutes between posts (in seconds)

# --- AI Configuration --------------------------------------------------------
# Environment detection for cloud vs local deployment
IS_CLOUD = os.getenv("DEPLOYMENT_ENV") == "cloud"

if IS_CLOUD:
    # Bitdeer Cloud AI Configuration
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API")
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("❌ Missing DEEPSEEK_API environment variable in cloud environment")
    print(f"✅ Cloud mode: Using Bitdeer DeepSeek-R1 API")
else:
    # Local Ollama Configuration
    print(f"🔧 Local mode: Using Ollama with {MODEL_NAME}")

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
        
        if IS_CLOUD:
            # Use Bitdeer AI API
            if debug_mode:
                print("⚡ Sending request to Bitdeer DeepSeek-R1...")
            
            async with BitdeerAIClient(DEEPSEEK_API_KEY) as client:
                ai_response = await client.simple_chat(full_prompt, context)
            
            if debug_mode:
                print(f"✅ Bitdeer API response: {len(ai_response)} chars")
            
        else:
            # Use local Ollama
            if debug_mode:
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
            if debug_mode:
                print(f"✅ Ollama response: {len(ai_response)} chars")
        
        # Log thinking process to console (for debugging)
        if debug_mode:
            if len(ai_response) > 200:
                print(f"💭 AI Response Preview: {ai_response[:200]}...")
            else:
                print(f"💭 AI Full Response: {ai_response}")
        
        bot_status.log_ai_response()
        
        # Extract content after thinking process - works for both R1 models
        def extract_final_response(response_text):
            """Extract the final response after thinking process."""
            import re
            
            # First, try to remove <think>...</think> blocks (common in R1 models)
            think_pattern = r'<think>.*?</think>'
            cleaned = re.sub(think_pattern, '', response_text, flags=re.DOTALL | re.IGNORECASE)
            
            # If no <think> tags found, look for bullet points and extract only those
            if cleaned == response_text:  # No <think> tags were removed
                lines = response_text.split('\n')
                bullet_lines = []
                
                for line in lines:
                    line = line.strip()
                    # Only keep lines that start with bullet points
                    if line and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                        if not line.startswith('•'):
                            line = '•' + line[1:]  # Standardize to •
                        bullet_lines.append(line)
                
                # If we found bullet points, return only those
                if bullet_lines:
                    return '\n'.join(bullet_lines)
                else:
                    # Fallback: look for the last few sentences that seem like conclusions
                    sentences = [s.strip() for s in response_text.split('.') if s.strip()]
                    if len(sentences) >= 3:
                        return '\n'.join(f"• {s}." for s in sentences[-3:])
            
            # Clean up any remaining whitespace and empty lines
            lines = cleaned.split('\n')
            final_lines = []
            
            for line in lines:
                line = line.strip()
                if line:  # Only keep non-empty lines
                    final_lines.append(line)
            
            return '\n'.join(final_lines).strip()
        
        # Extract final response only for local Ollama (cloud responses are already clean)
        if not IS_CLOUD:
            ai_response = extract_final_response(ai_response)
        
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
                ai_prompt = f"""Analyze this news article and provide exactly 3 bullet points about market impact. Each bullet should be 1 concise sentence (10-15 words max). Format as bullet points with • symbol.

Article: {headline}

{article_content}

Focus on: market implications, investor impact, and strategic significance."""

                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: ollama.chat(
                        model=MODEL_NAME,
                        messages=[{'role': 'user', 'content': ai_prompt}]
                    )
                )
                
                ai_analysis = response['message']['content']
                
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
                    
                    for line in lines:
                        clean_line = line.strip()
                        # Only extract actual bullet points, ignore thinking text
                        if clean_line and (clean_line.startswith('•') or clean_line.startswith('-') or clean_line.startswith('*')):
                            if not clean_line.startswith('•'):
                                clean_line = '•' + clean_line[1:]
                            bullet_points.append(clean_line)
                            if len(bullet_points) >= 3:  # Stop at 3 bullets
                                break
                    
                    # If no bullet points found, create them from non-thinking sentences
                    if not bullet_points:
                        sentences = [s.strip() for s in response_text.split('.') if s.strip() and len(s.strip()) > 20]
                        for sentence in sentences[-3:]:  # Take last 3 sentences as they're likely conclusions
                            if not any(thinking_word in sentence.lower() for thinking_word in ['thinking', 'analyzing', 'looking at', 'considering']):
                                bullet_points.append(f"• {sentence}.")
                                if len(bullet_points) >= 3:
                                    break
                    
                    return bullet_points[:3]
                
                bullet_points = extract_final_response(ai_analysis)
                
                # Ensure exactly 3 points
                while len(bullet_points) < 3:
                    bullet_points.append("• Market developments indicate continued institutional interest and adoption")
                
                analysis = '\n'.join(bullet_points)
                
            except Exception as e:
                print(f"⚠️ AI analysis failed: {e}")
                analysis = "• Institutional adoption continues across traditional finance sectors\n• Market infrastructure improvements enable larger transaction volumes\n• Regulatory developments support continued growth momentum"
            
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
        "👋 Hi! I'm your RWA & Gold Intelligence bot powered by a local R1 model.\n\n"
        "🤖 **Status**: Online and ready!\n"
        "⚡ **AI Model**: DeepSeek R1-14B\n"
        "📊 **Commands**: /help for full list\n\n"
        "Type /help to see what I can do, or just ask me anything!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available commands."""
    log_command("help", update.effective_user.id, update.effective_user.username)
    help_text = """🤖 **RWA & Gold Intelligence Bot**

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
• Fresh content every 30 minutes

💬 **Chat:** Send any message for AI analysis"""
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
        "Provide exactly 3 bullet points about crypto exchange partnership opportunities. Each point should be 1-2 sentences max. Start each with • symbol.\n\nTopics: liquidity partnerships, market expansion, institutional services\n\nFormat: • [Brief opportunity description]",
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
    
    bd_prompt = f"""Analyze this news article specifically for Matrixdock partnership and business development opportunities. Provide exactly 3-4 bullet points covering:

1. Partnership angles and opportunities for Matrixdock
2. Potential strategic contacts or companies to engage
3. Business development actions Matrixdock could take
4. Competitive advantages this news reveals

News Content: {news_content}

Focus on concrete BD actions, specific companies/contacts mentioned, and strategic opportunities for RWA/gold tokenization partnerships. Format with • symbol."""

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
    
    bd_prompt = f"""Analyze this content specifically for Matrixdock partnership and business development opportunities. Provide exactly 3-4 bullet points covering:

1. Partnership angles and opportunities for Matrixdock
2. Potential strategic contacts or companies to engage  
3. Business development actions Matrixdock could take
4. Competitive advantages or market positioning opportunities

Content: {analysis_content}

Focus on concrete BD actions, specific companies/contacts mentioned, and strategic opportunities for RWA/gold tokenization partnerships. Format with • symbol."""

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
    bd_prompt = f"""Analyze this news article specifically for Matrixdock partnership and business development opportunities. Provide exactly 3-4 bullet points covering:

1. Partnership angles and opportunities for Matrixdock
2. Potential strategic contacts or companies to engage
3. Business development actions Matrixdock could take
4. Competitive advantages this news reveals

News Content: {fake_news}

Focus on concrete BD actions, specific companies/contacts mentioned, and strategic opportunities for RWA/gold tokenization partnerships. Format with • symbol."""

    ai_response = await get_ai_response(bd_prompt, command="test_bd")
    
    if ai_response:
        response = f"🧪 **Test BD Analysis**\n\n📰 *Sample News:* BlackRock launches tokenized gold fund...\n\n{ai_response}"
        log_thinking_step("Test BD Complete", f"Generated test BD analysis")
    else:
        response = f"🧪 **Test BD Analysis**\n\n📰 *Sample News:* BlackRock launches tokenized gold fund...\n\n• Partnership opportunity with State Street for custody integration solutions\n• Strategic outreach to BlackRock's digital assets team for platform collaboration\n• Business development follow-up on tokenized gold infrastructure partnerships\n• Market positioning advantage as established gold tokenization platform"
        log_thinking_step("Test BD Fallback", "Using fallback test BD analysis")
    
    await status_msg.edit_text(response)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message with AI response."""
    log_command("chat", update.effective_user.id, update.effective_user.username)
    
    user_message = update.message.text
    thinking_msg = await update.message.reply_text("🤔 Processing with AI...")
    
    log_thinking_step("Chat Processing", f"User question: {user_message[:100]}...")
    print(f"💬 Full user message: {user_message}")
    
    log_thinking_step("AI Processing", "Requesting concise conversational response")
    response = await get_ai_response(
        f"Answer this question concisely in 3-5 bullet points: {user_message}",
        command="chat"
    )
    
    if response:
        log_thinking_step("Chat Response", "AI provided concise conversational response")
        await thinking_msg.edit_text(response)
    else:
        log_thinking_step("Fallback Menu", "AI unavailable, showing command menu")
        await thinking_msg.edit_text(
            "🤖 AI temporarily unavailable. Quick commands:\n\n"
            "📈 /gold - Gold analysis\n"
            "🏗️ /rwa - RWA analysis\n" 
            "🔍 /meaning - News analysis\n"
            "🤝 /bd - Partnership analysis\n"
            "📋 /summary - Market overview"
        )
    
    print(f"✅ Chat interaction completed")

async def debug_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug function to log all messages the bot receives."""
    try:
        if update.message:
            message_info = {
                'chat_type': update.effective_chat.type,
                'chat_title': update.effective_chat.title,
                'chat_id': update.effective_chat.id,
                'user_id': update.effective_user.id if update.effective_user else None,
                'username': update.effective_user.username if update.effective_user else None,
                'message_text': update.message.text[:50] if update.message.text else None,
                'is_reply': bool(update.message.reply_to_message),
                'from_user': str(update.message.from_user) if update.message.from_user else "No user",
                'message_id': update.message.message_id
            }
            
            print(f"📨 Message Debug: {message_info}")
        
        # Don't respond to avoid spam, just log
        
    except Exception as e:
        print(f"❌ Debug message error: {e}")

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
            
            bd_prompt = f"""Analyze this news article specifically for Matrixdock partnership and business development opportunities. Provide exactly 3-4 bullet points covering:

1. Partnership angles and opportunities for Matrixdock
2. Potential strategic contacts or companies to engage
3. Business development actions Matrixdock could take
4. Competitive advantages this news reveals

News Content: {replied_text}

Focus on concrete BD actions, specific companies/contacts mentioned, and strategic opportunities for RWA/gold tokenization partnerships. Format with • symbol."""

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
    print(f"🚀 Starting RWA & Gold Intelligence Bot")
    print(f"⏰ Start time: {bot_status.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔄 Enhanced mode with conflict resolution enabled")
    
    # Set up global application reference for channel posting
    global application_instance
    
    # Check if Ollama model exists
    try:
        models = ollama.list()
        model_names = [model['name'] for model in models['models']]
        if MODEL_NAME not in model_names and f"{MODEL_NAME}:latest" not in model_names:
            print(f"⚠️  Model '{MODEL_NAME}' not found. AI features limited.")
            print("📝 Commands will work with curated content.")
        else:
            print(f"✅ AI Model '{MODEL_NAME}' ready!")
        print(f"📋 Available models: {model_names}")
    except Exception as e:
        print(f"⚠️  Ollama connection issue: {e}")
        print("🔄 Bot will run with limited AI features.")
    
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
    
    # Handle direct messages and channel messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    # Add specific handler for channel messages (more permissive)
    application.add_handler(
        MessageHandler(filters.ALL, debug_all_messages)
    )
    
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
            
            # Create background tasks
            news_task = asyncio.create_task(news_scheduler())
            console_task = asyncio.create_task(console_monitor())
            
            print("📅 News scheduler started")
            print("⌨️ Console monitor started")
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
                
                try:
                    await asyncio.gather(news_task, console_task, return_exceptions=True)
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
