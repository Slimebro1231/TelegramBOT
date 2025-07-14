"""
News Scraper Module for Telegram Bot
====================================

Fetches real-time news from multiple sources, filters for relevance,
and provides article content for AI processing with duplicate prevention.

Sources:
- CoinDesk RSS (crypto/blockchain news)
- Reuters Business RSS (traditional finance)
- CoinTelegraph RSS (crypto news)
- Yahoo Finance RSS (markets/gold)
- Decrypt (crypto news)
- The Block (crypto/blockchain)
- Benzinga (financial news)
- MarketWatch (market news)
- CryptoSlate (crypto news)
- Bloomberg Crypto (premium financial news)
- Fintech News (fintech developments)
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional, Set
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import hashlib

# RSS Feed URLs - Expanded sources
RSS_FEEDS = {
    "coindesk": "https://feeds.coindesk.com/coindesk",
    "cointelegraph": "https://cointelegraph.com/rss",
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "yahoo_finance": "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "decrypt": "https://decrypt.co/feed",
    "theblock": "https://www.theblock.co/rss.xml",
    "benzinga": "https://www.benzinga.com/feed",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/",
    "cryptoslate": "https://cryptoslate.com/feed/",
    "fintech_news": "https://www.fintechnews.org/feed/",
    "coinjournal": "https://coinjournal.net/feed/",
    "investing_crypto": "https://www.investing.com/rss/news_285.rss",
    "crypto_news": "https://cryptonews.com/news/feed/",
    "ambcrypto": "https://ambcrypto.com/feed/"
}

# Keywords for relevance filtering - Enhanced
RELEVANCE_KEYWORDS = {
    "rwa": [
        "real world asset", "rwa", "tokenization", "tokenized", "asset backed",
        "real estate token", "commodity token", "security token", "sto",
        "asset digitization", "blockchain asset", "defi asset", "traditional asset",
        "asset tokenization", "digital asset", "token asset", "backed token",
        "physical asset", "tangible asset", "tokenize", "fractionalized"
    ],
    "gold": [
        "gold", "precious metal", "bullion", "gold price", "gold market",
        "gold etf", "gold mining", "gold reserve", "central bank gold",
        "gold futures", "spot gold", "gold backed", "gold standard",
        "gold coin", "gold bar", "gold investment", "gold rally",
        "gold demand", "gold supply", "xau", "troy ounce"
    ],
    "partnerships": [
        "partnership", "collaboration", "integration", "announces", "teams up",
        "joint venture", "strategic alliance", "cooperation", "agreement",
        "deal", "merger", "acquisition", "investment", "launches with",
        "partners with", "alliance", "working together", "strategic partnership",
        "business partnership", "technology partnership"
    ],
    "institutional": [
        "institutional", "bank", "financial institution", "corporate",
        "enterprise", "blackrock", "fidelity", "jpmorgan", "goldman sachs",
        "morgan stanley", "wells fargo", "visa", "mastercard", "paypal",
        "deutsche bank", "ubs", "credit suisse", "hsbc", "citigroup",
        "institutional adoption", "institutional investor", "wall street"
    ],
    "defi": [
        "defi", "decentralized finance", "yield farming", "liquidity pool",
        "dex", "decentralized exchange", "lending protocol", "borrowing",
        "staking", "governance token", "dao", "smart contract",
        "automated market maker", "amm", "tvl", "total value locked"
    ],
    "regulation": [
        "regulation", "regulatory", "sec", "cftc", "compliance", "license",
        "approval", "framework", "guidance", "law", "legal", "policy",
        "government", "federal", "state", "international", "global regulation"
    ]
}

# Duplicate tracking file
TRACKING_FILE = "news_tracker.json"

class NewsTracker:
    """Handles duplicate detection and article tracking with rich metadata."""
    
    def __init__(self, tracking_file: str = TRACKING_FILE):
        self.tracking_file = tracking_file
        self.posted_articles: Dict[str, Dict] = {}  # Changed from Set to Dict for metadata
        self.load_tracking_data()
    
    def load_tracking_data(self):
        """Load previously posted articles from file."""
        try:
            if os.path.exists(self.tracking_file):
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                    
                    # Handle both old format (list) and new format (dict)
                    posted_data = data.get('posted_articles', [])
                    if isinstance(posted_data, list):
                        # Convert old format to new format
                        self.posted_articles = {}
                        for article_hash in posted_data:
                            self.posted_articles[article_hash] = {
                                'title': 'Legacy Article',
                                'source': 'unknown',
                                'posted_at': datetime.now().isoformat(),
                                'published_at': None
                            }
                        print(f"📝 Converted {len(posted_data)} legacy entries to new format")
                    else:
                        self.posted_articles = posted_data
                    
                # Clean old entries (older than 7 days)
                self.cleanup_old_entries()
                print(f"📝 Loaded {len(self.posted_articles)} tracked articles")
            else:
                print("📝 No tracking file found, starting fresh")
                self.posted_articles = {}
        except Exception as e:
            print(f"⚠️ Error loading tracking data: {e}")
            self.posted_articles = {}
    
    def save_tracking_data(self):
        """Save tracking data to file with rich metadata."""
        try:
            data = {
                'posted_articles': self.posted_articles,
                'last_updated': datetime.now().isoformat(),
                'total_tracked': len(self.posted_articles)
            }
            with open(self.tracking_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving tracking data: {e}")
    
    def cleanup_old_entries(self):
        """Remove entries older than 7 days to prevent file from growing too large."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=7)
        
        # Remove entries older than 7 days
        old_entries = []
        for article_hash, metadata in self.posted_articles.items():
            try:
                posted_at = datetime.fromisoformat(metadata['posted_at'])
                if posted_at < cutoff_time:
                    old_entries.append(article_hash)
            except (KeyError, ValueError):
                # If we can't parse the date, keep it but mark for cleanup
                if len(self.posted_articles) > 1000:
                    old_entries.append(article_hash)
        
        # Remove old entries
        for article_hash in old_entries:
            del self.posted_articles[article_hash]
        
        if old_entries:
            print(f"🧹 Cleaned {len(old_entries)} old entries, keeping {len(self.posted_articles)} recent articles")
    
    def get_article_hash(self, article) -> str:
        """Generate a unique hash for an article based on title and URL."""
        # Use title and URL to create a unique identifier
        content = f"{article.title}|{article.url}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def is_duplicate(self, article) -> bool:
        """Check if article has already been posted."""
        article_hash = self.get_article_hash(article)
        return article_hash in self.posted_articles
    
    def mark_as_posted(self, article):
        """Mark an article as posted with full metadata."""
        article_hash = self.get_article_hash(article)
        
        # Store rich metadata
        self.posted_articles[article_hash] = {
            'title': article.title,
            'source': article.source,
            'posted_at': datetime.now().isoformat(),
            'published_at': article.published.isoformat() if article.published else None,
            'url': article.url,
            'category': getattr(article, 'category', 'unknown')
        }
        
        self.save_tracking_data()
        print(f"✅ Marked article as posted: {article.title[:50]}...")
    
    def get_recent_articles(self, limit: int = 10) -> List[Dict]:
        """Get recently posted articles with metadata."""
        articles = []
        for article_hash, metadata in self.posted_articles.items():
            articles.append({
                'hash': article_hash,
                **metadata
            })
        
        # Sort by posted_at timestamp, most recent first
        articles.sort(key=lambda x: x.get('posted_at', ''), reverse=True)
        return articles[:limit]

class NewsArticle:
    """Represents a news article with metadata."""
    
    def __init__(self, title: str, url: str, source: str, published: datetime, 
                 summary: str = "", content: str = "", category: str = ""):
        self.title = title
        self.url = url
        self.source = source
        self.published = published
        self.summary = summary
        self.content = content
        self.category = category
        self.relevance_score = 0.0

class NewsScraper:
    """Handles fetching and processing news from multiple sources."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.last_fetch = {}
        self.cache = {}
        self.tracker = NewsTracker()
        
    def fetch_rss_feed(self, feed_name: str, url: str) -> List[Dict]:
        """Fetch and parse RSS feed."""
        try:
            print(f"📡 Fetching {feed_name} RSS feed...")
            
            # Add timeout and error handling
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                print(f"⚠️ No entries found in {feed_name} feed")
                return []
            
            articles = []
            for entry in feed.entries[:15]:  # Increased to 15 most recent
                try:
                    # Parse published date
                    published = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        published = datetime(*entry.updated_parsed[:6])
                    
                    # Skip articles older than 48 hours (increased from 24)
                    if published < datetime.now() - timedelta(hours=48):
                        continue
                    
                    article = {
                        'title': entry.title if hasattr(entry, 'title') else 'No Title',
                        'url': entry.link if hasattr(entry, 'link') else '',
                        'summary': entry.summary if hasattr(entry, 'summary') else '',
                        'published': published,
                        'source': feed_name
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    print(f"⚠️ Error parsing entry from {feed_name}: {e}")
                    continue
            
            print(f"✅ Fetched {len(articles)} articles from {feed_name}")
            return articles
            
        except Exception as e:
            print(f"❌ Error fetching {feed_name} RSS: {e}")
            return []
    
    def calculate_relevance_score(self, article: Dict) -> float:
        """Calculate relevance score based on keywords."""
        text = f"{article['title']} {article['summary']}".lower()
        
        # Filter out price prediction articles
        price_prediction_keywords = [
            'price prediction', 'price forecast', 'price target',
            'price analysis', 'technical analysis', 'price outlook',
            'will reach', 'could hit', 'price could', 'price may',
            'price estimate', 'price projection', 'price expectations',
            'bullish target', 'bearish target', 'resistance level',
            'support level', 'fibonacci', 'moving average', 'rsi',
            'chart analysis', 'trading signals', 'buy signal', 'sell signal'
        ]
        
        # Check if article is a price prediction article
        for keyword in price_prediction_keywords:
            if keyword in text:
                return 0.0  # Zero score for price prediction articles
        
        total_score = 0.0
        category_matches = {}
        
        for category, keywords in RELEVANCE_KEYWORDS.items():
            category_score = 0.0
            matches = 0
            
            for keyword in keywords:
                if keyword.lower() in text:
                    # Weight based on keyword importance and position
                    weight = 3.0 if keyword.lower() in article['title'].lower() else 1.0
                    category_score += weight
                    matches += 1
            
            if matches > 0:
                category_matches[category] = category_score
                total_score += category_score
        
        # Bonus for multiple category matches
        if len(category_matches) > 1:
            total_score *= 1.5
        
        # Determine primary category
        if category_matches:
            primary_category = max(category_matches.keys(), key=lambda k: category_matches[k])
            article['category'] = primary_category
        
        return min(total_score, 15.0)  # Increased cap to 15.0
    
    def extract_article_content(self, url: str) -> str:
        """Extract article content from URL."""
        try:
            print(f"📄 Extracting content from: {url[:50]}...")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
                element.decompose()
            
            # Try different content selectors based on common patterns
            content_selectors = [
                'article',
                '.article-content',
                '.post-content',
                '.entry-content',
                '.content',
                'main',
                '.story-body',
                '.article-body',
                '.post-body',
                '.news-content'
            ]
            
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    # Get text from paragraphs within the content area
                    paragraphs = elements[0].find_all('p')
                    if paragraphs:
                        content = ' '.join([p.get_text().strip() for p in paragraphs[:7]])  # Increased to 7 paragraphs
                        break
            
            # Fallback: get all paragraphs
            if not content:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text().strip() for p in paragraphs[:5]])
            
            # Clean up content
            content = re.sub(r'\s+', ' ', content).strip()
            
            # Limit content length
            if len(content) > 2000:  # Increased limit
                content = content[:2000] + "..."
            
            print(f"✅ Extracted {len(content)} characters of content")
            return content
            
        except Exception as e:
            print(f"⚠️ Error extracting content from {url}: {e}")
            return ""
    
    async def fetch_all_feeds(self) -> List[NewsArticle]:
        """Fetch articles from all RSS feeds concurrently."""
        print("🔄 Starting news fetch from all sources...")
        
        all_articles = []
        
        # Use ThreadPoolExecutor for concurrent RSS fetching
        with ThreadPoolExecutor(max_workers=8) as executor:  # Increased workers
            loop = asyncio.get_event_loop()
            
            # Create tasks for all feeds
            tasks = []
            for feed_name, url in RSS_FEEDS.items():
                task = loop.run_in_executor(executor, self.fetch_rss_feed, feed_name, url)
                tasks.append(task)
            
            # Wait for all feeds to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                feed_name = list(RSS_FEEDS.keys())[i]
                
                if isinstance(result, Exception):
                    print(f"❌ Error fetching {feed_name}: {result}")
                    continue
                
                if not result:
                    continue
                
                # Process articles from this feed
                for article_data in result:
                    relevance_score = self.calculate_relevance_score(article_data)
                    
                    # Lower threshold to get more articles
                    if relevance_score >= 1.5:
                        article = NewsArticle(
                            title=article_data['title'],
                            url=article_data['url'],
                            source=article_data['source'],
                            published=article_data['published'],
                            summary=article_data['summary'],
                            category=article_data.get('category', 'general')
                        )
                        article.relevance_score = relevance_score
                        
                        # Check for duplicates
                        if not self.tracker.is_duplicate(article):
                            all_articles.append(article)
                        else:
                            print(f"🔄 Skipping duplicate: {article.title[:50]}...")
        
        # Sort by relevance score and recency
        all_articles.sort(key=lambda x: (x.relevance_score, x.published), reverse=True)
        
        print(f"🎯 Found {len(all_articles)} unique relevant articles")
        return all_articles[:30]  # Return top 30 most relevant
    
    async def get_article_with_content(self, article: NewsArticle) -> NewsArticle:
        """Fetch full content for an article."""
        if not article.content and article.url:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                article.content = await loop.run_in_executor(
                    executor, self.extract_article_content, article.url
                )
        return article

# Global scraper instance
scraper = NewsScraper()

async def get_latest_relevant_news(limit: int = 5) -> List[NewsArticle]:
    """Get the latest relevant news articles."""
    try:
        articles = await scraper.fetch_all_feeds()
        
        # Get full content for top articles
        top_articles = articles[:limit]
        
        # Fetch content for articles concurrently
        tasks = [scraper.get_article_with_content(article) for article in top_articles]
        articles_with_content = await asyncio.gather(*tasks)
        
        return articles_with_content
        
    except Exception as e:
        print(f"❌ Error in get_latest_relevant_news: {e}")
        return []

async def get_single_relevant_article() -> Optional[NewsArticle]:
    """Get a single relevant article for channel posting."""
    articles = await get_latest_relevant_news(limit=5)  # Get top 5 candidates
    
    # Return the first non-duplicate article
    for article in articles:
        if not scraper.tracker.is_duplicate(article):
            # Mark as posted and return
            scraper.tracker.mark_as_posted(article)
            return article
    
    # If all are duplicates, return None
    print("⚠️ All articles are duplicates, no new content available")
    return None

def format_article_for_ai(article: NewsArticle) -> str:
    """Format article for AI processing."""
    content_preview = article.content[:800] + "..." if len(article.content) > 800 else article.content
    
    return f"""
Title: {article.title}
Source: {article.source}
Category: {article.category}
URL: {article.url}
Published: {article.published.strftime('%Y-%m-%d %H:%M')}
Relevance Score: {article.relevance_score:.1f}

Summary: {article.summary}

Content Preview: {content_preview}
"""

def get_tracker_stats() -> Dict:
    """Get enhanced statistics about tracked articles."""
    recent_articles = scraper.tracker.get_recent_articles(5)
    
    # Count articles by source
    source_counts = {}
    category_counts = {}
    
    for article_hash, metadata in scraper.tracker.posted_articles.items():
        source = metadata.get('source', 'unknown')
        category = metadata.get('category', 'unknown')
        
        source_counts[source] = source_counts.get(source, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
    
    return {
        'total_tracked': len(scraper.tracker.posted_articles),
        'tracking_file': scraper.tracker.tracking_file,
        'recent_articles': recent_articles,
        'sources': source_counts,
        'categories': category_counts,
        'last_updated': datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Test the scraper
    async def test_scraper():
        print("🧪 Testing enhanced news scraper...")
        articles = await get_latest_relevant_news(limit=5)
        
        print(f"\n📊 Tracker Stats: {get_tracker_stats()}")
        
        for i, article in enumerate(articles, 1):
            print(f"\n📰 Article {i}:")
            print(f"Title: {article.title}")
            print(f"Source: {article.source}")
            print(f"Category: {article.category}")
            print(f"Relevance: {article.relevance_score:.1f}")
            print(f"URL: {article.url}")
            print(f"Content length: {len(article.content)} chars")
            print(f"Duplicate: {scraper.tracker.is_duplicate(article)}")
            print("-" * 50)
    
    asyncio.run(test_scraper()) 