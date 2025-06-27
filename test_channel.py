#!/usr/bin/env python3
"""
Simple Channel Test Script
=========================
Tests if the bot can post to the Telegram channel without conflicts.
"""

import os
import asyncio
import random
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@Matrixdock_News"

# Test news items
TEST_NEWS = [
    "🏆 Gold hits $2,150/oz as central banks increase purchases by 15% this quarter",
    "📈 BlackRock Files for $2.5B Tokenized Treasury Fund with SEC", 
    "🤝 JPMorgan partners with blockchain platform for $500M RWA initiative"
]

async def test_channel_access():
    """Test if bot can access and post to the channel."""
    print(f"🔍 Testing channel access to {CHANNEL_ID}")
    print(f"🤖 Using bot token: {TOKEN[:10]}...")
    
    try:
        bot = Bot(token=TOKEN)
        await bot.initialize()  # Initialize the bot properly
        
        # Test 1: Get channel info
        print("\n📊 Test 1: Getting channel information...")
        chat = await bot.get_chat(CHANNEL_ID)
        print(f"✅ Channel found: {chat.title}")
        print(f"📋 Channel ID: {chat.id}")
        print(f"🔧 Channel type: {chat.type}")
        
        # Test 2: Check bot permissions
        print("\n🔐 Test 2: Checking bot permissions...")
        bot_member = await bot.get_chat_member(CHANNEL_ID, bot.id)
        print(f"🤖 Bot status in channel: {bot_member.status}")
        
        can_post = bot_member.status in ['administrator', 'creator']
        can_delete = can_post and getattr(bot_member, 'can_delete_messages', False)
        
        print(f"📤 Can post messages: {can_post}")
        print(f"🗑️ Can delete messages: {can_delete}")
        
        if not can_post:
            print("❌ Bot cannot post to channel - needs admin permissions")
            return False
        
        # Test 3: Post a test message
        print("\n📝 Test 3: Posting test message...")
        test_message = f"🔄 Channel test - {datetime.now().strftime('%H:%M:%S')}"
        
        message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=test_message
        )
        print(f"✅ Test message posted successfully!")
        print(f"📋 Message ID: {message.message_id}")
        
        # Test 4: Delete the test message if possible
        if can_delete:
            print("\n🗑️ Test 4: Cleaning up test message...")
            await asyncio.sleep(2)  # Wait 2 seconds
            await bot.delete_message(CHANNEL_ID, message.message_id)
            print("✅ Test message deleted successfully!")
        else:
            print("\n⚠️ Test 4: Cannot delete messages - leaving test message")
        
        # Test 5: Post actual news
        print("\n📰 Test 5: Posting sample news...")
        news_headline = random.choice(TEST_NEWS)
        news_message = f"""{news_headline}

• Market impact analysis shows institutional adoption accelerating
• Regulatory clarity continues to improve investor confidence  
• Technology infrastructure enables larger transaction volumes

Source (https://example.com/news)"""
        
        news_post = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=news_message,
            disable_web_page_preview=True
        )
        print(f"✅ News posted successfully!")
        print(f"📋 News message ID: {news_post.message_id}")
        
        print(f"\n🎉 All tests passed! Bot can successfully post to {CHANNEL_ID}")
        return True
        
    except Exception as e:
        print(f"\n❌ Channel test failed: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        
        if "chat not found" in str(e).lower():
            print("💡 Possible issues:")
            print("   - Channel name is incorrect")
            print("   - Channel doesn't exist")
            print("   - Bot is not added to the channel")
        elif "forbidden" in str(e).lower():
            print("💡 Possible issues:")
            print("   - Bot is not admin in the channel")
            print("   - Bot lacks posting permissions")
            print("   - Channel is private and bot lacks access")
        
        return False
    finally:
        # Clean up bot connection
        try:
            await bot.shutdown()
        except:
            pass

if __name__ == "__main__":
    print("🚀 Starting Telegram Channel Test")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        exit(1)
    
    try:
        result = asyncio.run(test_channel_access())
        if result:
            print("\n🎯 Channel is ready for bot posting!")
        else:
            print("\n⚠️ Channel needs configuration before bot can post")
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}") 