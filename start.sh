#!/bin/bash
# start.sh - Start Trading System on GCP VM

echo "========================================="
echo "🚀 Starting Trading System v2.0"
echo "========================================="

cd ~/trading-system

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✅ Loaded environment variables"
else
    echo "⚠️  .env file not found, using defaults"
    export TRADING_SERVER_PORT=9999
    export ADMIN_API_PORT=5000
    export CUSTOMER_API_PORT=5001
    export DB_PATH=~/trading-system/signals.db
fi

# Activate Python virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Activated Python virtual environment"
else
    echo "❌ Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Create necessary directories
mkdir -p logs backups

# Initialize database if not exists
if [ ! -f "$DB_PATH" ]; then
    echo "💾 Initializing database..."
    python scripts/init_database.py
fi

echo "🔧 Starting services..."

# Service 1: Trading Socket Server
echo "   🟢 Trading Server (port $TRADING_SERVER_PORT)..."
pm2 start server.py \
    --name "trading-server" \
    --interpreter python3 \
    -- \
    --host 0.0.0.0 \
    --port $TRADING_SERVER_PORT \
    > logs/trading_server_start.log 2>&1

# Service 2: Admin API
echo "   🟢 Admin API (port $ADMIN_API_PORT)..."
pm2 start gunicorn \
    --name "admin-api" \
    -- \
    --bind 0.0.0.0:$ADMIN_API_PORT \
    --workers 2 \
    --threads 4 \
    --access-logfile logs/admin_api_access.log \
    --error-logfile logs/admin_api_error.log \
    --log-level info \
    --timeout 120 \
    admin_api_server:app \
    > logs/admin_api_start.log 2>&1

# Service 3: Customer API
echo "   🟢 Customer API (port $CUSTOMER_API_PORT)..."
pm2 start gunicorn \
    --name "customer-api" \
    -- \
    --bind 0.0.0.0:$CUSTOMER_API_PORT \
    --workers 2 \
    --threads 4 \
    --access-logfile logs/customer_api_access.log \
    --error-logfile logs/customer_api_error.log \
    --log-level info \
    --timeout 120 \
    customer_api:app \
    > logs/customer_api_start.log 2>&1

# Save PM2 process list
pm2 save > /dev/null 2>&1

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
echo "========================================="

# Get VM external IP
VM_IP=$(curl -s http://checkip.amazonaws.com || hostname -I | awk '{print $1}')

echo "🌐 Public IP: $VM_IP"
echo ""

# Check each service
echo "1. Trading Socket Server:"
if curl -s http://localhost:$TRADING_SERVER_PORT > /dev/null 2>&1; then
    echo "   ✅ Running on port $TRADING_SERVER_PORT"
else
    echo "   ❌ Not responding on port $TRADING_SERVER_PORT"
fi

echo ""
echo "2. Admin API:"
if curl -s http://localhost:$ADMIN_API_PORT/api/admin/health > /dev/null 2>&1; then
    echo "   ✅ Running on port $ADMIN_API_PORT"
    echo "   🔗 Admin Panel: http://$VM_IP/"
    echo "   🔗 API Health: http://$VM_IP/api/admin/health"
else
    echo "   ❌ Not responding on port $ADMIN_API_PORT"
fi

echo ""
echo "3. Customer API:"
if curl -s http://localhost:$CUSTOMER_API_PORT/api/customer/health > /dev/null 2>&1; then
    echo "   ✅ Running on port $CUSTOMER_API_PORT"
    echo "   🔗 API Health: http://$VM_IP:$CUSTOMER_API_PORT/api/customer/health"
else
    echo "   ❌ Not responding on port $CUSTOMER_API_PORT"
fi

echo ""
echo "4. Nginx Proxy:"
if sudo systemctl is-active --quiet nginx; then
    echo "   ✅ Running"
    echo "   🔗 Main URL: http://$VM_IP"
else
    echo "   ❌ Not running"
fi

echo ""
echo "========================================="
echo "✅ All services started!"
echo "========================================="
echo ""
echo "📋 Management Commands:"
echo "   pm2 status              # View service status"
echo "   pm2 logs                # View all logs"
echo "   pm2 logs trading-server # View trading server logs"
echo "   pm2 logs admin-api      # View admin API logs"
echo "   pm2 logs customer-api   # View customer API logs"
echo "   ./stop.sh               # Stop all services"
echo "   ./update.sh             # Update system"
echo ""
echo "📁 Logs Directory: ~/trading-system/logs/"
echo "💾 Database: $DB_PATH"
echo "========================================="

# Setup auto-restart on reboot
pm2 startup > /dev/null 2>&1