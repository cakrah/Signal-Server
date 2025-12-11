#!/bin/bash
# setup.sh - Setup Trading System on GCP VM
# Paste di terminal VM: nano setup.sh

echo "========================================="
echo "🚀 Setting up Trading System on GCP VM"
echo "========================================="

# Update system
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python
echo "🐍 Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# Install Nginx
echo "🌐 Installing Nginx..."
sudo apt-get install -y nginx

# Install SQLite (for database)
echo "💾 Installing SQLite..."
sudo apt-get install -y sqlite3

# Install PM2 for process management (Node.js needed)
echo "📊 Installing Node.js and PM2..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g pm2

# Create project structure
echo "📁 Creating project structure..."
mkdir -p ~/trading-system/{scripts,logs,backups,config,static}
cd ~/trading-system

# Create Python virtual environment
echo "🔧 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip

# Create requirements.txt
cat > requirements.txt << 'EOF'
Flask==2.3.3
Flask-CORS==4.0.0
gunicorn==21.2.0
python-dotenv==1.0.0
python-socketio==5.10.0
eventlet==0.33.3
requests==2.31.0
EOF

pip install -r requirements.txt

# Create .env file
echo "⚙️ Creating environment file..."
cat > .env << 'EOF'
# Trading System Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-change-this

# Port Configuration
TRADING_SERVER_PORT=9999
ADMIN_API_PORT=5000
CUSTOMER_API_PORT=5001

# Security
ADMIN_RATE_LIMIT=120
CUSTOMER_RATE_LIMIT=60
SESSION_TIMEOUT_MINUTES=30

# Trading Settings
SIGNAL_EXPIRY_MINUTES=5
MAX_ACTIVE_SIGNALS=50

# Database
DB_PATH=/home/$USER/trading-system/signals.db

# Logging
LOG_DIR=/home/$USER/trading-system/logs
EOF

# Create start.sh
echo "▶️ Creating start script..."
cat > start.sh << 'EOF'
#!/bin/bash
cd ~/trading-system

# Activate virtual environment
source venv/bin/activate

# Load environment variables
set -a
source .env
set +a

# Start services with PM2
echo "🚀 Starting Trading System..."

# Service 1: Trading Socket Server
pm2 start server.py --name "trading-server" --interpreter python3 -- \
    --host 0.0.0.0 --port $TRADING_SERVER_PORT

# Service 2: Admin API
pm2 start gunicorn --name "admin-api" -- \
    --bind 0.0.0.0:$ADMIN_API_PORT \
    --workers 2 \
    --threads 4 \
    admin_api_server:app

# Service 3: Customer API  
pm2 start gunicorn --name "customer-api" -- \
    --bind 0.0.0.0:$CUSTOMER_API_PORT \
    --workers 2 \
    --threads 4 \
    customer_api:app

# Save PM2 process list
pm2 save

# Enable PM2 startup
pm2 startup

echo "✅ All services started!"
echo ""
echo "📊 Service Status:"
echo "   Trading Server:  http://$(curl -s ifconfig.me):$TRADING_SERVER_PORT"
echo "   Admin API:       http://$(curl -s ifconfig.me):$ADMIN_API_PORT"
echo "   Admin Panel:     http://$(curl -s ifconfig.me):$ADMIN_API_PORT/"
echo "   Customer API:    http://$(curl -s ifconfig.me):$CUSTOMER_API_PORT"
EOF

chmod +x start.sh

# Create stop.sh
echo "🛑 Creating stop script..."
cat > stop.sh << 'EOF'
#!/bin/bash
echo "Stopping Trading System..."
pm2 stop all
pm2 delete all
echo "✅ All services stopped"
EOF

chmod +x stop.sh

# Create update.sh
echo "🔄 Creating update script..."
cat > update.sh << 'EOF'
#!/bin/bash
cd ~/trading-system

echo "Updating Trading System..."

# Stop services
./stop.sh

# Pull latest code (if using git)
# git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Start services
./start.sh

echo "✅ Update completed!"
EOF

chmod +x update.sh

# Create Nginx config
echo "🌐 Creating Nginx configuration..."
sudo tee /etc/nginx/sites-available/trading-system << 'EOF'
server {
    listen 80;
    server_name _;
    
    # Admin API
    location /api/admin/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Customer API
    location /api/customer/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Admin Panel (static files)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/trading-system /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 9999/tcp  # Trading Server
sudo ufw allow 5000/tcp  # Admin API
sudo ufw allow 5001/tcp  # Customer API
sudo ufw --force enable

echo ""
echo "========================================="
echo "✅ SETUP COMPLETED!"
echo "========================================="
echo ""
echo "📋 Next Steps:"
echo "1. Upload your Python files to:"
echo "   /home/$USER/trading-system/"
echo ""
echo "2. Start the system:"
echo "   cd ~/trading-system"
echo "   ./start.sh"
echo ""
echo "3. Check status:"
echo "   pm2 status"
echo ""
echo "4. View logs:"
echo "   pm2 logs"
echo ""
echo "5. Access your application:"
echo "   http://$(curl -s ifconfig.me)"
echo "========================================="