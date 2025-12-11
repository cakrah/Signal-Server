#!/usr/bin/env python3
"""
HTTP REST API untuk Customer v1.2 - PRODUCTION READY
Sinkron dengan server dan database production-ready
"""

from flask import Flask, jsonify, request, g
import socket
import json
import time
import os
import threading
from datetime import datetime, timedelta
from flask_cors import CORS
import sqlite3
from functools import wraps
import hashlib
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS untuk semua route

@app.before_request
def assign_request_id():
    """Assign unique request ID for tracking"""
    request.id = str(uuid.uuid4())[:8]
    # Optional: Log request start
    # print(f"[{datetime.now()}] Request {request.id}: {request.method} {request.path}")

@app.after_request
def add_request_id_header(response):
    """Add request ID to response headers"""
    if hasattr(request, 'id'):
        response.headers['X-Request-ID'] = request.id
        # Optional: Log response
        # print(f"[{datetime.now()}] Response {request.id}: {response.status_code}")
    return response

# Konfigurasi Trading Server
TRADING_SERVER_HOST = os.environ.get('TRADING_SERVER_HOST', 'localhost')
TRADING_SERVER_PORT = int(os.environ.get('TRADING_SERVER_PORT', 9999))

# Rate limiting
RATE_LIMIT_PER_MINUTE = 60
rate_limits = {}
rate_lock = threading.Lock()

# Database connection pool
DATABASE_PATH = 'signals.db'

def get_db():
    """Get database connection with connection pooling"""
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = sqlite3.connect(DATABASE_PATH)
        g.sqlite_db.row_factory = sqlite3.Row
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Close database connection"""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

class CustomerAPIManager:
    """Manager untuk customer API connections - PRODUCTION READY"""
    
    def __init__(self):
        self.api_keys_file = 'api_keys_secure.json'
        self.user_status_file = 'user_status.json'
        self.api_keys = self.load_api_keys()
        self.user_status = self.load_user_status()
        self.sessions = {}
        self.session_lock = threading.Lock()
    
    def load_api_keys(self):
        """Load API keys dari file yang sama dengan server"""
        try:
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading API keys: {e}")
        
        # Return empty jika file tidak ada
        return {"admins": {}, "customers": {}}
    
    def load_user_status(self):
        """Load user status dari file yang sama dengan server"""
        try:
            if os.path.exists(self.user_status_file):
                with open(self.user_status_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading user status: {e}")
        
        return {"admins": {}, "customers": {}}
    
    def validate_customer_credentials(self, customer_id, api_key):
        """Validate customer credentials dari file yang sama"""
        # Cek di customers
        if customer_id in self.api_keys.get('customers', {}):
            expected_key = self.api_keys['customers'][customer_id]
            if api_key == expected_key:
                # Cek status user
                user_status = self.user_status.get('customers', {}).get(customer_id, {})
                if user_status.get('status', 'active') == 'active':
                    return True
        return False
        
    # TAMBAHKAN METHOD INI DI SINI:
    def refresh_data(self):
        """Refresh data from JSON files"""
        self.api_keys = self.load_api_keys()
        self.user_status = self.load_user_status()
        print(f"✅ Refreshed customer data: {len(self.api_keys.get('customers', {}))} customers")
    
    def send_to_trading_server(self, request_data, timeout=5, retries=2):
        """Send request ke socket server dengan retry mechanism"""
        for attempt in range(retries + 1):
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(timeout)
                client_socket.connect((TRADING_SERVER_HOST, TRADING_SERVER_PORT))
                
                client_socket.send(json.dumps(request_data).encode('utf-8'))
                
                response_data = b""
                while True:
                    try:
                        chunk = client_socket.recv(4096)
                        if not chunk:
                            break
                        response_data += chunk
                        if len(chunk) < 4096:
                            break
                    except socket.timeout:
                        break
                
                client_socket.close()
                
                if response_data:
                    return json.loads(response_data.decode('utf-8'))
                else:
                    if attempt < retries:
                        time.sleep(1)  # Wait before retry
                        continue
                    return {"status": "error", "message": "Empty response"}
                    
            except socket.timeout:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return {"status": "error", "message": "Connection timeout"}
            except ConnectionRefusedError:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return {"status": "error", "message": "Trading server not available"}
            except Exception as e:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return {"status": "error", "message": f"Connection error: {str(e)}"}
        
        return {"status": "error", "message": "Max retries exceeded"}
    
    def get_signals_for_customer(self, customer_id, api_key, session_id=None):
        """Get signals untuk customer"""
        request_data = {
            "customer_id": customer_id,
            "api_key": api_key,
            "action": "check_signal"
        }
        
        if session_id:
            request_data["session_id"] = session_id
        
        return self.send_to_trading_server(request_data)
    
    def get_all_signals(self, customer_id, api_key, session_id=None):
        """Get all active signals"""
        request_data = {
            "customer_id": customer_id,
            "api_key": api_key,
            "action": "get_all_signals"
        }
        
        if session_id:
            request_data["session_id"] = session_id
        
        return self.send_to_trading_server(request_data)

# Inisialisasi manager
customer_manager = CustomerAPIManager()

def check_rate_limit(customer_id):
    """Check rate limit untuk customer"""
    with rate_lock:
        max_requests = RATE_LIMIT_PER_MINUTE
        now = time.time()
        one_minute_ago = now - 60
        
        if customer_id not in rate_limits:
            rate_limits[customer_id] = []
        
        # Clean old requests
        rate_limits[customer_id] = [t for t in rate_limits[customer_id] if t > one_minute_ago]
        
        if len(rate_limits[customer_id]) >= max_requests:
            return False
        
        rate_limits[customer_id].append(now)
        return True

def authenticate_customer(f):
    """Decorator untuk authenticate customer"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        customer_id = request.headers.get('X-Customer-ID')
        api_key = request.headers.get('X-API-Key')
        
        if not customer_id or not api_key:
            return jsonify({
                "status": "error",
                "message": "Authentication required",
                "code": "AUTH_REQUIRED"
            }), 401
        
        if not customer_manager.validate_customer_credentials(customer_id, api_key):
            return jsonify({
                "status": "error",
                "message": "Invalid credentials or inactive account",
                "code": "INVALID_CREDENTIALS"
            }), 401
        
        # Check rate limit
        if not check_rate_limit(customer_id):
            return jsonify({
                "status": "error",
                "message": f"Rate limit exceeded. Max {RATE_LIMIT_PER_MINUTE} requests per minute.",
                "code": "RATE_LIMIT_EXCEEDED"
            }), 429
        
        # Log request
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO system_logs (level, module, message)
                VALUES (?, ?, ?)
            ''', ('INFO', 'customer_api', f'Request from customer {customer_id}: {request.path}'))
            db.commit()
        except:
            pass
        
        return f(customer_id, api_key, *args, **kwargs)
    
    return decorated_function

def check_database_connection():
    """Check database connection dan schema - UPDATED: Tidak cek user_stats"""
    try:
        if not os.path.exists(DATABASE_PATH):
            return False, "Database file not found"
        
        db = sqlite3.connect(DATABASE_PATH)
        cursor = db.cursor()
        
        # Check required tables exist (REMOVED user_stats check)
        required_tables = ['signals', 'signal_deliveries', 'client_connections']
        missing_tables = []
        
        for table in required_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                missing_tables.append(table)
        
        if missing_tables:
            db.close()
            return False, f"Missing tables: {', '.join(missing_tables)}"
        
        db.close()
        return True, "Database OK (JSON-based user management)"
        
    except Exception as e:
        return False, str(e)

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page"""
    # Hitung total customers dari file
    total_customers = len(customer_manager.api_keys.get('customers', {}))
    active_customers = sum(1 for c in customer_manager.user_status.get('customers', {}).values() 
                          if c.get('status') == 'active')
    
    # Check database connection
    db_ok, db_msg = check_database_connection()
    
    # Check trading server connection
    trading_server_ok = True
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        test_socket.connect((TRADING_SERVER_HOST, TRADING_SERVER_PORT))
        test_socket.close()
    except:
        trading_server_ok = False
    
    return {
        "service": "Trading Customer API",
        "version": "1.2.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "statistics": {
            "total_customers": total_customers,
            "active_customers": active_customers
        },
        "services": {
            "database": {
                "status": "ok" if db_ok else "error",
                "message": db_msg
            },
            "trading_server": {
                "status": "connected" if trading_server_ok else "disconnected",
                "host": TRADING_SERVER_HOST,
                "port": TRADING_SERVER_PORT
            }
        },
        "endpoints": {
            "GET /api/customer/health": "Health check (requires auth)",
            "GET /api/customer/signals": "Get new signals",
            "GET /api/customer/signals/all": "Get all active signals",
            "GET /api/customer/history": "Get delivery history",
            "GET /api/customer/profile": "Get customer profile"
        },
        "authentication": {
            "headers": {
                "X-Customer-ID": "Customer ID",
                "X-API-Key": "API Key"
            },
            "rate_limit": f"{RATE_LIMIT_PER_MINUTE} requests/minute"
        }
    }

@app.route('/api/customer/health', methods=['GET'])
@authenticate_customer
def customer_health(customer_id, api_key):
    """Health check untuk customer"""
    session_id = request.headers.get('X-Session-ID')
    
    # Check database
    db_ok, db_msg = check_database_connection()
    
    # Check trading server
    trading_server_ok = True
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        test_socket.connect((TRADING_SERVER_HOST, TRADING_SERVER_PORT))
        test_socket.close()
    except:
        trading_server_ok = False
    
    response = {
        "status": "healthy",
        "service": "trading-customer-api",
        "timestamp": datetime.now().isoformat(),
        "customer_id": customer_id,
        "services": {
            "database": {
                "status": "ok" if db_ok else "error",
                "message": db_msg if not db_ok else "Connected"
            },
            "trading_server": {
                "status": "connected" if trading_server_ok else "disconnected",
                "host": TRADING_SERVER_HOST,
                "port": TRADING_SERVER_PORT
            }
        },
        "session_id": session_id
    }
    
    return jsonify(response)

@app.route('/api/customer/signals', methods=['GET'])
@authenticate_customer
def get_customer_signals(customer_id, api_key):
    """Get new signals untuk customer"""
    session_id = request.headers.get('X-Session-ID')
    
    # Get signals dari trading server
    response = customer_manager.get_signals_for_customer(customer_id, api_key, session_id)
    
    # Format response untuk API
    if response.get('status') == 'success':
        signals = response.get('signals', [])
        new_signals = [s for s in signals if s.get('is_new', False)]
        
        api_response = {
            "status": "success",
            "customer_id": customer_id,
            "timestamp": datetime.now().isoformat(),
            "signals": {
                "new": new_signals,
                "all": signals,
                "new_count": len(new_signals),
                "total_count": len(signals)
            },
            "server_response": {
                "signal_available": response.get('signal_available', False),
                "message": response.get('message', '')
            }
        }
        
        # Add session_id ke headers jika ada
        if response.get('session_id'):
            api_response['session_id'] = response['session_id']
        
        return jsonify(api_response)
    else:
        return jsonify({
            "status": "error",
            "message": response.get('message', 'Unknown error'),
            "code": response.get('code', 'SERVER_ERROR')
        }), 500

@app.route('/api/customer/signals/all', methods=['GET'])
@authenticate_customer
def get_all_customer_signals(customer_id, api_key):
    """Get semua active signals"""
    session_id = request.headers.get('X-Session-ID')
    
    response = customer_manager.get_all_signals(customer_id, api_key, session_id)
    
    if response.get('status') == 'success':
        return jsonify({
            "status": "success",
            "customer_id": customer_id,
            "timestamp": datetime.now().isoformat(),
            "signals": response.get('active_signals', []),
            "total": response.get('total_signals', 0),
            "session_id": response.get('session_id')
        })
    else:
        return jsonify({
            "status": "error",
            "message": response.get('message', 'Unknown error'),
            "code": response.get('code', 'SERVER_ERROR')
        }), 500

@app.route('/api/customer/history', methods=['GET'])
@authenticate_customer
def get_customer_history(customer_id, api_key):
    """Get delivery history untuk customer - UPDATED: No user_stats table"""
    # Check database
    db_ok, db_msg = check_database_connection()
    if not db_ok:
        return jsonify({
            "status": "error",
            "message": f"Database not available: {db_msg}"
        }), 500
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get parameters
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        days = int(request.args.get('days', 7))
        
        # Calculate date range
        from_date = datetime.now() - timedelta(days=days)
        
        # Get delivery history
        query = '''
            SELECT 
                s.signal_id,
                s.symbol,
                s.type,
                s.price,
                s.sl,
                s.tp,
                s.admin_id,
                s.created_at,
                d.delivered_at
            FROM signal_deliveries d
            JOIN signals s ON d.signal_id = s.signal_id
            WHERE d.customer_id = ? 
            AND d.delivered_at >= ?
            ORDER BY d.delivered_at DESC
            LIMIT ? OFFSET ?
        '''
        
        cursor.execute(query, (customer_id, from_date.isoformat(), limit, offset))
        
        deliveries = []
        for row in cursor.fetchall():
            deliveries.append({
                'signal_id': row['signal_id'],
                'symbol': row['symbol'],
                'type': row['type'],
                'price': row['price'],
                'sl': row['sl'],
                'tp': row['tp'],
                'admin_id': row['admin_id'],
                'created_at': row['created_at'],
                'delivered_at': row['delivered_at']
            })
        
        # Get total count
        cursor.execute('''
            SELECT COUNT(*) as total 
            FROM signal_deliveries 
            WHERE customer_id = ? AND delivered_at >= ?
        ''', (customer_id, from_date.isoformat()))
        
        total = cursor.fetchone()['total']
        
        # Get customer stats from database (NOT from user_stats)
        cursor.execute('''
            SELECT 
                COUNT(*) as total_deliveries,
                MIN(delivered_at) as first_delivery,
                MAX(delivered_at) as last_delivery
            FROM signal_deliveries 
            WHERE customer_id = ?
        ''', (customer_id,))
        
        delivery_stats = cursor.fetchone()
        
        # Get connection stats
        cursor.execute('''
            SELECT 
                COUNT(*) as connection_count,
                MAX(connected_at) as last_seen
            FROM client_connections 
            WHERE client_id = ? AND client_type = 'customer'
        ''', (customer_id,))
        
        connection_stats = cursor.fetchone()
        
        # Get customer status from JSON file
        customer_status = customer_manager.user_status.get('customers', {}).get(customer_id, {})
        
        stats = {
            'total_deliveries': delivery_stats['total_deliveries'] if delivery_stats else 0,
            'first_delivery': delivery_stats['first_delivery'] if delivery_stats and delivery_stats['first_delivery'] else None,
            'last_delivery': delivery_stats['last_delivery'] if delivery_stats and delivery_stats['last_delivery'] else None,
            'connection_count': connection_stats['connection_count'] if connection_stats else 0,
            'last_seen': connection_stats['last_seen'] if connection_stats else None,
            'account_status': customer_status.get('status', 'active'),
            'account_created': customer_status.get('created', 'unknown')
        }
        
        return jsonify({
            "status": "success",
            "customer_id": customer_id,
            "deliveries": deliveries,
            "total": total,
            "limit": limit,
            "offset": offset,
            "days": days,
            "customer_stats": stats,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500

@app.route('/api/customer/profile', methods=['GET'])
@authenticate_customer
def get_customer_profile(customer_id, api_key):
    """Get customer profile dan statistics - UPDATED: No user_stats table"""
    # Check database
    db_ok, db_msg = check_database_connection()
    if not db_ok:
        return jsonify({
            "status": "error",
            "message": f"Database not available: {db_msg}"
        }), 500
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get delivery stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_deliveries,
                MIN(delivered_at) as first_delivery,
                MAX(delivered_at) as last_delivery
            FROM signal_deliveries 
            WHERE customer_id = ?
        ''', (customer_id,))
        
        delivery_stats = cursor.fetchone()
        
        # Get recent signals (last 5)
        cursor.execute('''
            SELECT 
                s.signal_id,
                s.symbol,
                s.type,
                s.price,
                d.delivered_at
            FROM signal_deliveries d
            JOIN signals s ON d.signal_id = s.signal_id
            WHERE d.customer_id = ?
            ORDER BY d.delivered_at DESC
            LIMIT 5
        ''', (customer_id,))
        
        recent_signals = cursor.fetchall()
        
        # Get favorite symbol (most received)
        cursor.execute('''
            SELECT 
                s.symbol,
                COUNT(*) as signal_count
            FROM signal_deliveries d
            JOIN signals s ON d.signal_id = s.signal_id
            WHERE d.customer_id = ?
            GROUP BY s.symbol
            ORDER BY signal_count DESC
            LIMIT 1
        ''', (customer_id,))
        
        favorite = cursor.fetchone()
        
        # Get connection stats
        cursor.execute('''
            SELECT 
                COUNT(*) as connection_count,
                MAX(connected_at) as last_seen
            FROM client_connections 
            WHERE client_id = ? AND client_type = 'customer'
        ''', (customer_id,))
        
        connection_stats = cursor.fetchone()
        
        # Get user status dari file JSON
        user_status_info = customer_manager.user_status.get('customers', {}).get(customer_id, {})
        
        # Calculate account age
        account_age_days = 0
        if user_status_info.get('created'):
            try:
                from datetime import datetime as dt
                created_date = dt.fromisoformat(user_status_info['created'].replace('Z', '+00:00'))
                account_age_days = (datetime.now() - created_date).days
            except:
                pass
        
        return jsonify({
            "status": "success",
            "customer_id": customer_id,
            "timestamp": datetime.now().isoformat(),
            "account_info": {
                "status": user_status_info.get('status', 'active'),
                "created": user_status_info.get('created', 'unknown'),
                "last_modified": user_status_info.get('last_modified', 'unknown'),
                "account_age_days": account_age_days
            },
            "statistics": {
                "total_signals_received": delivery_stats['total_deliveries'] if delivery_stats else 0,
                "first_signal": delivery_stats['first_delivery'] if delivery_stats and delivery_stats['first_delivery'] else None,
                "last_signal": delivery_stats['last_delivery'] if delivery_stats and delivery_stats['last_delivery'] else None,
                "favorite_symbol": favorite['symbol'] if favorite else "N/A",
                "favorite_count": favorite['signal_count'] if favorite else 0,
                "connection_count": connection_stats['connection_count'] if connection_stats else 0,
                "last_seen": connection_stats['last_seen'] if connection_stats else None
            },
            "recent_signals": [
                {
                    'signal_id': row['signal_id'],
                    'symbol': row['symbol'],
                    'type': row['type'],
                    'price': row['price'],
                    'delivered_at': row['delivered_at']
                }
                for row in recent_signals
            ],
            "data_source": "json_and_database"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500

def calculate_days_active(created_date_str):
    """Calculate how many days the account has been active"""
    try:
        from datetime import datetime as dt
        created_date = dt.fromisoformat(created_date_str.replace('Z', '+00:00'))
        current_date = dt.now()
        days_active = (current_date - created_date).days
        return max(days_active, 0)
    except:
        return 0

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "status": "error",
        "message": f"Endpoint not found: {request.path}",
        "available_endpoints": [
            "/api/customer/health",
            "/api/customer/signals",
            "/api/customer/signals/all",
            "/api/customer/history",
            "/api/customer/profile"
        ]
    }), 404

@app.errorhandler(429)
def too_many_requests(error):
    """Handle 429 errors"""
    return jsonify({
        "status": "error",
        "message": "Rate limit exceeded",
        "rate_limit": f"{RATE_LIMIT_PER_MINUTE} requests per minute"
    }), 429

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        "status": "error",
        "message": "Internal server error",
        "timestamp": datetime.now().isoformat()
    }), 500

def main():
    """Main function"""
    print("=" * 60)
    print("🚀 HTTP REST API for Customers v1.2 - PRODUCTION READY")
    print("=" * 60)
    print(f"📡 Port: 5001")
    print(f"🔗 Trading Server: {TRADING_SERVER_HOST}:{TRADING_SERVER_PORT}")
    print(f"📊 Rate Limit: {RATE_LIMIT_PER_MINUTE} requests/minute")
    print("=" * 60)
    
    # Load data dari file yang sama
    print("\n📂 Loading customer data from shared files...")
    
    try:
        # Load API keys
        if os.path.exists('api_keys_secure.json'):
            with open('api_keys_secure.json', 'r') as f:
                api_keys = json.load(f)
                customers = api_keys.get('customers', {})
                print(f"✅ Loaded {len(customers)} customers from api_keys_secure.json")
        else:
            print("⚠️  api_keys_secure.json not found (will be created empty)")
            
        # Load user status
        if os.path.exists('user_status.json'):
            with open('user_status.json', 'r') as f:
                user_status = json.load(f)
                active_customers = sum(1 for c in user_status.get('customers', {}).values() 
                                      if c.get('status') == 'active')
                print(f"✅ Loaded {active_customers} active customers from user_status.json")
        else:
            print("⚠️  user_status.json not found (will be created empty)")
            
    except Exception as e:
        print(f"❌ Error loading data: {e}")
    
    # Check database
    print("\n💾 Testing database connection...")
    db_ok, db_msg = check_database_connection()
    if db_ok:
        print(f"✅ Database: {db_msg}")
    else:
        print(f"❌ Database: {db_msg}")
    
    print("\n🔐 Authentication:")
    print("  Use headers:")
    print("  - X-Customer-ID: Customer ID")
    print("  - X-API-Key: API Key")
    print("  - X-Session-ID: Session ID (optional)")
    print("\n📋 Available endpoints:")
    print("  GET  /api/customer/health     - Health check")
    print("  GET  /api/customer/signals    - Get new signals")
    print("  GET  /api/customer/signals/all - All active signals")
    print("  GET  /api/customer/history    - Delivery history")
    print("  GET  /api/customer/profile    - Customer profile")
    print("=" * 60)
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)

if __name__ == '__main__':
    main()