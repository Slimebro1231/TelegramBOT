"""
Nuclear Conflict Resolution System
==================================

Handles persistent Telegram API conflicts and bot startup issues.
This module can be easily disabled once the system becomes more stable.

Functions:
- nuclear_conflict_resolution(): Main cleanup function
- clear_telegram_webhooks(): Webhook clearing utilities
- kill_competing_processes(): Process cleanup
"""

import requests
import time
import subprocess
import asyncio
import os

def kill_competing_processes():
    """Kill competing python/bot processes, but NOT the current process."""
    print("🧹 Killing competing processes...")
    
    try:
        current_pid = os.getpid()
        parent_pid = os.getppid()
        print(f"🔒 Protecting current process PID: {current_pid}")
        print(f"🔒 Protecting parent process PID: {parent_pid}")
        
        # Get more specific process list - only exact matches
        result = subprocess.run(["pgrep", "-f", "python.*bot\\.py"], capture_output=True, text=True)
        if result.stdout:
            pids = result.stdout.strip().split('\n')
            print(f"🔍 Found {len(pids)} potential bot processes: {pids}")
            
            for pid in pids:
                if pid and pid.strip():
                    pid = pid.strip()
                    # Skip if it's the current process or parent process
                    if pid in [str(current_pid), str(parent_pid)]:
                        print(f"🔒 Skipping protected process PID: {pid}")
                        continue
                    
                    # Double-check the process before killing
                    try:
                        # Get process details to verify it's actually a competing bot
                        check_result = subprocess.run(
                            ["ps", "-p", pid, "-o", "cmd="], 
                            capture_output=True, text=True
                        )
                        if check_result.returncode == 0:
                            cmd_line = check_result.stdout.strip()
                            print(f"🔍 Process {pid} command: {cmd_line}")
                            
                            # Only kill if it's actually a bot.py process and not our current process
                            if "bot.py" in cmd_line and pid not in [str(current_pid), str(parent_pid)]:
                                subprocess.run(["kill", "-TERM", pid], capture_output=True)  # Use TERM instead of -9
                                print(f"✅ Terminated competing process PID: {pid}")
                                time.sleep(2)  # Give it time to shutdown gracefully
                                
                                # Check if it's still running, then use KILL
                                check_again = subprocess.run(["ps", "-p", pid], capture_output=True)
                                if check_again.returncode == 0:
                                    subprocess.run(["kill", "-9", pid], capture_output=True)
                                    print(f"🔪 Force killed stubborn process PID: {pid}")
                            else:
                                print(f"🔒 Skipping non-bot process PID: {pid}")
                        else:
                            print(f"⚠️ Process {pid} no longer exists")
                    except Exception as e:
                        print(f"⚠️ Failed to check/kill PID {pid}: {e}")
        else:
            print("✅ No competing bot processes found")
        
        print("✅ Process cleanup complete (protected current process)")
        time.sleep(3)
    except Exception as e:
        print(f"⚠️ Process killing failed: {e}")

def clear_telegram_webhooks(token: str):
    """Clear Telegram webhooks using multiple methods."""
    print("🧹 Clearing Telegram webhooks...")
    
    # Multiple webhook clearing methods
    webhook_methods = [
        f"https://api.telegram.org/bot{token}/deleteWebhook",
        f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true",
        f"https://api.telegram.org/bot{token}/setWebhook?url=",
        f"https://api.telegram.org/bot{token}/setWebhook?url=&drop_pending_updates=true"
    ]
    
    for method_num, webhook_url in enumerate(webhook_methods):
        for attempt in range(3):
            try:
                response = requests.post(webhook_url, timeout=20)
                print(f"✅ Webhook method {method_num + 1} attempt {attempt + 1} completed")
                time.sleep(2)
                break
                
            except Exception as e:
                print(f"⚠️ Webhook method {method_num + 1} attempt {attempt + 1} failed: {e}")
                time.sleep(3)

def clear_pending_updates(token: str):
    """Aggressively clear pending updates with multiple strategies."""
    print("🧹 Clearing pending updates...")
    
    for round_num in range(5):
        try:
            # Strategy 1: Clear with very high offset
            updates_url = f"https://api.telegram.org/bot{token}/getUpdates?offset=999999999&limit=100&timeout=1"
            response = requests.get(updates_url, timeout=20)
            
            # Strategy 2: Get all updates and confirm with offset
            if response.status_code == 200:
                data = response.json()
                if data.get('result'):
                    last_update_id = data['result'][-1]['update_id'] + 1
                    confirm_url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id}&timeout=1"
                    requests.get(confirm_url, timeout=20)
            
            # Strategy 3: Force clear with negative offset  
            force_url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-1&limit=1&timeout=1"
            requests.get(force_url, timeout=20)
                    
            print(f"✅ Updates cleared (round {round_num + 1})")
            
        except Exception as e:
            print(f"⚠️ Clear updates round {round_num + 1} failed: {e}")
        
        time.sleep(3)

def nuclear_conflict_resolution(token: str):
    """
    Nuclear-level multi-step conflict resolution for persistent issues.
    
    Args:
        token (str): Telegram bot token for API calls
    """
    print("🔧 Nuclear conflict resolution starting...")
    
    # Step 1: Kill ALL competing processes
    kill_competing_processes()
    
    # Step 2: Clear webhooks with multiple methods
    clear_telegram_webhooks(token)
    
    # Step 3: Aggressive pending update clearing
    clear_pending_updates(token)
    
    # Step 4: Extended stabilization phases
    print("⏳ Phase 1 stabilization (10 seconds)...")
    time.sleep(10)
    
    # Final webhook clear
    try:
        requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true", timeout=20)
        print("🧹 Final webhook clear")
    except Exception as e:
        print(f"⚠️ Final webhook clear failed: {e}")
    
    print("⏳ Phase 2 stabilization (20 seconds)...")
    time.sleep(20)
    
    print("✅ Nuclear conflict resolution complete")

async def ultra_robust_polling_start(application, token: str, max_retries: int = 10):
    """
    Start polling with ultra-robust conflict resolution and retries.
    
    Args:
        application: Telegram Application instance
        token: Bot token for conflict resolution
        max_retries: Maximum retry attempts
    """
    from telegram.error import Conflict
    
    base_retry_delay = 20
    
    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting polling (attempt {attempt + 1}/{max_retries})...")
            
            # Try to start polling with maximum robustness
            # This should block and keep polling active like the regular start_polling
            await application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=None,
                timeout=30,
                poll_interval=2.0
            )
            print("✅ Polling started successfully")
            # Don't return here - let the polling continue running
            break
            
        except Conflict as e:
            print(f"⚠️ Conflict detected (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = base_retry_delay * (2 ** attempt) + (attempt * 5)
                print(f"⏳ Extended wait {delay} seconds before retry...")
                await asyncio.sleep(delay)
                
                # Nuclear cleanup between retries
                print("🔧 Performing nuclear inter-retry cleanup...")
                try:
                    # Kill competing processes
                    kill_competing_processes()
                    await asyncio.sleep(5)
                    
                    # Clear webhooks and updates
                    clear_telegram_webhooks(token)
                    clear_pending_updates(token)
                    
                    print("🧹 Nuclear inter-retry cleanup complete")
                    
                except Exception as cleanup_error:
                    print(f"⚠️ Cleanup error: {cleanup_error}")
            else:
                print(f"❌ Max retries ({max_retries}) exceeded")
                print("💡 Suggestion: Check if another bot instance is running elsewhere")
                raise
                
        except Exception as e:
            print(f"❌ Unexpected polling error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(10)
            else:
                raise
    
    # If we get here, polling should be running successfully
    # The function should not return until polling stops
    return True

# Configuration options
ENABLE_NUCLEAR_RESOLUTION = True  # Set to False to disable when system is stable
ENABLE_ULTRA_ROBUST_POLLING = False  # Set to False for simple polling

def should_use_conflict_resolution():
    """Check if conflict resolution should be used."""
    return ENABLE_NUCLEAR_RESOLUTION

def should_use_ultra_robust_polling():
    """Check if ultra-robust polling should be used."""
    return ENABLE_ULTRA_ROBUST_POLLING 