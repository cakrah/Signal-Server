#!/bin/bash
# stop.sh - Stop Trading System on GCP VM

echo "========================================="
echo "🛑 Stopping Trading System"
echo "========================================="

cd ~/trading-system

echo "⏳ Stopping services..."

# Stop PM2 processes
pm2 stop all > /dev/null 2>&1
pm2 delete all > /dev/null 2>&1

# Kill any remaining processes
pkill -f "server.py" || true
pkill -f "gunicorn" || true
pkill -f "admin_api_server" || true
pkill -f "customer_api" || true

# Clear PM2 logs
pm2 flush > /dev/null 2>&1

# Remove PM2 startup
pm2 unstartup > /dev/null 2>&1

echo "✅ All services stopped"

# Show what's still running
echo ""
echo "📊 Checking remaining processes:"
echo "========================================="

PORTS="9999 5000 5001 80"
for port in $PORTS; do
    if sudo lsof -i :$port > /dev/null 2>&1; then
        echo "⚠️  Port $port is still in use:"
        sudo lsof -i :$port | grep LISTEN
    else
        echo "✅ Port $port is free"
    fi
done

echo ""
echo "🎯 To start services again: ./start.sh"
echo "========================================="