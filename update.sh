#!/bin/bash
# update.sh - Update Trading System

echo "========================================="
echo "🔄 Updating Trading System"
echo "========================================="

cd ~/trading-system

# Backup before update
echo "💾 Creating backup..."
./scripts/backup_database.py

# Stop services
echo "🛑 Stopping services..."
./stop.sh

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Update Python packages
echo "🐍 Updating Python packages..."
source venv/bin/activate
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "Installing/updating dependencies..."
    pip install --upgrade -r requirements.txt
fi

# Update PM2
echo "📊 Updating PM2..."
sudo npm install -g pm2@latest

# Update from Git (if using version control)
if [ -d ".git" ]; then
    echo "📥 Pulling latest code..."
    git pull origin main
fi

# Start services
echo "🚀 Starting services..."
./start.sh

echo ""
echo "✅ Update completed!"
echo "========================================="
echo "📊 System Status:"
pm2 status --silent
echo "========================================="