#!/usr/bin/env python3
"""
VM Bot Monitor - Local monitoring tool for remote Telegram bot
Shows status, logs, and history of the bot running on Bitdeer VM
"""

import subprocess
import sys
import os
import json
import tempfile
import threading
import queue
import select
import time
from datetime import datetime

# VM Configuration
VM_IP = "157.10.162.223"
VM_USER = "ubuntu"
SSH_KEY = "TelegramBot-Key.pem"
BOT_DIR = "~/TelegramBOT"

class VMMonitor:
    def __init__(self):
        self.ssh_base = f"ssh -i {SSH_KEY} {VM_USER}@{VM_IP}"
        
    def run_ssh_command(self, command, timeout=30):
        """Run SSH command on VM and return output"""
        try:
            full_command = f"{self.ssh_base} '{command}'"
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1
        except Exception as e:
            return "", f"SSH Error: {str(e)}", -1
    
    def check_vm_connectivity(self):
        """Test if VM is reachable"""
        print("🔍 Checking VM connectivity...")
        stdout, stderr, code = self.run_ssh_command("echo 'VM Connected'", timeout=10)
        if code == 0:
            print("✅ VM is reachable")
            return True
        else:
            print(f"❌ VM connection failed: {stderr}")
            return False
    
    def get_bot_status(self):
        """Get current bot service status"""
        print("\n📊 BOT STATUS")
        print("=" * 40)
        
        # Service status
        stdout, stderr, code = self.run_ssh_command("systemctl is-active telegram-bot.service")
        status = stdout.strip() if code == 0 else "inactive"
        
        # Service details
        stdout2, _, _ = self.run_ssh_command("systemctl status telegram-bot.service --no-pager -l")
        
        print(f"Service Status: {'🟢 ACTIVE' if status == 'active' else '🔴 INACTIVE'}")
        print(f"Last Check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if stdout2:
            lines = stdout2.split('\n')
            for line in lines[:10]:  # Show first 10 lines
                if any(keyword in line.lower() for keyword in ['active', 'loaded', 'main pid', 'memory', 'cpu']):
                    print(f"  {line.strip()}")
    
    def get_recent_logs(self, lines=50):
        """Get recent bot logs"""
        print(f"\n📋 RECENT LOGS (Last {lines} lines)")
        print("=" * 40)
        
        command = f"journalctl -u telegram-bot.service -n {lines} --no-pager"
        stdout, stderr, code = self.run_ssh_command(command)
        
        if code == 0 and stdout:
            for line in stdout.split('\n')[-lines:]:
                if line.strip():
                    print(line)
        else:
            print(f"❌ Could not fetch logs: {stderr}")
    
    def get_bot_stats(self):
        """Get bot performance statistics"""
        print("\n💹 BOT STATISTICS")
        print("=" * 40)
        
        # Uptime
        stdout, _, _ = self.run_ssh_command("systemctl show telegram-bot.service --property=ActiveEnterTimestamp")
        if stdout:
            print(f"  {stdout.strip()}")
        
        # Resource usage
        stdout, _, _ = self.run_ssh_command("systemctl show telegram-bot.service --property=MemoryCurrent,CPUUsageNSec")
        if stdout:
            for line in stdout.split('\n'):
                if line.strip():
                    print(f"  {line.strip()}")
        
        # Process info
        stdout, _, _ = self.run_ssh_command("ps aux | grep -E 'python.*bot.py' | grep -v grep")
        if stdout:
            print(f"\n🔄 Active Process:")
            print(f"  {stdout.strip()}")
    
    def tail_logs(self):
        """Show live log tail (blocking)"""
        print("\n📺 LIVE LOGS (Press Ctrl+C to stop)")
        print("=" * 40)
        
        try:
            command = f"{self.ssh_base} 'journalctl -u telegram-bot.service -f'"
            subprocess.run(command, shell=True)
        except KeyboardInterrupt:
            print("\n✅ Log monitoring stopped")
    
    def control_bot(self, action):
        """Control bot service (start/stop/restart)"""
        print(f"\n🎮 {action.upper()} BOT")
        print("=" * 40)
        
        if action not in ['start', 'stop', 'restart']:
            print("❌ Invalid action. Use: start, stop, restart")
            return
        
        command = f"sudo systemctl {action} telegram-bot.service"
        stdout, stderr, code = self.run_ssh_command(command)
        
        if code == 0:
            print(f"✅ Bot {action} command executed successfully")
            time.sleep(2)  # Wait for service to change state
            self.get_bot_status()
        else:
            print(f"❌ Failed to {action} bot: {stderr}")
    
    def virtual_terminal(self):
        """Virtual terminal mode - live logs + bot interaction"""
        print("\n🖥️ VIRTUAL TERMINAL MODE")
        print("=" * 60)
        print("📺 Live logs will appear below")
        print("⌨️ Type commands in format: CMD> your_command")
        print("🔄 Available commands: next, verify, status, restart, stop")
        print("❌ Type 'exit' to leave virtual terminal")
        print("💡 Bot continues running when you disconnect")
        print("=" * 60)
        
        # Queue for commands
        command_queue = queue.Queue()
        stop_threads = threading.Event()
        
        def log_streamer():
            """Stream logs in real-time"""
            try:
                import subprocess
                import fcntl
                import os
                
                # Start journalctl follow process
                cmd = f"{self.ssh_base} 'journalctl -u telegram-bot.service -f --no-pager'"
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Make stdout non-blocking
                fd = proc.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
                while not stop_threads.is_set():
                    try:
                        ready, _, _ = select.select([proc.stdout], [], [], 0.1)
                        if ready:
                            line = proc.stdout.readline()
                            if line:
                                # Clean up the log line and print it
                                clean_line = line.strip()
                                if clean_line and not clean_line.startswith('-- '):
                                    timestamp = datetime.now().strftime("%H:%M:%S")
                                    print(f"📺 [{timestamp}] {clean_line}")
                    except:
                        pass
                
                proc.terminate()
                proc.wait()
                
            except Exception as e:
                print(f"❌ Log streaming error: {e}")
        
        def command_processor():
            """Process commands sent to bot"""
            while not stop_threads.is_set():
                try:
                    if not command_queue.empty():
                        cmd = command_queue.get_nowait()
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        if cmd == "next":
                            print(f"⚡ [{timestamp}] Triggering news post...")
                            # Create signal file for bot to detect and process
                            signal_command = {
                                'command': 'post_news',
                                'timestamp': timestamp,
                                'source': 'virtual_terminal'
                            }
                            
                            # Send signal file to VM
                            try:
                                import tempfile
                                import json
                                
                                # Create local signal file
                                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                                    json.dump(signal_command, f)
                                    temp_file = f.name
                                
                                # Upload signal file to VM
                                signal_file = f"{BOT_DIR}/bot_signal.json"
                                upload_cmd = f"scp -i {SSH_KEY} {temp_file} {VM_USER}@{VM_IP}:{signal_file}"
                                result = subprocess.run(upload_cmd, shell=True, capture_output=True)
                                
                                # Clean up local file
                                os.unlink(temp_file)
                                
                                if result.returncode == 0:
                                    print(f"📤 [{timestamp}] News trigger sent to bot successfully")
                                else:
                                    print(f"❌ [{timestamp}] Failed to send news trigger: {result.stderr.decode()}")
                            except Exception as e:
                                print(f"❌ [{timestamp}] Error sending news trigger: {e}")
                            
                        elif cmd == "verify":
                            print(f"🔍 [{timestamp}] Verifying channel access...")
                            # Create verify signal file
                            signal_command = {
                                'command': 'verify_channel',
                                'timestamp': timestamp,
                                'source': 'virtual_terminal'
                            }
                            
                            try:
                                import tempfile
                                import json
                                
                                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                                    json.dump(signal_command, f)
                                    temp_file = f.name
                                
                                signal_file = f"{BOT_DIR}/bot_signal.json"
                                upload_cmd = f"scp -i {SSH_KEY} {temp_file} {VM_USER}@{VM_IP}:{signal_file}"
                                result = subprocess.run(upload_cmd, shell=True, capture_output=True)
                                
                                os.unlink(temp_file)
                                
                                if result.returncode == 0:
                                    print(f"📤 [{timestamp}] Channel verification request sent")
                                else:
                                    print(f"❌ [{timestamp}] Failed to send verification request")
                            except Exception as e:
                                print(f"❌ [{timestamp}] Error sending verification request: {e}")
                        
                        elif cmd == "status":
                            print(f"📊 [{timestamp}] Getting bot status...")
                            stdout, stderr, code = self.run_ssh_command("systemctl is-active telegram-bot.service")
                            status = stdout.strip() if code == 0 else "inactive"
                            print(f"📊 [{timestamp}] Bot status: {'🟢 ACTIVE' if status == 'active' else '🔴 INACTIVE'}")
                            
                        elif cmd == "restart":
                            print(f"🔄 [{timestamp}] Restarting bot...")
                            stdout, stderr, code = self.run_ssh_command("sudo systemctl restart telegram-bot.service")
                            if code == 0:
                                print(f"✅ [{timestamp}] Bot restarted successfully")
                            else:
                                print(f"❌ [{timestamp}] Restart failed: {stderr}")
                                
                        elif cmd == "stop":
                            print(f"🛑 [{timestamp}] Stopping bot...")
                            stdout, stderr, code = self.run_ssh_command("sudo systemctl stop telegram-bot.service")
                            if code == 0:
                                print(f"✅ [{timestamp}] Bot stopped")
                            else:
                                print(f"❌ [{timestamp}] Stop failed: {stderr}")
                        
                        command_queue.task_done()
                        
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"❌ Command processor error: {e}")
                
                time.sleep(0.1)
        
        # Start background threads
        log_thread = threading.Thread(target=log_streamer, daemon=True)
        cmd_thread = threading.Thread(target=command_processor, daemon=True)
        
        log_thread.start()
        cmd_thread.start()
        
        # Main input loop
        try:
            while True:
                try:
                    user_input = input().strip()
                    
                    if user_input.lower() == 'exit':
                        print("\n🚪 Exiting virtual terminal...")
                        print("💡 Bot continues running on VM")
                        break
                    
                    if user_input.lower().startswith('cmd>'):
                        # Extract command
                        cmd = user_input[4:].strip().lower()
                        if cmd in ['next', 'verify', 'status', 'restart', 'stop']:
                            command_queue.put(cmd)
                        else:
                            print(f"❌ Unknown command: {cmd}")
                            print("🔄 Available: next, verify, status, restart, stop")
                    
                    elif user_input.lower() in ['next', 'verify', 'status', 'restart', 'stop']:
                        # Direct command without CMD> prefix
                        command_queue.put(user_input.lower())
                    
                    elif user_input.lower() == 'help':
                        print("\n📋 VIRTUAL TERMINAL COMMANDS:")
                        print("  next      - Trigger news post")
                        print("  verify    - Check channel access")
                        print("  status    - Get bot status")
                        print("  restart   - Restart bot service")
                        print("  stop      - Stop bot service")
                        print("  help      - Show this help")
                        print("  exit      - Leave virtual terminal")
                        print("💡 Commands can be typed directly or with 'CMD>' prefix\n")
                    
                    elif user_input == '':
                        continue
                    
                    else:
                        print(f"❌ Unknown input: {user_input}")
                        print("💡 Type 'help' for available commands")
                
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n🚪 Exiting virtual terminal...")
                    break
                    
        finally:
            # Clean shutdown
            stop_threads.set()
            time.sleep(0.5)  # Let threads finish
            print("✅ Virtual terminal session ended")

    def show_help(self):
        """Show available commands"""
        print("\n🎮 VM BOT MONITOR COMMANDS")
        print("=" * 40)
        print("status     - Show current bot status")
        print("logs       - Show recent logs (default 50 lines)")
        print("logs N     - Show recent N lines of logs")
        print("live       - Show live log stream (Ctrl+C to stop)")
        print("vterminal  - Virtual terminal mode (live logs + interaction)")
        print("stats      - Show bot performance statistics")
        print("start      - Start the bot service")
        print("stop       - Stop the bot service")
        print("restart    - Restart the bot service")
        print("console    - Open remote console (interactive)")
        print("help       - Show this help")
        print("exit       - Exit monitor")

    def open_console(self):
        """Open interactive console on VM"""
        print("\n🖥️  Opening VM Console...")
        print("Type 'exit' to return to local monitor")
        print("=" * 40)
        
        try:
            command = f"{self.ssh_base} -t 'cd {BOT_DIR} && bash'"
            subprocess.run(command, shell=True)
        except KeyboardInterrupt:
            print("\n✅ Console session ended")

def main():
    if not os.path.exists(SSH_KEY):
        print(f"❌ SSH key not found: {SSH_KEY}")
        print("Make sure TelegramBot-Key.pem is in the current directory")
        sys.exit(1)
    
    monitor = VMMonitor()
    
    print("🚀 TELEGRAM BOT VM MONITOR")
    print("=" * 40)
    print(f"VM: {VM_IP}")
    print(f"User: {VM_USER}")
    print(f"Bot Directory: {BOT_DIR}")
    
    if not monitor.check_vm_connectivity():
        sys.exit(1)
    
    # If arguments provided, run command and exit
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            monitor.get_bot_status()
        elif command == "logs":
            lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            monitor.get_recent_logs(lines)
        elif command == "live":
            monitor.tail_logs()
        elif command == "stats":
            monitor.get_bot_stats()
        elif command in ["start", "stop", "restart"]:
            monitor.control_bot(command)
        elif command == "console":
            monitor.open_console()
        elif command == "vterminal":
            monitor.virtual_terminal()
        elif command == "help":
            monitor.show_help()
        else:
            print(f"❌ Unknown command: {command}")
            monitor.show_help()
        return
    
    # Interactive mode
    monitor.get_bot_status()
    monitor.show_help()
    
    while True:
        try:
            command = input("\n🎮 Monitor> ").strip().lower()
            
            if command == "exit":
                break
            elif command == "status":
                monitor.get_bot_status()
            elif command.startswith("logs"):
                parts = command.split()
                lines = int(parts[1]) if len(parts) > 1 else 50
                monitor.get_recent_logs(lines)
            elif command == "live":
                monitor.tail_logs()
            elif command == "stats":
                monitor.get_bot_stats()
            elif command in ["start", "stop", "restart"]:
                monitor.control_bot(command)
            elif command == "console":
                monitor.open_console()
            elif command == "vterminal":
                monitor.virtual_terminal()
            elif command == "help":
                monitor.show_help()
            elif command == "":
                continue
            else:
                print(f"❌ Unknown command: {command}")
                monitor.show_help()
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except EOFError:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main() 