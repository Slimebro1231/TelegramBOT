#!/usr/bin/env python3
"""
Development to VM Deployment Script
Test bot locally, then deploy to VM with one command
"""

import subprocess
import sys
import os
import time
import signal
import threading
from datetime import datetime

# Configuration
VM_IP = "157.10.162.223"
VM_USER = "ubuntu"
SSH_KEY = "TelegramBot-Key.pem"
BOT_DIR = "~/TelegramBOT"
LOCAL_TEST_TIMEOUT = 30  # seconds

class DevDeploy:
    def __init__(self):
        self.ssh_base = f"ssh -i {SSH_KEY} {VM_USER}@{VM_IP}"
        self.test_process = None
        self.test_success = False
        
    def log(self, message, level="INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
        icon = icons.get(level, "ℹ️")
        print(f"[{timestamp}] {icon} {message}")
    
    def run_ssh_command(self, command, timeout=30):
        """Run SSH command on VM"""
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
    
    def check_prerequisites(self):
        """Check if all required files exist"""
        self.log("Checking prerequisites...")
        
        required_files = [
            "bot.py",
            "bitdeer_ai_client.py", 
            "news_scraper.py",
            "conflict_resolution.py",
            "requirements.txt",
            SSH_KEY
        ]
        
        missing = []
        for file in required_files:
            if not os.path.exists(file):
                missing.append(file)
        
        if missing:
            self.log(f"Missing required files: {', '.join(missing)}", "ERROR")
            return False
        
        # Check .env file
        if not os.path.exists(".env"):
            self.log("No .env file found - make sure you have API keys configured", "WARNING")
        
        self.log("Prerequisites check passed", "SUCCESS")
        return True
    
    def test_bot_locally(self):
        """Test bot locally for a short period"""
        self.log(f"Testing bot locally for {LOCAL_TEST_TIMEOUT} seconds...")
        
        try:
            # Start bot in background
            self.test_process = subprocess.Popen(
                [sys.executable, "bot.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor output for startup messages
            start_time = time.time()
            while time.time() - start_time < LOCAL_TEST_TIMEOUT:
                if self.test_process.poll() is not None:
                    # Process ended
                    stdout, stderr = self.test_process.communicate()
                    if "Bot ready!" in stdout or "✅ Bot ready!" in stdout:
                        self.test_success = True
                        self.log("Bot started successfully locally", "SUCCESS")
                    else:
                        self.log(f"Bot failed to start: {stderr}", "ERROR")
                        return False
                    break
                time.sleep(1)
            
            if self.test_process.poll() is None:
                # Still running, assume success
                self.test_success = True
                self.log("Bot is running locally", "SUCCESS")
            
            return True
            
        except Exception as e:
            self.log(f"Local test failed: {str(e)}", "ERROR")
            return False
        finally:
            self.stop_local_test()
    
    def stop_local_test(self):
        """Stop local test process"""
        if self.test_process and self.test_process.poll() is None:
            self.log("Stopping local test...")
            self.test_process.terminate()
            try:
                self.test_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.test_process.kill()
                self.test_process.wait()
    
    def stop_vm_bot(self):
        """Stop bot on VM"""
        self.log("Stopping VM bot...")
        stdout, stderr, code = self.run_ssh_command("sudo systemctl stop telegram-bot.service")
        if code == 0:
            self.log("VM bot stopped", "SUCCESS")
            return True
        else:
            self.log(f"Failed to stop VM bot: {stderr}", "ERROR")
            return False
    
    def deploy_files(self):
        """Deploy files to VM"""
        self.log("Deploying files to VM...")
        
        files_to_deploy = [
            "bot.py",
            "bitdeer_ai_client.py",
            "news_scraper.py", 
            "conflict_resolution.py",
            "requirements.txt",
            "relevance_checklist.json",
            "news_tracker.json"
        ]
        
        try:
            for file in files_to_deploy:
                if os.path.exists(file):
                    command = f"scp -i {SSH_KEY} {file} {VM_USER}@{VM_IP}:{BOT_DIR}/"
                    result = subprocess.run(command, shell=True, capture_output=True)
                    if result.returncode != 0:
                        self.log(f"Failed to deploy {file}: {result.stderr.decode()}", "ERROR")
                        return False
                    self.log(f"Deployed {file}")
            
            self.log("All files deployed successfully", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Deployment failed: {str(e)}", "ERROR")
            return False
    
    def update_vm_dependencies(self):
        """Update dependencies on VM if needed"""
        self.log("Updating VM dependencies...")
        
        commands = [
            f"cd {BOT_DIR}",
            "source .venv/bin/activate",
            "pip install -r requirements.txt"
        ]
        
        command = " && ".join(commands)
        stdout, stderr, code = self.run_ssh_command(command, timeout=60)
        
        if code == 0:
            self.log("Dependencies updated", "SUCCESS")
            return True
        else:
            self.log(f"Failed to update dependencies: {stderr}", "ERROR")
            return False
    
    def start_vm_bot(self):
        """Start bot on VM"""
        self.log("Starting VM bot...")
        
        stdout, stderr, code = self.run_ssh_command("sudo systemctl start telegram-bot.service")
        if code != 0:
            self.log(f"Failed to start VM bot: {stderr}", "ERROR")
            return False
        
        # Wait and check status
        time.sleep(3)
        stdout, stderr, code = self.run_ssh_command("systemctl is-active telegram-bot.service")
        
        if code == 0 and stdout.strip() == "active":
            self.log("VM bot started successfully", "SUCCESS")
            return True
        else:
            self.log("VM bot failed to start properly", "ERROR")
            return False
    
    def show_vm_status(self):
        """Show final VM bot status"""
        self.log("VM Bot Status:")
        
        # Service status
        stdout, stderr, code = self.run_ssh_command("systemctl status telegram-bot.service --no-pager -l")
        if stdout:
            for line in stdout.split('\n')[:8]:
                if line.strip():
                    print(f"  {line}")
        
        # Recent logs
        self.log("Recent logs:")
        stdout, stderr, code = self.run_ssh_command("journalctl -u telegram-bot.service -n 5 --no-pager")
        if stdout:
            for line in stdout.split('\n')[-5:]:
                if line.strip():
                    print(f"  {line}")
    
    def sync_news_tracker(self):
        """Sync news_tracker.json bidirectionally, keeping the most up-to-date version"""
        self.log("Syncing news_tracker.json...")
        
        local_file = "news_tracker.json"
        remote_file = f"{BOT_DIR}/news_tracker.json"
        
        try:
            # Get local file modification time
            local_mtime = 0
            if os.path.exists(local_file):
                local_mtime = os.path.getmtime(local_file)
                local_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(local_mtime))
                self.log(f"Local news_tracker.json: {local_time_str}")
            else:
                self.log("No local news_tracker.json found")
            
            # Get remote file modification time
            stdout, stderr, code = self.run_ssh_command(f"stat -c %Y {remote_file} 2>/dev/null || echo 0")
            remote_mtime = 0
            if code == 0 and stdout.strip().isdigit():
                remote_mtime = int(stdout.strip())
                remote_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(remote_mtime))
                self.log(f"Remote news_tracker.json: {remote_time_str}")
            else:
                self.log("No remote news_tracker.json found")
            
            # Determine sync direction
            if local_mtime == 0 and remote_mtime == 0:
                self.log("No news_tracker.json found on either side - will create new")
                return True
            elif local_mtime == 0:
                # Download from remote
                self.log("Downloading news_tracker.json from VM...")
                command = f"scp -i {SSH_KEY} {VM_USER}@{VM_IP}:{remote_file} {local_file}"
                result = subprocess.run(command, shell=True, capture_output=True)
                if result.returncode == 0:
                    self.log("Downloaded news_tracker.json from VM", "SUCCESS")
                else:
                    self.log(f"Failed to download: {result.stderr.decode()}", "ERROR")
                    return False
            elif remote_mtime == 0:
                # Upload to remote
                self.log("Uploading news_tracker.json to VM...")
                command = f"scp -i {SSH_KEY} {local_file} {VM_USER}@{VM_IP}:{remote_file}"
                result = subprocess.run(command, shell=True, capture_output=True)
                if result.returncode == 0:
                    self.log("Uploaded news_tracker.json to VM", "SUCCESS")
                else:
                    self.log(f"Failed to upload: {result.stderr.decode()}", "ERROR")
                    return False
            elif remote_mtime > local_mtime:
                # Remote is newer, download
                self.log("Remote news_tracker.json is newer - downloading...")
                command = f"scp -i {SSH_KEY} {VM_USER}@{VM_IP}:{remote_file} {local_file}"
                result = subprocess.run(command, shell=True, capture_output=True)
                if result.returncode == 0:
                    self.log("Downloaded newer news_tracker.json from VM", "SUCCESS")
                else:
                    self.log(f"Failed to download: {result.stderr.decode()}", "ERROR")
                    return False
            elif local_mtime > remote_mtime:
                # Local is newer, upload
                self.log("Local news_tracker.json is newer - uploading...")
                command = f"scp -i {SSH_KEY} {local_file} {VM_USER}@{VM_IP}:{remote_file}"
                result = subprocess.run(command, shell=True, capture_output=True)
                if result.returncode == 0:
                    self.log("Uploaded newer news_tracker.json to VM", "SUCCESS")
                else:
                    self.log(f"Failed to upload: {result.stderr.decode()}", "ERROR")
                    return False
            else:
                # Files are the same age
                self.log("news_tracker.json files are synchronized", "SUCCESS")
            
            return True
            
        except Exception as e:
            self.log(f"Error syncing news_tracker.json: {str(e)}", "ERROR")
            return False

def main():
    if len(sys.argv) < 2:
        print("🚀 Development to VM Deployment Tool")
        print("=" * 40)
        print("Usage:")
        print("  python dev_deploy.py test        - Test bot locally only")
        print("  python dev_deploy.py deploy      - Test locally then deploy to VM")
        print("  python dev_deploy.py force       - Deploy to VM without local testing") 
        print("  python dev_deploy.py stop        - Stop VM bot only")
        print("  python dev_deploy.py status      - Show VM bot status")
        return
    
    action = sys.argv[1].lower()
    deployer = DevDeploy()
    
    if action == "test":
        if not deployer.check_prerequisites():
            sys.exit(1)
        if deployer.test_bot_locally():
            deployer.log("Local test completed successfully", "SUCCESS")
        else:
            deployer.log("Local test failed", "ERROR")
            sys.exit(1)
    
    elif action == "deploy":
        if not deployer.check_prerequisites():
            sys.exit(1)
        
        # Test locally first
        if not deployer.test_bot_locally():
            deployer.log("Local test failed - aborting deployment", "ERROR")
            sys.exit(1)
        
        # Sync news_tracker.json before deployment
        if not deployer.sync_news_tracker():
            deployer.log("Failed to sync news_tracker.json", "WARNING")
        
        # Deploy to VM
        if not deployer.stop_vm_bot():
            sys.exit(1)
        
        if not deployer.deploy_files():
            sys.exit(1)
        
        if not deployer.update_vm_dependencies():
            sys.exit(1)
        
        if not deployer.start_vm_bot():
            sys.exit(1)
        
        # Sync news_tracker.json after deployment
        if not deployer.sync_news_tracker():
            deployer.log("Failed to sync news_tracker.json after deployment", "WARNING")
        
        deployer.show_vm_status()
        deployer.log("Deployment completed successfully! 🎉", "SUCCESS")
    
    elif action == "force":
        if not deployer.check_prerequisites():
            sys.exit(1)
        
        deployer.log("Force deploying without local testing...")
        
        # Sync news_tracker.json before deployment
        if not deployer.sync_news_tracker():
            deployer.log("Failed to sync news_tracker.json", "WARNING")
        
        if not deployer.stop_vm_bot():
            sys.exit(1)
        
        if not deployer.deploy_files():
            sys.exit(1)
        
        if not deployer.update_vm_dependencies():
            sys.exit(1)
        
        if not deployer.start_vm_bot():
            sys.exit(1)
        
        # Sync news_tracker.json after deployment
        if not deployer.sync_news_tracker():
            deployer.log("Failed to sync news_tracker.json after deployment", "WARNING")
        
        deployer.show_vm_status()
        deployer.log("Force deployment completed! 🎉", "SUCCESS")
    
    elif action == "stop":
        deployer.stop_vm_bot()
    
    elif action == "status":
        deployer.show_vm_status()
    
    else:
        deployer.log(f"Unknown action: {action}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Deployment interrupted by user")
        sys.exit(1) 