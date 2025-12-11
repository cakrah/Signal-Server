#!/usr/bin/env python3
"""
HTTP REST API Server untuk Admin Panel v2.0 - PRODUCTION READY
Sinkron dengan server production-ready dan database
"""

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from functools import wraps
import socket
import json
import time
import os
import threading
import sqlite3
from datetime import datetime, timedelta
import hashlib
import uuid

app = Flask(__name__)
CORS(app)

@app.before_request
def assign_request_id():
    """Assign unique request ID for tracking"""
    request.id = str(uuid.uuid4())[:8]
    # Log request start
    app.logger.info(f"Request {request.id}: {request.method} {request.path}")

@app.after_request
def add_request_id_header(response):
    """Add request ID to response headers"""
    if hasattr(request, 'id'):
        response.headers['X-Request-ID'] = request.id
        # Log response
        app.logger.info(f"Response {request.id}: {response.status_code}")
    return response

# Konfigurasi dari environment variables
TRADING_SERVER_HOST = os.environ.get('TRADING_SERVER_HOST', 'localhost')
TRADING_SERVER_PORT = int(os.environ.get('TRADING_SERVER_PORT', 9999))
API_KEYS_FILE = 'api_keys_secure.json'
USER_STATUS_FILE = 'user_status.json'
DATABASE_PATH = 'signals.db'

# Rate limiting
RATE_LIMIT_PER_MINUTE = 120  # Higher limit untuk admin
rate_limits = {}
rate_lock = threading.Lock()

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

class AdminAPIManager:
    """Manager untuk admin API - PRODUCTION READY"""
    
    def __init__(self):
        self.api_keys_file = API_KEYS_FILE
        self.user_status_file = USER_STATUS_FILE
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
    
    def validate_admin_credentials(self, admin_id, api_key):
        """Validate admin credentials dari file yang sama"""
        if admin_id in self.api_keys.get('admins', {}):
            expected_key = self.api_keys['admins'][admin_id]
            if api_key == expected_key:
                user_status = self.user_status.get('admins', {}).get(admin_id, {})
                if user_status.get('status', 'active') == 'active':
                    return True
        return False
        
    # TAMBAHKAN METHOD INI DI SINI:
    def refresh_data(self):
        """Refresh data from JSON files"""
        self.api_keys = self.load_api_keys()
        self.user_status = self.load_user_status()
        print(f"✅ Refreshed data: {len(self.api_keys.get('admins', {}))} admins, "
              f"{len(self.api_keys.get('customers', {}))} customers")
    
    
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
                        time.sleep(1)
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
    
    def get_server_stats(self, admin_id, api_key):
        """Get server statistics"""
        request_data = {
            "admin_id": admin_id,
            "api_key": api_key,
            "action": "get_stats"
        }
        return self.send_to_trading_server(request_data)
    
    def list_users_with_status(self, admin_id, api_key):
        """List all users with status"""
        request_data = {
            "admin_id": admin_id,
            "api_key": api_key,
            "action": "list_users_with_status"
        }
        return self.send_to_trading_server(request_data)
    
    def add_api_key(self, admin_id, api_key, user_type, user_id, new_api_key):
        """Add new API key"""
        request_data = {
            "admin_id": admin_id,
            "api_key": api_key,
            "action": "add_api_key",
            "user_type": user_type,
            "user_id": user_id,
            "api_key": new_api_key
        }
        return self.send_to_trading_server(request_data)
    
    def set_user_status(self, admin_id, api_key, user_type, user_id, status):
        """Set user status"""
        request_data = {
            "admin_id": admin_id,
            "api_key": api_key,
            "action": "set_user_status",
            "user_type": user_type,
            "user_id": user_id,
            "status": status
        }
        return self.send_to_trading_server(request_data)
    
    def revoke_api_key(self, admin_id, api_key, user_type, user_id):
        """Revoke API key"""
        request_data = {
            "admin_id": admin_id,
            "api_key": api_key,
            "action": "revoke_api_key",
            "user_type": user_type,
            "user_id": user_id
        }
        return self.send_to_trading_server(request_data)

# Inisialisasi manager
admin_manager = AdminAPIManager()

def check_rate_limit(admin_id):
    """Check rate limit untuk admin"""
    with rate_lock:
        max_requests = RATE_LIMIT_PER_MINUTE
        now = time.time()
        one_minute_ago = now - 60
        
        if admin_id not in rate_limits:
            rate_limits[admin_id] = []
        
        rate_limits[admin_id] = [t for t in rate_limits[admin_id] if t > one_minute_ago]
        
        if len(rate_limits[admin_id]) >= max_requests:
            return False
        
        rate_limits[admin_id].append(now)
        return True

def authenticate_admin(f):
    """Decorator untuk authenticate admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = request.headers.get('X-Admin-ID')
        api_key = request.headers.get('X-API-Key')
        
        if not admin_id or not api_key:
            return jsonify({
                "status": "error",
                "message": "Authentication required",
                "code": "AUTH_REQUIRED"
            }), 401
        
        if not admin_manager.validate_admin_credentials(admin_id, api_key):
            return jsonify({
                "status": "error",
                "message": "Invalid credentials or inactive account",
                "code": "INVALID_CREDENTIALS"
            }), 401
        
        # Check rate limit
        if not check_rate_limit(admin_id):
            return jsonify({
                "status": "error",
                "message": f"Rate limit exceeded. Max {RATE_LIMIT_PER_MINUTE} requests per minute.",
                "code": "RATE_LIMIT_EXCEEDED"
            }), 429
        
        return f(admin_id, api_key, *args, **kwargs)
    
    return decorated_function

def check_database_schema():
    """Check database schema compatibility"""
    try:
        if not os.path.exists(DATABASE_PATH):
            return False, "Database file not found"
        
        db = sqlite3.connect(DATABASE_PATH)
        cursor = db.cursor()
        
        # Check if user_stats table exists (new schema)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_stats'")
        has_user_stats = cursor.fetchone() is not None
        
        # Check if signals table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
        has_signals = cursor.fetchone() is not None
        
        db.close()
        
        if has_user_stats and has_signals:
            return True, "Database schema compatible"
        elif has_signals:
            return True, "Legacy database schema"
        else:
            return False, "Invalid database schema"
        
    except Exception as e:
        return False, str(e)

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page"""
    # Count users dari file
    total_admins = len(admin_manager.api_keys.get('admins', {}))
    total_customers = len(admin_manager.api_keys.get('customers', {}))
    active_admins = sum(1 for a in admin_manager.user_status.get('admins', {}).values() 
                       if a.get('status') == 'active')
    active_customers = sum(1 for c in admin_manager.user_status.get('customers', {}).values() 
                          if c.get('status') == 'active')
    
    # Check services
    db_ok, db_msg = check_database_schema()
    
    # Check trading server
    trading_server_ok = True
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        test_socket.connect((TRADING_SERVER_HOST, TRADING_SERVER_PORT))
        test_socket.close()
    except:
        trading_server_ok = False
    
    return {
        "service": "Trading Server Admin API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "statistics": {
            "admins": {
                "total": total_admins,
                "active": active_admins
            },
            "customers": {
                "total": total_customers,
                "active": active_customers
            }
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
            "GET /api/admin/health": "Health check",
            "GET /api/admin/stats": "Server statistics",
            "GET /api/admin/signals": "Active signals",
            "GET /api/admin/signals/detailed": "Detailed signals with deliveries",
            "GET /api/admin/deliveries": "Signal delivery history",
            "GET /api/admin/users": "List all users",
            "GET /api/admin/customers/with-stats": "Customers with delivery stats",
            "GET /api/admin/users/<type>/<id>/stats": "Get user statistics",
            "POST /api/admin/users": "Add new user",
            "PUT /api/admin/users/<type>/<id>/status": "Update user status",
            "PUT /api/admin/users/<type>/<id>/apikey": "Update API key",
            "DELETE /api/admin/users/<type>/<id>": "Delete user"
        },
        "authentication": {
            "headers": {
                "X-Admin-ID": "Admin ID",
                "X-API-Key": "API Key"
            },
            "rate_limit": f"{RATE_LIMIT_PER_MINUTE} requests/minute"
        }
    }

@app.route('/api/admin/health', methods=['GET'])
@authenticate_admin
def health_check(admin_id, api_key):
    """Health check endpoint"""
    # Test trading server connection
    server_response = admin_manager.get_server_stats(admin_id, api_key)
    
    # Check database
    db_ok, db_msg = check_database_schema()
    
    return jsonify({
        "status": "healthy",
        "service": "trading-admin-api",
        "timestamp": datetime.now().isoformat(),
        "admin_id": admin_id,
        "services": {
            "database": {
                "status": "ok" if db_ok else "error",
                "message": db_msg
            },
            "trading_server": {
                "connected": server_response.get('status') == 'success',
                "response_time": "immediate"
            }
        }
    })

@app.route('/api/admin/stats', methods=['GET'])
@authenticate_admin
def get_stats(admin_id, api_key):
    """Get server statistics"""
    response = admin_manager.get_server_stats(admin_id, api_key)
    
    if response.get('status') == 'success':
        return jsonify(response)
    else:
        # Fallback ke database stats
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Get signals count
            cursor.execute("SELECT COUNT(*) as total FROM signals")
            total_signals = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as active FROM signals WHERE status = 'active'")
            active_signals = cursor.fetchone()['active']
            
            # Get deliveries count
            cursor.execute("SELECT COUNT(*) as total FROM signal_deliveries")
            total_deliveries = cursor.fetchone()['total']
            
            # Get user counts
            cursor.execute("SELECT COUNT(DISTINCT customer_id) as customers FROM signal_deliveries")
            total_customers = cursor.fetchone()['customers']
            
            # Get recent activity
            cursor.execute('''
                SELECT COUNT(*) as recent FROM admin_activities 
                WHERE created_at >= datetime('now', '-1 day')
            ''')
            recent_activities = cursor.fetchone()['recent']
            
            return jsonify({
                "status": "success",
                "stats": {
                    "server_status": "running",
                    "active_signals": active_signals,
                    "total_signals": total_signals,
                    "total_deliveries": total_deliveries,
                    "total_customers": total_customers,
                    "recent_activities": recent_activities,
                    "timestamp": datetime.now().isoformat()
                }
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Failed to get statistics: {str(e)}"
            }), 500

@app.route('/api/admin/signals', methods=['GET'])
@authenticate_admin
def get_signals(admin_id, api_key):
    """Get active signals"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get active signals
        cursor.execute('''
            SELECT signal_id, symbol, type, price, sl, tp, admin_id, 
                   created_at, expires_at, delivery_count
            FROM signals 
            WHERE status = 'active' 
            ORDER BY created_at DESC
        ''')
        
        signals = []
        for row in cursor.fetchall():
            signals.append({
                'signal_id': row['signal_id'],
                'symbol': row['symbol'],
                'type': row['type'],
                'price': row['price'],
                'sl': row['sl'],
                'tp': row['tp'],
                'admin_id': row['admin_id'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'delivery_count': row['delivery_count']
            })
        
        return jsonify({
            "status": "success",
            "signals": signals,
            "total": len(signals),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get signals: {str(e)}"
        }), 500

@app.route('/api/admin/signals/detailed', methods=['GET'])
@authenticate_admin
def get_signals_detailed(admin_id, api_key):
    """Get all signals with delivery information"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get parameters
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status', '')
        admin_filter = request.args.get('admin_id', '')
        
        # Build query
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
                s.expires_at,
                s.status,
                s.delivery_count,
                COUNT(d.id) as customer_count
            FROM signals s
            LEFT JOIN signal_deliveries d ON s.signal_id = d.signal_id
            WHERE 1=1
        '''
        params = []
        
        if status:
            query += ' AND s.status = ?'
            params.append(status)
        
        if admin_filter:
            query += ' AND s.admin_id = ?'
            params.append(admin_filter)
        
        query += '''
            GROUP BY s.signal_id
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
        '''
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        signals = []
        for row in rows:
            signals.append({
                'signal_id': row['signal_id'],
                'symbol': row['symbol'],
                'type': row['type'],
                'price': row['price'],
                'sl': row['sl'],
                'tp': row['tp'],
                'admin_id': row['admin_id'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'status': row['status'],
                'delivery_count': row['delivery_count'],
                'customer_count': row['customer_count']
            })
        
        # Get total count
        count_query = 'SELECT COUNT(*) as total FROM signals WHERE 1=1'
        count_params = []
        
        if status:
            count_query += ' AND status = ?'
            count_params.append(status)
        
        if admin_filter:
            count_query += ' AND admin_id = ?'
            count_params.append(admin_filter)
        
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['total']
        
        return jsonify({
            "status": "success",
            "signals": signals,
            "total": total,
            "limit": limit,
            "offset": offset,
            "admin_id": admin_id
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get signals: {str(e)}"
        }), 500

@app.route('/api/admin/deliveries', methods=['GET'])
@authenticate_admin
def get_deliveries(admin_id, api_key):
    """Get signal delivery history"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get parameters
        customer_id = request.args.get('customer_id', '')
        signal_type = request.args.get('type', '')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        days = int(request.args.get('days', 7))
        
        # Build query
        query = '''
            SELECT 
                d.signal_id,
                s.symbol,
                s.type,
                s.price,
                s.sl,
                s.tp,
                s.admin_id,
                d.customer_id,
                d.delivered_at,
                s.created_at as signal_created
            FROM signal_deliveries d
            JOIN signals s ON d.signal_id = s.signal_id
            WHERE d.delivered_at >= ?
        '''
        params = [datetime.now() - timedelta(days=days)]
        
        if customer_id:
            query += ' AND d.customer_id = ?'
            params.append(customer_id)
        
        if signal_type:
            query += ' AND s.type = ?'
            params.append(signal_type)
        
        query += ' ORDER BY d.delivered_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        deliveries = []
        for row in rows:
            deliveries.append({
                'signal_id': row['signal_id'],
                'symbol': row['symbol'],
                'type': row['type'],
                'price': row['price'],
                'sl': row['sl'],
                'tp': row['tp'],
                'admin_id': row['admin_id'],
                'customer_id': row['customer_id'],
                'delivered_at': row['delivered_at'],
                'signal_created': row['signal_created']
            })
        
        # Get total count
        count_query = '''
            SELECT COUNT(*) as total 
            FROM signal_deliveries d
            JOIN signals s ON d.signal_id = s.signal_id
            WHERE d.delivered_at >= ?
        '''
        count_params = [datetime.now() - timedelta(days=days)]
        
        if customer_id:
            count_query += ' AND d.customer_id = ?'
            count_params.append(customer_id)
        
        if signal_type:
            count_query += ' AND s.type = ?'
            count_params.append(signal_type)
        
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()['total']
        
        return jsonify({
            "status": "success",
            "deliveries": deliveries,
            "total": total,
            "limit": limit,
            "offset": offset,
            "days": days
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get deliveries: {str(e)}"
        }), 500

@app.route('/api/admin/users', methods=['GET'])
@authenticate_admin
def get_users(admin_id, api_key):
    """Get all users with status - UPDATED: Full JSON-based"""
    try:
        # Load fresh data from files
        admin_manager.api_keys = admin_manager.load_api_keys()
        admin_manager.user_status = admin_manager.load_user_status()
        
        users_data = {
            "admins": {},
            "customers": {}
        }
        
        # Process admins
        for admin_id_key, api_key_val in admin_manager.api_keys.get('admins', {}).items():
            status_info = admin_manager.user_status.get('admins', {}).get(admin_id_key, {})
            
            # Get signal count from database
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM signals WHERE admin_id = ?', (admin_id_key,))
                signal_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT MAX(created_at) FROM signals WHERE admin_id = ?', (admin_id_key,))
                last_signal = cursor.fetchone()[0]
            except:
                signal_count = 0
                last_signal = None
            
            users_data['admins'][admin_id_key] = {
                'api_key': api_key_val[:10] + '...' if len(api_key_val) > 10 else api_key_val,
                'status': status_info.get('status', 'unknown'),
                'created': status_info.get('created', 'unknown'),
                'last_modified': status_info.get('last_modified', 'unknown'),
                'signal_count': signal_count,
                'last_signal': last_signal
            }
        
        # Process customers
        for cust_id, api_key_val in admin_manager.api_keys.get('customers', {}).items():
            status_info = admin_manager.user_status.get('customers', {}).get(cust_id, {})
            
            # Get delivery stats from database
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM signal_deliveries WHERE customer_id = ?', (cust_id,))
                delivery_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT MAX(delivered_at) FROM signal_deliveries WHERE customer_id = ?', (cust_id,))
                last_delivery = cursor.fetchone()[0]
            except:
                delivery_count = 0
                last_delivery = None
            
            users_data['customers'][cust_id] = {
                'api_key': api_key_val[:10] + '...' if len(api_key_val) > 10 else api_key_val,
                'status': status_info.get('status', 'unknown'),
                'created': status_info.get('created', 'unknown'),
                'last_modified': status_info.get('last_modified', 'unknown'),
                'delivery_count': delivery_count,
                'last_delivery': last_delivery
            }
        
        return jsonify({
            "status": "success",
            "users": users_data,
            "total_admins": len(users_data['admins']),
            "total_customers": len(users_data['customers']),
            "active_admins": sum(1 for a in users_data['admins'].values() if a['status'] == 'active'),
            "active_customers": sum(1 for c in users_data['customers'].values() if c['status'] == 'active'),
            "source": "json_files_with_db_stats"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get users: {str(e)}"
        }), 500

@app.route('/api/admin/users/<user_type>/<user_id>/stats', methods=['GET'])
@authenticate_admin
def get_user_stats(admin_id, api_key, user_type, user_id):
    """Get user statistics - UPDATED: Tidak pakai user_stats table"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        if user_type == 'customers':
            # Get customer delivery stats dari database
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_deliveries,
                    MIN(delivered_at) as first_delivery,
                    MAX(delivered_at) as last_delivery
                FROM signal_deliveries 
                WHERE customer_id = ?
            ''', (user_id,))
            
            delivery_stats = cursor.fetchone()
            
            # Get customer stats dari JSON file
            customer_status = admin_manager.user_status.get('customers', {}).get(user_id, {})
            
            # Get connection stats dari client_connections table
            cursor.execute('''
                SELECT 
                    COUNT(*) as connection_count,
                    MAX(connected_at) as last_seen
                FROM client_connections 
                WHERE client_id = ? AND client_type = 'customer'
            ''', (user_id,))
            
            connection_stats = cursor.fetchone()
            
            stats = {
                'user_id': user_id,
                'user_type': user_type,
                'account_status': customer_status.get('status', 'unknown'),
                'account_created': customer_status.get('created', 'unknown'),
                'total_deliveries': delivery_stats['total_deliveries'] if delivery_stats else 0,
                'first_delivery': delivery_stats['first_delivery'] if delivery_stats and delivery_stats['first_delivery'] else None,
                'last_delivery': delivery_stats['last_delivery'] if delivery_stats and delivery_stats['last_delivery'] else None,
                'connection_count': connection_stats['connection_count'] if connection_stats else 0,
                'last_seen': connection_stats['last_seen'] if connection_stats else None,
                'source': 'json_files'
            }
            
        elif user_type == 'admins':
            # Get admin signal stats dari database
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_signals,
                    MIN(created_at) as first_signal,
                    MAX(created_at) as last_signal
                FROM signals 
                    WHERE admin_id = ?
            ''', (user_id,))
            
            signal_stats = cursor.fetchone()
            
            # Get admin stats dari JSON file
            admin_status = admin_manager.user_status.get('admins', {}).get(user_id, {})
            
            # Get connection stats dari client_connections table
            cursor.execute('''
                SELECT 
                    COUNT(*) as connection_count,
                    MAX(connected_at) as last_seen
                FROM client_connections 
                WHERE client_id = ? AND client_type = 'admin'
            ''', (user_id,))
            
            connection_stats = cursor.fetchone()
            
            stats = {
                'user_id': user_id,
                'user_type': user_type,
                'account_status': admin_status.get('status', 'unknown'),
                'account_created': admin_status.get('created', 'unknown'),
                'total_signals': signal_stats['total_signals'] if signal_stats else 0,
                'first_signal': signal_stats['first_signal'] if signal_stats and signal_stats['first_signal'] else None,
                'last_signal': signal_stats['last_signal'] if signal_stats and signal_stats['last_signal'] else None,
                'connection_count': connection_stats['connection_count'] if connection_stats else 0,
                'last_seen': connection_stats['last_seen'] if connection_stats else None,
                'source': 'json_files'
            }
        
        return jsonify({
            "status": "success",
            "stats": stats
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get user stats: {str(e)}"
        }), 500

@app.route('/api/admin/users', methods=['POST'])
@authenticate_admin
def add_user(admin_id, api_key):
    """Add new user"""
    data = request.json
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "No data provided"
        }), 400
    
    required_fields = ['user_type', 'user_id']
    for field in required_fields:
        if field not in data:
            return jsonify({
                "status": "error",
                "message": f"Missing required field: {field}"
            }), 400
    
    if data['user_type'] not in ['admins', 'customers']:
        return jsonify({
            "status": "error", 
            "message": "user_type must be 'admins' or 'customers'"
        }), 400
    
    # Generate API key jika tidak disediakan
    if 'api_key' not in data or not data['api_key']:
        import random
        import string
        import secrets
        
        prefix = 'sk_admin_' if data['user_type'] == 'admins' else 'sk_cust_'
        random_part = secrets.token_urlsafe(16)
        data['api_key'] = prefix + random_part
    
    response = admin_manager.add_api_key(
        admin_id, api_key,
        data['user_type'],
        data['user_id'],
        data['api_key']
    )
    
    if response.get('status') == 'success':
        # Log activity
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO admin_activities (admin_id, action, details, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, 'add_user', f"Added {data['user_type']}/{data['user_id']}", request.remote_addr))
            db.commit()
        except:
            pass
        
        return jsonify(response)
    else:
        return jsonify(response), 500

@app.route('/api/admin/users/<user_type>/<user_id>/status', methods=['PUT'])
@authenticate_admin
def update_user_status(admin_id, api_key, user_type, user_id):
    """Update user status"""
    data = request.json
    
    if not data or 'status' not in data:
        return jsonify({
            "status": "error",
            "message": "Status is required"
        }), 400
    
    if data['status'] not in ['active', 'inactive']:
        return jsonify({
            "status": "error",
            "message": "Status must be 'active' or 'inactive'"
        }), 400
    
    if user_type not in ['admins', 'customers']:
        return jsonify({
            "status": "error",
            "message": "user_type must be 'admins' or 'customers'"
        }), 400
    
    response = admin_manager.set_user_status(
        admin_id, api_key,
        user_type, user_id,
        data['status']
    )
    
    if response.get('status') == 'success':
        # Log activity
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO admin_activities (admin_id, action, details, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, 'set_user_status', f"Set {user_type}/{user_id} to {data['status']}", request.remote_addr))
            db.commit()
        except:
            pass
        
        return jsonify(response)
    else:
        return jsonify(response), 500

@app.route('/api/admin/users/<user_type>/<user_id>', methods=['DELETE'])
@authenticate_admin
def delete_user(admin_id, api_key, user_type, user_id):
    """Delete user"""
    if user_type not in ['admins', 'customers']:
        return jsonify({
            "status": "error",
            "message": "user_type must be 'admins' or 'customers'"
        }), 400
    
    response = admin_manager.revoke_api_key(
        admin_id, api_key,
        user_type, user_id
    )
    
    if response.get('status') == 'success':
        # Log activity
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO admin_activities (admin_id, action, details, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, 'delete_user', f"Deleted {user_type}/{user_id}", request.remote_addr))
            db.commit()
        except:
            pass
        
        return jsonify(response)
    else:
        return jsonify(response), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "Endpoint not found",
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(429)
def too_many_requests(error):
    return jsonify({
        "status": "error",
        "message": "Rate limit exceeded",
        "rate_limit": f"{RATE_LIMIT_PER_MINUTE} requests per minute"
    }), 429

def main():
    """Main function"""
    print("=" * 60)
    print("🚀 HTTP REST API for Admin Panel v2.0 - PRODUCTION READY")
    print("=" * 60)
    print(f"📡 Port: 5000")
    print(f"🔗 Trading Server: {TRADING_SERVER_HOST}:{TRADING_SERVER_PORT}")
    print(f"📊 Rate Limit: {RATE_LIMIT_PER_MINUTE} requests/minute")
    print("=" * 60)
    
    # Load data
    print("\n📂 Loading admin data from shared files...")
    
    try:
        if os.path.exists(API_KEYS_FILE):
            with open(API_KEYS_FILE, 'r') as f:
                api_keys = json.load(f)
                admins = api_keys.get('admins', {})
                print(f"✅ Loaded {len(admins)} admins from {API_KEYS_FILE}")
        else:
            print(f"⚠️  {API_KEYS_FILE} not found")
            
        if os.path.exists(USER_STATUS_FILE):
            with open(USER_STATUS_FILE, 'r') as f:
                user_status = json.load(f)
                active_admins = sum(1 for a in user_status.get('admins', {}).values() 
                                  if a.get('status') == 'active')
                print(f"✅ Loaded {active_admins} active admins from {USER_STATUS_FILE}")
        else:
            print(f"⚠️  {USER_STATUS_FILE} not found")
            
    except Exception as e:
        print(f"❌ Error loading data: {e}")
    
    # Check database
    print("\n💾 Testing database connection...")
    db_ok, db_msg = check_database_schema()
    if db_ok:
        print(f"✅ Database: {db_msg}")
    else:
        print(f"❌ Database: {db_msg}")
    
    print("\n🔐 Authentication:")
    print("  Use headers:")
    print("  - X-Admin-ID: Admin ID")
    print("  - X-API-Key: API Key")
    print("\n📋 Available endpoints:")
    print("  GET  /api/admin/health          - Health check")
    print("  GET  /api/admin/stats           - Server statistics")
    print("  GET  /api/admin/signals         - Active signals")
    print("  GET  /api/admin/signals/detailed - Detailed signals")
    print("  GET  /api/admin/deliveries      - Delivery history")
    print("  GET  /api/admin/users           - List all users")
    print("  GET  /api/admin/customers/with-stats - Customers with stats")
    print("  GET  /api/admin/users/.../stats - User statistics")
    print("  POST /api/admin/users           - Add new user")
    print("  PUT  /api/admin/users/.../status - Update user status")
    print("  PUT  /api/admin/users/.../apikey - Update API key")
    print("  DELETE /api/admin/users/...     - Delete user")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

if __name__ == '__main__':
    main()