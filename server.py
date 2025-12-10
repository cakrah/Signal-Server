#!/usr/bin/env python3
"""
Trading Signal Server v4.0 - WITH API KEY FOR BOTH ADMIN & CUSTOMER
Enhanced security with API Key authentication for all users
"""

import socket
import threading
import json
import time
from datetime import datetime
import signal
import sys
import os
import uuid
import traceback

# Import database and logging
try:
    from database import database
    from logging_config import setup_logging, log_signal, log_access
    DB_ENABLED = True
    logger, signal_logger, access_logger = setup_logging('TradingSignalServer')
    print("✅ Database and logging modules loaded successfully")
except ImportError as e:
    print(f"⚠️ Database/Logging modules not found: {e}")
    print("⚠️ Running in fallback mode (in-memory only)")
    DB_ENABLED = False
    logger = None
    signal_logger = None
    access_logger = None

class TradingSignalServer:
    def __init__(self, config_file='config.json'):
        # Load konfigurasi
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            print("✅ Config loaded from config.json")
        except FileNotFoundError:
            self.config = {
                'server': {'host': '0.0.0.0', 'port': 9999},
                'security': {
                    'rate_limit_per_minute': 60,
                    'max_connections': 100,
                    'session_timeout_minutes': 30
                },
                'signal_settings': {
                    'expiry_minutes': 5,
                    'max_active_signals': 10,
                    'check_interval_seconds': 60
                }
            }
            print("⚠️ config.json not found, using default config")
        
        # === CLOUD DEPLOYMENT SETTINGS ===
        self.host = self.config['server']['host']
        self.port = int(os.environ.get('PORT', self.config['server']['port']))
        
        # === SECURITY SETTINGS ===
        # Load API Keys for both admins and customers
        self.admin_api_keys, self.customer_api_keys = self.load_api_keys()
        
        # Rate limiting
        self.rate_limits = {}  # user_id: [timestamps]
        self.max_requests_per_minute = self.config['security'].get('rate_limit_per_minute', 60)
        
        # Admin rate limit (higher limit)
        self.admin_max_requests = 120
        
        # Connection tracking
        self.active_connections = 0
        self.max_connections = self.config['security'].get('max_connections', 100)
        self.connection_lock = threading.Lock()
        
        # Session tracking
        self.active_sessions = {}  # session_id: {user_id, login_time, last_activity}
        self.session_timeout = self.config['security'].get('session_timeout_minutes', 30) * 60
        # =============================
        
        self.expiry_minutes = self.config['signal_settings']['expiry_minutes']
        self.max_active_signals = self.config['signal_settings'].get('max_active_signals', 10)
        
        # Data storage
        self.active_signals = []  # List of active signals
        self.signal_lock = threading.Lock()
        self.running = True
        
        # Tracking signal deliveries per customer
        self.customer_received_signals = {}
        
        # Admin activity log
        self.admin_activities = []
        
        # Setup socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Initialize database if enabled
        if DB_ENABLED:
            self.init_database()
        
        # Untuk tracking uptime
        self.start_time = time.time()
        
        self.log_info(f"Server initialized at {self.host}:{self.port}")
        self.log_info("Mode: Each customer gets EACH active signal ONCE")
        self.log_info(f"Security: API Key authentication for ALL users")
        self.log_info(f"Admins: {len(self.admin_api_keys)} | Customers: {len(self.customer_api_keys)}")
        self.log_info(f"Rate limit: Customers={self.max_requests_per_minute}/min, Admins={self.admin_max_requests}/min")
    
    def load_api_keys(self):
        """Load API keys from file for both admins and customers"""
        api_keys_file = 'api_keys.json'
        
        try:
            if os.path.exists(api_keys_file):
                with open(api_keys_file, 'r') as f:
                    all_keys = json.load(f)
                    
                    # Separate admin and customer keys
                    admin_keys = all_keys.get('admins', {})
                    customer_keys = all_keys.get('customers', {})
                    
                    self.log_info(f"Loaded {len(admin_keys)} admin keys and {len(customer_keys)} customer keys")
                    return admin_keys, customer_keys
        except Exception as e:
            self.log_warning(f"Error loading API keys: {e}")
        
        # Default API keys (for testing/fallback)
        default_admin_keys = {
            "ADMIN_001": "sk_admin_secure123",
            "ADMIN_002": "sk_admin_secure456",
            "SUPER_ADMIN": "sk_admin_super789"
        }
        
        default_customer_keys = {
            "CUST_001": "sk_cust_abc123def456",
            "CUST_002": "sk_cust_xyz789uvw012",
            "CUST_003": "sk_cust_mno345pqr678",
            "CUST_004": "sk_cust_jkl234mno567",
            "CUST_005": "sk_cust_efg890hij123"
        }
        
        self.log_warning(f"Using default API keys. Create {api_keys_file} for production.")
        return default_admin_keys, default_customer_keys
    
    def check_rate_limit(self, user_id, is_admin=False):
        """Check if user has exceeded rate limit"""
        now = time.time()
        one_minute_ago = now - 60
        
        # Use different limits for admin and customer
        max_requests = self.admin_max_requests if is_admin else self.max_requests_per_minute
        
        # Initialize if not exists
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = []
        
        # Remove old requests
        self.rate_limits[user_id] = [
            t for t in self.rate_limits[user_id] 
            if t > one_minute_ago
        ]
        
        # Check limit
        if len(self.rate_limits[user_id]) >= max_requests:
            return False
        
        # Add current request
        self.rate_limits[user_id].append(now)
        return True
    
    def create_session(self, user_id, client_type):
        """Create new session for user"""
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'client_type': client_type,
            'login_time': time.time(),
            'last_activity': time.time()
        }
        return session_id
    
    def validate_session(self, session_id, user_id):
        """Validate user session"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        
        # Check if session belongs to user
        if session['user_id'] != user_id:
            return False
        
        # Check if session expired
        current_time = time.time()
        if current_time - session['last_activity'] > self.session_timeout:
            del self.active_sessions[session_id]
            return False
        
        # Update last activity
        session['last_activity'] = current_time
        return True
    
    def authenticate(self, request, client_type):
        """
        Authenticate client with API Key (both admin and customer)
        Also supports legacy password for backward compatibility
        """
        password = request.get('password', '')
        api_key = request.get('api_key', '')
        user_id = request.get('admin_id') if client_type == 'admin' else request.get('customer_id', '')
        session_id = request.get('session_id', '')
        
        # If session ID provided, validate it
        if session_id and user_id:
            if self.validate_session(session_id, user_id):
                return True, user_id
        
        if client_type == 'admin':
            # Method 1: API Key authentication
            if api_key:
                # Check if API key exists in admin keys
                for admin_id, key in self.admin_api_keys.items():
                    if api_key == key:
                        # If admin_id provided, must match
                        if user_id and user_id != admin_id:
                            continue
                        
                        # Create session
                        session_id = self.create_session(admin_id, 'admin')
                        self.log_info(f"Admin authenticated via API key: {admin_id}, Session: {session_id[:8]}...")
                        
                        # Log admin activity
                        self.log_admin_activity(admin_id, "login", "API Key authentication")
                        
                        return True, admin_id, session_id
            
            # Method 2: Legacy password (backward compatibility)
            if password:
                # Check if password matches any admin key (for migration)
                for admin_id, key in self.admin_api_keys.items():
                    if password == key:
                        self.log_info(f"Admin authenticated via legacy password: {admin_id}")
                        
                        # Create session
                        session_id = self.create_session(admin_id, 'admin')
                        self.log_admin_activity(admin_id, "login", "Legacy password")
                        
                        return True, admin_id, session_id
            
            self.log_warning(f"Admin authentication failed for: {user_id}")
            return False, None, None
        
        elif client_type == 'customer':
            # Method 1: API Key authentication
            if api_key:
                # Check if API key exists in customer keys
                for cust_id, key in self.customer_api_keys.items():
                    if api_key == key:
                        # If customer_id provided, must match
                        if user_id and user_id != cust_id:
                            continue
                        
                        # Create session
                        session_id = self.create_session(cust_id, 'customer')
                        self.log_info(f"Customer authenticated via API key: {cust_id}, Session: {session_id[:8]}...")
                        
                        return True, cust_id, session_id
            
            # Method 2: Legacy password (backward compatibility)
            if password:
                # Check if password matches any customer key (for migration)
                for cust_id, key in self.customer_api_keys.items():
                    if password == key:
                        self.log_info(f"Customer authenticated via legacy password: {cust_id}")
                        
                        # Create session
                        session_id = self.create_session(cust_id, 'customer')
                        
                        return True, cust_id, session_id
            
            self.log_warning(f"Customer authentication failed for: {user_id}")
            return False, None, None
        
        return False, None, None
    
    def log_admin_activity(self, admin_id, action, details=""):
        """Log admin activity for auditing"""
        activity = {
            'admin_id': admin_id,
            'action': action,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'ip': threading.current_thread().name
        }
        
        self.admin_activities.append(activity)
        
        # Keep only last 100 activities
        if len(self.admin_activities) > 100:
            self.admin_activities = self.admin_activities[-100:]
        
        # Log to database if enabled
        if DB_ENABLED:
            try:
                database.log_admin_activity(admin_id, action, details)
            except Exception as db_err:
                self.log_warning(f"Database activity log warning: {db_err}")
    
    def init_database(self):
        """Initialize database tables"""
        if DB_ENABLED:
            try:
                database.fix_database_issues()
                self.log_info("Database system ready")
            except Exception as e:
                self.log_warning(f"Database check warning: {e}")
    
    def log_info(self, message):
        """Log info message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] INFO: {message}")
        if logger:
            logger.info(message)
    
    def log_error(self, message):
        """Log error message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ERROR: {message}")
        if logger:
            logger.error(message)
    
    def log_warning(self, message):
        """Log warning message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] WARNING: {message}")
        if logger:
            logger.warning(message)
    
    def start(self):
        """Start the server"""
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.log_info(f"✅ Server running at {self.host}:{self.port}")
            self.log_info("📡 Waiting for connections...")
            self.log_info("🔔 Mode: Each customer gets EACH active signal ONCE")
            self.log_info(f"📊 Max active signals: {self.max_active_signals}")
            self.log_info(f"🔒 Security: API Key authentication for ALL users")
            self.log_info(f"👥 Admins: {len(self.admin_api_keys)} | Customers: {len(self.customer_api_keys)}")
            self.log_info(f"⚡ Rate limit: Customers={self.max_requests_per_minute}/min, Admins={self.admin_max_requests}/min")
            
            # Thread untuk menerima koneksi
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            
            # Thread untuk cleanup dengan database
            cleanup_thread = threading.Thread(target=self.periodic_cleanup_with_db)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            # Thread untuk statistik
            stats_thread = threading.Thread(target=self.periodic_stats)
            stats_thread.daemon = True
            stats_thread.start()
            
            # Thread untuk cleanup rate limits
            rate_limit_thread = threading.Thread(target=self.cleanup_rate_limits)
            rate_limit_thread.daemon = True
            rate_limit_thread.start()
            
            # Thread untuk session cleanup
            session_thread = threading.Thread(target=self.cleanup_sessions)
            session_thread.daemon = True
            session_thread.start()
            
            # Tunggu sampai server dimatikan
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            self.log_error(f"Failed to start server: {e}")
            self.log_error(f"Error details: {type(e).__name__}")
            traceback.print_exc()
        finally:
            self.stop()
    
    def cleanup_rate_limits(self):
        """Periodically clean up old rate limit entries"""
        while self.running:
            time.sleep(300)  # Setiap 5 menit
            
            try:
                now = time.time()
                five_minutes_ago = now - 300
                
                for user_id in list(self.rate_limits.keys()):
                    # Hapus entries yang lebih dari 5 menit
                    self.rate_limits[user_id] = [
                        t for t in self.rate_limits[user_id] 
                        if t > five_minutes_ago
                    ]
                    
                    # Jika kosong, hapus key
                    if not self.rate_limits[user_id]:
                        del self.rate_limits[user_id]
                
                self.log_info(f"🧹 Rate limits cleanup: {len(self.rate_limits)} active users")
                
            except Exception as e:
                self.log_error(f"Error in rate limit cleanup: {e}")
    
    def cleanup_sessions(self):
        """Clean up expired sessions"""
        while self.running:
            time.sleep(60)  # Check every minute
            
            try:
                now = time.time()
                expired_sessions = []
                
                for session_id, session in self.active_sessions.items():
                    if now - session['last_activity'] > self.session_timeout:
                        expired_sessions.append(session_id)
                
                # Remove expired sessions
                for session_id in expired_sessions:
                    del self.active_sessions[session_id]
                
                if expired_sessions:
                    self.log_info(f"🧹 Session cleanup: Removed {len(expired_sessions)} expired sessions")
                    
            except Exception as e:
                self.log_error(f"Error in session cleanup: {e}")
    
    def accept_connections(self):
        """Accept connections from clients"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                
                # Check connection limit
                with self.connection_lock:
                    if self.active_connections >= self.max_connections:
                        self.log_warning(f"Connection limit reached, rejecting {address}")
                        error_response = {
                            'status': 'error',
                            'message': 'Server busy, too many connections'
                        }
                        client_socket.send(json.dumps(error_response).encode('utf-8'))
                        client_socket.close()
                        continue
                    
                    self.active_connections += 1
                
                self.log_info(f"🔌 New connection from {address} (Active: {self.active_connections}/{self.max_connections})")
                
                # Log ke database
                if DB_ENABLED:
                    try:
                        database.add_client_connection('unknown', str(address))
                    except Exception as db_err:
                        self.log_warning(f"Database log warning: {db_err}")
                
                # Buat thread untuk menangani client
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.log_error(f"Error accepting connection: {e}")
    
    def handle_client(self, client_socket, address):
        """Handle communication with client"""
        try:
            # Terima data awal
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return
            
            request = json.loads(data)
            
            # Identifikasi tipe client
            client_type = request.get('client_type', 'customer')
            user_id = request.get('admin_id') if client_type == 'admin' else request.get('customer_id', f"IP_{address[0]}")
            
            # === RATE LIMITING ===
            if not self.check_rate_limit(user_id, client_type == 'admin'):
                response = {
                    'status': 'error', 
                    'message': f'Rate limit exceeded. Maximum {self.admin_max_requests if client_type == "admin" else self.max_requests_per_minute} requests per minute.'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                client_socket.close()
                self.log_warning(f"Rate limit exceeded for {user_id}")
                return
            
            # Authentikasi dengan API Key
            auth_result, auth_user_id, session_id = self.authenticate(request, client_type)
            if not auth_result:
                response = {
                    'status': 'error', 
                    'message': 'Authentication failed. Check your API Key or credentials.'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                client_socket.close()
                self.log_warning(f"Authentication failed from {address}")
                return
            
            # Update user_id with authenticated one
            user_id = auth_user_id
            
            # Update database dengan client_type yang benar
            if DB_ENABLED:
                try:
                    database.add_client_connection(client_type, str(address))
                except Exception as db_err:
                    self.log_warning(f"Database update warning: {db_err}")
            
            # Tambahkan session_id ke response
            request['session_id'] = session_id
            
            if client_type == 'admin':
                self.handle_admin(client_socket, request, address, user_id, session_id)
            elif client_type == 'customer':
                self.handle_customer(client_socket, request, address, user_id, session_id)
            else:
                response = {'status': 'error', 'message': 'Unknown client type'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except json.JSONDecodeError:
            self.log_error(f"Invalid JSON data from {address}")
            error_response = {'status': 'error', 'message': 'Invalid JSON format'}
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
        except Exception as e:
            self.log_error(f"Error handling client {address}: {e}")
            traceback.print_exc()
        finally:
            try:
                client_socket.close()
            except:
                pass
            
            # Update connection count
            with self.connection_lock:
                self.active_connections -= 1
            
            # Update disconnect in database
            if DB_ENABLED:
                try:
                    database.update_client_disconnect(str(address))
                except:
                    pass
    
    def handle_admin(self, client_socket, request, address, admin_id, session_id):
        """Handle admin client with API Key authentication"""
        try:
            action = request.get('action')
            
            # Include session_id in all responses
            base_response = {'session_id': session_id}
            
            if action == 'send_signal':
                # Validasi data signal dengan TP
                required_fields = ['symbol', 'price', 'sl', 'tp', 'type']
                for field in required_fields:
                    if field not in request:
                        response = {'status': 'error', 'message': f'Missing field: {field}'}
                        response.update(base_response)
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                
                # Validasi type
                signal_type = request['type'].lower()
                if signal_type not in ['buy', 'sell']:
                    response = {'status': 'error', 'message': 'Type must be "buy" or "sell"'}
                    response.update(base_response)
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    return
                
                # Validasi TP berdasarkan type
                try:
                    price = float(request['price'])
                    sl = float(request['sl'])
                    tp = float(request['tp'])
                except ValueError:
                    response = {'status': 'error', 'message': 'Price, SL, and TP must be numbers'}
                    response.update(base_response)
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    return
                
                if signal_type == 'buy':
                    if tp <= price:
                        response = {'status': 'error', 'message': 'TP must be greater than entry price for BUY'}
                        response.update(base_response)
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                    if sl >= price:
                        response = {'status': 'error', 'message': 'SL must be less than entry price for BUY'}
                        response.update(base_response)
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                else:  # sell
                    if tp >= price:
                        response = {'status': 'error', 'message': 'TP must be less than entry price for SELL'}
                        response.update(base_response)
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                    if sl <= price:
                        response = {'status': 'error', 'message': 'SL must be greater than entry price for SELL'}
                        response.update(base_response)
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                
                with self.signal_lock:
                    # Simpan ke database jika enabled
                    signal_id = None
                    if DB_ENABLED:
                        try:
                            signal_id = database.add_signal(
                                symbol=request['symbol'],
                                price=price,
                                sl=sl,
                                tp=tp,
                                signal_type=signal_type,
                                admin_address=str(address),
                                admin_id=admin_id,
                                expiry_minutes=self.expiry_minutes
                            )
                            
                            self.log_info(f"✅ Signal saved to database: ID={signal_id}")
                            
                        except Exception as db_error:
                            self.log_error(f"Database error: {db_error}")
                            # Fallback to in-memory storage
                            signal_id = f"MEM_{int(time.time())}_{len(self.active_signals)}"
                    
                    # Generate signal ID jika tidak ada
                    if not signal_id:
                        signal_id = f"SIG_{int(time.time())}_{len(self.active_signals)}"
                    
                    # Buat signal object
                    new_signal = {
                        'signal_id': str(signal_id),
                        'symbol': request['symbol'],
                        'price': price,
                        'sl': sl,
                        'tp': tp,
                        'type': signal_type,
                        'timestamp': datetime.now().isoformat(),
                        'created_at': time.time(),
                        'admin_address': str(address),
                        'admin_id': admin_id
                    }
                    
                    # Tambahkan ke active signals
                    self.active_signals.append(new_signal)
                    
                    # Batasi jumlah active signals
                    if len(self.active_signals) > self.max_active_signals:
                        # Hapus yang paling tua
                        removed = self.active_signals.pop(0)
                        self.log_info(f"🧹 Removed old signal: {removed['signal_id']}")
                    
                    # Log admin activity
                    self.log_admin_activity(admin_id, "send_signal", 
                                           f"{new_signal['symbol']} {new_signal['type']} at {new_signal['price']}")
                    
                    self.log_info(f"📡 New Signal #{signal_id} from admin {admin_id}")
                    self.log_info(f"   Symbol: {new_signal['symbol']} {new_signal['type']}")
                    self.log_info(f"   Price: {new_signal['price']}, SL: {new_signal['sl']}, TP: {new_signal['tp']}")
                    self.log_info(f"   Active signals: {len(self.active_signals)}")
                    
                    response = {
                        'status': 'success',
                        'message': 'Signal successfully received',
                        'signal': {
                            'signal_id': str(signal_id),
                            'symbol': new_signal['symbol'],
                            'type': new_signal['type'],
                            'price': new_signal['price'],
                            'sl': new_signal['sl'],
                            'tp': new_signal['tp'],
                            'timestamp': new_signal['timestamp']
                        },
                        'total_active_signals': len(self.active_signals),
                        'admin_id': admin_id
                    }
                    response.update(base_response)
                    
                    client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif action == 'get_history':
                # Kirim history dari database
                limit = request.get('limit', 50)
                
                if DB_ENABLED:
                    try:
                        history = database.get_signal_history(limit=limit)
                        response = {
                            'status': 'success',
                            'history': history,
                            'admin_id': admin_id
                        }
                        response.update(base_response)
                    except Exception as db_err:
                        response = {
                            'status': 'error',
                            'message': f'Database error: {db_err}',
                            'admin_id': admin_id
                        }
                        response.update(base_response)
                else:
                    response = {
                        'status': 'error',
                        'message': 'Database not available',
                        'admin_id': admin_id
                    }
                    response.update(base_response)
                client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif action == 'get_stats':
                # Kirim statistik
                try:
                    stats = self.get_system_stats(admin_id)
                    response = {
                        'status': 'success',
                        'stats': stats,
                        'admin_id': admin_id
                    }
                    response.update(base_response)
                except Exception as e:
                    response = {
                        'status': 'error',
                        'message': f'Error getting stats: {e}',
                        'admin_id': admin_id
                    }
                    response.update(base_response)
                client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif action == 'get_health':
                # Health check endpoint
                health_stats = self.get_health_status()
                response = {
                    'status': 'success',
                    'health': health_stats,
                    'admin_id': admin_id
                }
                response.update(base_response)
                client_socket.send(json.dumps(response).encode('utf-8'))
                
            elif action == 'get_admin_activity':
                # Get admin activity log
                limit = request.get('limit', 20)
                activities = self.admin_activities[-limit:] if self.admin_activities else []
                response = {
                    'status': 'success',
                    'activities': activities,
                    'admin_id': admin_id,
                    'total_activities': len(self.admin_activities)
                }
                response.update(base_response)
                client_socket.send(json.dumps(response).encode('utf-8'))
                
            elif action == 'list_api_keys':
                # List API keys (admin only)
                response = {
                    'status': 'success',
                    'admin_keys': {k: '***' + v[-4:] for k, v in self.admin_api_keys.items()},
                    'customer_keys': {k: '***' + v[-4:] for k, v in self.customer_api_keys.items()},
                    'admin_id': admin_id
                }
                response.update(base_response)
                client_socket.send(json.dumps(response).encode('utf-8'))
                
            else:
                response = {'status': 'error', 'message': 'Invalid action'}
                response.update(base_response)
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except KeyError as e:
            response = {'status': 'error', 'message': f'Field {e} not found'}
            response.update(base_response)
            client_socket.send(json.dumps(response).encode('utf-8'))
            self.log_error(f"Key error in admin request: {e}")
        except ValueError as e:
            response = {'status': 'error', 'message': f'Invalid value: {e}'}
            response.update(base_response)
            client_socket.send(json.dumps(response).encode('utf-8'))
            self.log_error(f"Value error in admin request: {e}")
        except Exception as e:
            self.log_error(f"Error handling admin: {e}")
            traceback.print_exc()
    
    def get_health_status(self):
        """Get health status for monitoring"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        return {
            'status': 'healthy' if self.running else 'stopped',
            'connections': self.active_connections,
            'active_signals': len(self.active_signals),
            'total_customers': len(self.customer_received_signals),
            'uptime_seconds': int(time.time() - self.start_time),
            'memory_mb': round(process.memory_info().rss / 1024 / 1024, 2),
            'cpu_percent': process.cpu_percent(),
            'rate_limited_users': len(self.rate_limits),
            'active_sessions': len(self.active_sessions),
            'admin_activities': len(self.admin_activities),
            'timestamp': datetime.now().isoformat()
        }
    
    def handle_customer(self, client_socket, request, address, customer_id, session_id):
        """Handle customer client"""
        try:
            action = request.get('action', 'check_signal')
            
            # Include session_id in responses
            base_response = {'session_id': session_id, 'customer_id': customer_id}
            
            if action == 'check_signal':
                self._handle_customer_check_signal(client_socket, customer_id, address, session_id)
            elif action == 'get_all_signals':
                self._handle_customer_get_all_signals(client_socket, customer_id, session_id)
            else:
                self._handle_customer_check_signal(client_socket, customer_id, address, session_id)
                
        except Exception as e:
            self.log_error(f"Error in handle_customer: {e}")
            traceback.print_exc()
            error_response = {
                'status': 'error',
                'message': f'Server error: {str(e)}',
                'customer_id': customer_id
            }
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def _handle_customer_check_signal(self, client_socket, customer_id, address, session_id):
        """Handle customer checking for NEW signals"""
        try:
            new_signals_for_customer = []
            
            with self.signal_lock:
                # Inisialisasi tracking untuk customer ini jika belum ada
                if customer_id not in self.customer_received_signals:
                    self.customer_received_signals[customer_id] = set()
                
                # Dapatkan signals yang sudah diterima oleh customer ini
                received_signal_ids = self.customer_received_signals[customer_id]
                
                # Filter expired signals terlebih dahulu
                current_time = time.time()
                expiry_seconds = self.expiry_minutes * 60
                
                # Hapus signals yang expired
                non_expired_signals = []
                for signal in self.active_signals:
                    signal_age = current_time - signal['created_at']
                    if signal_age <= expiry_seconds:
                        non_expired_signals.append(signal)
                    else:
                        self.log_info(f"🕒 Signal {signal['signal_id']} expired (age: {signal_age:.0f}s)")
                
                # Update active signals dengan yang belum expired
                self.active_signals = non_expired_signals
                
                # Cari signals yang BELUM pernah diterima oleh customer ini
                for signal in self.active_signals:
                    signal_id = signal['signal_id']
                    
                    if signal_id not in received_signal_ids:
                        # Ini signal baru untuk customer
                        signal_copy = signal.copy()
                        signal_copy['is_new'] = True
                        signal_copy['age_seconds'] = current_time - signal['created_at']
                        signal_copy['expires_in'] = expiry_seconds - (current_time - signal['created_at'])
                        new_signals_for_customer.append(signal_copy)
                        
                        # Tandai sebagai sudah diterima
                        received_signal_ids.add(signal_id)
                        
                        # Log ke database jika enabled
                        if DB_ENABLED:
                            try:
                                database.mark_signal_sent(signal_id, customer_id)
                            except Exception as db_err:
                                self.log_warning(f"Database mark sent warning: {db_err}")
                
                # Log informasi
                if new_signals_for_customer:
                    self.log_info(f"🎯 Customer {customer_id} got {len(new_signals_for_customer)} NEW signals")
                    self.log_info(f"   Total received by this customer: {len(received_signal_ids)}")
            
            # Kirim response dengan session_id
            if new_signals_for_customer:
                response = {
                    'status': 'success',
                    'signal_available': True,
                    'new_signals_count': len(new_signals_for_customer),
                    'signals': new_signals_for_customer,
                    'customer_id': customer_id,
                    'total_active_signals': len(self.active_signals),
                    'server_time': datetime.now().isoformat(),
                    'session_id': session_id
                }
            else:
                response = {
                    'status': 'success',
                    'signal_available': False,
                    'message': 'No new signals available',
                    'customer_id': customer_id,
                    'total_active_signals': len(self.active_signals),
                    'total_received_signals': len(self.customer_received_signals.get(customer_id, set())),
                    'server_time': datetime.now().isoformat(),
                    'session_id': session_id
                }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error in _handle_customer_check_signal: {e}")
            traceback.print_exc()
            error_response = {
                'status': 'error',
                'message': f'Server processing error: {str(e)}',
                'customer_id': customer_id,
                'session_id': session_id
            }
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def _handle_customer_get_all_signals(self, client_socket, customer_id, session_id):
        """Handle customer getting all active signals"""
        try:
            with self.signal_lock:
                # Filter expired signals
                current_time = time.time()
                expiry_seconds = self.expiry_minutes * 60
                
                non_expired_signals = []
                for signal in self.active_signals:
                    signal_age = current_time - signal['created_at']
                    if signal_age <= expiry_seconds:
                        signal_copy = signal.copy()
                        signal_copy['age_seconds'] = signal_age
                        signal_copy['expires_in'] = expiry_seconds - signal_age
                        
                        # Cek apakah customer sudah menerima signal ini
                        if customer_id in self.customer_received_signals:
                            signal_copy['is_new'] = signal['signal_id'] not in self.customer_received_signals[customer_id]
                        else:
                            signal_copy['is_new'] = True
                        
                        non_expired_signals.append(signal_copy)
                
                # Update active signals
                self.active_signals = [s for s in self.active_signals if (current_time - s['created_at']) <= expiry_seconds]
            
            response = {
                'status': 'success',
                'active_signals_count': len(non_expired_signals),
                'signals': non_expired_signals,
                'customer_id': customer_id,
                'server_time': datetime.now().isoformat(),
                'session_id': session_id
            }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error in _handle_customer_get_all_signals: {e}")
            error_response = {
                'status': 'error',
                'message': f'Server error: {str(e)}',
                'customer_id': customer_id,
                'session_id': session_id
            }
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def get_system_stats(self, admin_id=None):
        """Get system statistics"""
        try:
            with self.signal_lock:
                stats = {
                    'server_status': 'running',
                    'server_time': datetime.now().isoformat(),
                    'uptime_seconds': int(time.time() - self.start_time),
                    'active_signals_count': len(self.active_signals),
                    'total_customers_served': len(self.customer_received_signals),
                    'max_active_signals': self.max_active_signals,
                    'signal_expiry_minutes': self.expiry_minutes,
                    'active_connections': self.active_connections,
                    'max_connections': self.max_connections,
                    'rate_limited_users': len(self.rate_limits),
                    'active_sessions': len(self.active_sessions),
                    'admin_activities_count': len(self.admin_activities)
                }
                
                # Hitung total deliveries
                total_deliveries = 0
                for customer_id, signals in self.customer_received_signals.items():
                    total_deliveries += len(signals)
                
                stats['total_signal_deliveries'] = total_deliveries
                
                # Info tentang active signals
                if self.active_signals:
                    stats['active_signals_info'] = []
                    for signal in self.active_signals[-5:]:  # 5 signal terakhir
                        signal_age = time.time() - signal['created_at']
                        stats['active_signals_info'].append({
                            'signal_id': signal['signal_id'],
                            'symbol': signal['symbol'],
                            'type': signal['type'],
                            'age_seconds': int(signal_age),
                            'expires_in': int((self.expiry_minutes * 60) - signal_age),
                            'admin_id': signal.get('admin_id', 'unknown')
                        })
                
                # Tambahkan admin-specific stats jika admin request
                if admin_id:
                    # Count signals sent by this admin
                    admin_signals = [s for s in self.active_signals if s.get('admin_id') == admin_id]
                    stats['your_signals_active'] = len(admin_signals)
                    
                    # Recent admin activities
                    admin_activities = [a for a in self.admin_activities if a.get('admin_id') == admin_id]
                    stats['your_recent_activities'] = admin_activities[-5:] if admin_activities else []
                
                # Tambahkan stats dari database jika ada
                if DB_ENABLED:
                    try:
                        db_stats = database.get_statistics()
                        stats['database_stats'] = db_stats
                    except Exception as db_err:
                        stats['database_stats'] = {'error': str(db_err), 'available': False}
                
                return stats
                
        except Exception as e:
            self.log_error(f"Error in get_system_stats: {e}")
            return {
                'server_status': 'error',
                'error': str(e),
                'server_time': datetime.now().isoformat()
            }
    
    def periodic_cleanup_with_db(self):
        """Periodic cleanup expired signals"""
        while self.running:
            time.sleep(60)  # Cek setiap 1 menit
            
            try:
                with self.signal_lock:
                    # Cleanup expired signals in memory
                    current_time = time.time()
                    expiry_seconds = self.expiry_minutes * 60
                    
                    # Hitung sebelum cleanup
                    before_count = len(self.active_signals)
                    
                    # Filter hanya signals yang belum expired
                    self.active_signals = [
                        signal for signal in self.active_signals 
                        if (current_time - signal['created_at']) <= expiry_seconds
                    ]
                    
                    # Log jika ada yang dihapus
                    after_count = len(self.active_signals)
                    if before_count > after_count:
                        self.log_info(f"🧹 Cleaned up {before_count - after_count} expired signals")
                
                # Cleanup expired signals in database
                if DB_ENABLED:
                    try:
                        expired_count = database.expire_old_signals()
                        if expired_count > 0:
                            self.log_info(f"🗑️ Database cleanup: Expired {expired_count} signals")
                    except Exception as db_err:
                        self.log_warning(f"Database cleanup warning: {db_err}")
            
            except Exception as e:
                self.log_error(f"Error in periodic cleanup: {e}")
                traceback.print_exc()
    
    def periodic_stats(self):
        """Periodically log statistics"""
        while self.running:
            time.sleep(300)  # Setiap 5 menit
            
            try:
                with self.signal_lock:
                    if self.active_signals:
                        self.log_info(f"📊 Active Signals Stats: {len(self.active_signals)} signals active")
                        
                        # Hitung deliveries per signal
                        signal_deliveries = {}
                        for customer_id, signals in self.customer_received_signals.items():
                            for signal_id in signals:
                                signal_deliveries[signal_id] = signal_deliveries.get(signal_id, 0) + 1
                        
                        # Log 3 signal terakhir
                        for signal in self.active_signals[-3:]:
                            deliveries = signal_deliveries.get(signal['signal_id'], 0)
                            signal_age = time.time() - signal['created_at']
                            self.log_info(f"   Signal {signal['signal_id']}: {signal['symbol']} {signal['type']}, "
                                        f"Age: {signal_age:.0f}s, Delivered to {deliveries} customers")
                    
                    # Log customer stats
                    total_customers = len(self.customer_received_signals)
                    if total_customers > 0:
                        total_deliveries = sum(len(s) for s in self.customer_received_signals.values())
                        avg_signals_per_customer = total_deliveries / total_customers
                        self.log_info(f"👥 Customer Stats: {total_customers} customers, "
                                    f"{total_deliveries} total deliveries, "
                                    f"{avg_signals_per_customer:.1f} signals/customer avg")
                    
                    # Log connection stats
                    self.log_info(f"🔗 Connection Stats: {self.active_connections}/{self.max_connections} active")
                    
                    # Log session stats
                    self.log_info(f"🔐 Session Stats: {len(self.active_sessions)} active sessions")
                    
                    # Log admin stats
                    if self.admin_activities:
                        self.log_info(f"🛠️  Admin Activities: {len(self.admin_activities)} total")
                            
            except Exception as e:
                self.log_error(f"Error in periodic stats: {e}")
    
    def stop(self):
        """Stop the server"""
        self.log_info("🛑 Stopping server...")
        self.running = False
        
        # Tutup socket
        try:
            self.server_socket.close()
        except:
            pass
        
        self.log_info("✅ Server stopped")

def signal_handler(sig, frame):
    """Handle Ctrl+C signal"""
    print("\n🛑 Received stop signal...")
    sys.exit(0)

def main():
    """Main function"""
    port = int(os.environ.get('PORT', 9999))
    
    print("=" * 60)
    print("        TRADING SIGNAL SERVER v4.0")
    print("          API KEY AUTHENTICATION")
    print("=" * 60)
    print("🔔 FEATURES:")
    print("  • API Key Authentication for ALL users")
    print("  • Session Management")
    print("  • Admin Activity Logging")
    print("  • Rate Limiting (Admins: 120/min, Customers: 60/min)")
    print("=" * 60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version}")
    print(f"🌐 Port: {port}")
    print(f"📊 Database: {'Enabled' if DB_ENABLED else 'Disabled (fallback mode)'}")
    print(f"🔒 Security: API Keys Required")
    print("=" * 60)
    print()
    
    # Setup handler untuk Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Buat dan jalankan server
    server = TradingSignalServer()
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        server.stop()

if __name__ == "__main__":
    main()