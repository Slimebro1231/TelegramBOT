#!/usr/bin/env python3
"""
VM Bot Monitor - Local monitoring tool for remote Telegram bot
Shows status, logs, and history of the bot running on Bitdeer VM
"""

import subprocess
import sys
import os
import json
from datetime import datetime
import time

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
    
    def show_help(self):
        """Show available commands"""
        print("\n🎮 VM BOT MONITOR COMMANDS")
        print("=" * 40)
        print("status     - Show current bot status")
        print("logs       - Show recent logs (default 50 lines)")
        print("logs N     - Show recent N lines of logs")
        print("live       - Show live log stream (Ctrl+C to stop)")
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