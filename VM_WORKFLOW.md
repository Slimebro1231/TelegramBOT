# VM Bot Development Workflow

## Overview
Clean workflow for local development → testing → VM deployment

## Tools Created

### 1. `vm_monitor.py` - VM Bot Monitoring
Monitor your VM bot remotely from local machine

**Usage:**
```bash
# Interactive mode
python vm_monitor.py

# Direct commands
python vm_monitor.py status      # Show bot status
python vm_monitor.py logs 100    # Show last 100 log lines
python vm_monitor.py live        # Live log stream
python vm_monitor.py start       # Start bot
python vm_monitor.py stop        # Stop bot
python vm_monitor.py restart     # Restart bot
python vm_monitor.py console     # Open VM console
```

### 2. `dev_deploy.py` - Development to VM Deployment
Test locally then deploy to VM automatically

**Usage:**
```bash
# Test bot locally only
python dev_deploy.py test

# Test locally then deploy to VM
python dev_deploy.py deploy

# Deploy to VM without local testing
python dev_deploy.py force

# Stop VM bot
python dev_deploy.py stop

# Show VM status
python dev_deploy.py status
```

### 3. `bot_console.sh` - Quick VM Console Access
Direct SSH access to VM with bot control menu

**Usage:**
```bash
./bot_console.sh
```

## Recommended Workflow

### Daily Development:
1. **Start VM monitoring** (in separate terminal):
   ```bash
   python vm_monitor.py live
   ```

2. **Make code changes** locally

3. **Test and deploy**:
   ```bash
   python dev_deploy.py deploy
   ```

### Quick Testing:
```bash
# Test locally without deploying
python dev_deploy.py test
```

### Emergency Control:
```bash
# Stop VM bot immediately
python vm_monitor.py stop

# Or restart if stuck
python vm_monitor.py restart
```

## File Structure
```
TelegramBOT/
├── vm_monitor.py        # VM monitoring tool
├── dev_deploy.py        # Deployment automation
├── bot_console.sh       # Quick console access
├── TelegramBot-Key.pem  # SSH key (gitignored)
└── [bot files]
```

## VM Details
- **IP:** 157.10.162.223
- **User:** ubuntu
- **Bot Directory:** ~/TelegramBOT
- **Service:** telegram-bot.service

## Security Notes
- SSH key (`TelegramBot-Key.pem`) is excluded from git
- All VM-related files are in `.gitignore`
- API keys remain on VM only 