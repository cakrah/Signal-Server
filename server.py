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
                'credentials': {
                    'admin_password': 'admin123',
                    'customer_password': 'cust123'
                },
                'signal_settings': {
                    'expiry_minutes': 5,
                    'max_active_signals': 10,
                    'check_interval_seconds': 60
                }
            }
            print("⚠️ config.json not found, using default config")
        
        # === PERBAIKAN UNTUK CLOUD DEPLOYMENT ===
        # Gunakan port dari environment variable jika ada
        self.host = self.config['server']['host']
        self.port = int(os.environ.get('PORT', self.config['server']['port']))
        
        # Gunakan password dari environment variable jika ada
        self.admin_password = os.environ.get('ADMIN_PASSWORD', self.config['credentials']['admin_password'])
        self.customer_password = os.environ.get('CUSTOMER_PASSWORD', self.config['credentials']['customer_password'])
        # ========================================
        
        # === SECURITY IMPROVEMENTS ===
        # Load API Keys untuk customer authentication
        self.customer_api_keys = self.load_api_keys()
        
        # Rate limiting
        self.rate_limits = {}  # customer_id: [timestamps]
        self.max_requests_per_minute = 60
        
        # Connection tracking
        self.active_connections = 0
        self.max_connections = 100
        self.connection_lock = threading.Lock()
        # =============================
        
        self.expiry_minutes = self.config['signal_settings']['expiry_minutes']
        self.max_active_signals = self.config['signal_settings'].get('max_active_signals', 10)
        
        # Data storage
        self.active_signals = []  # List of active signals
        self.signal_lock = threading.Lock()
        self.running = True
        
        # Tracking signal deliveries per customer
        self.customer_received_signals = {}
        
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
        self.log_info(f"Max active signals: {self.max_active_signals}")
        self.log_info(f"Loaded {len(self.customer_api_keys)} customer API keys")
    
    def load_api_keys(self):
        """Load API keys from file or use defaults"""
        api_keys_file = 'api_keys.json'
        
        try:
            if os.path.exists(api_keys_file):
                with open(api_keys_file, 'r') as f:
                    api_keys = json.load(f)
                    self.log_info(f"Loaded {len(api_keys)} API keys from {api_keys_file}")
                    return api_keys
        except Exception as e:
            self.log_warning(f"Error loading API keys: {e}")
        
        # Default API keys (untuk testing/fallback)
        default_keys = {
            "CUST_001": "sk_live_abc123def456",
            "CUST_002": "sk_live_xyz789uvw012",
            "CUST_003": "sk_live_mno345pqr678",
            "CUST_004": "sk_live_jkl234mno567",
            "CUST_005": "sk_live_efg890hij123"
        }
        
        self.log_warning(f"Using default API keys. Create {api_keys_file} for production.")
        return default_keys
    
    def check_rate_limit(self, customer_id):
        """Check if customer has exceeded rate limit"""
        now = time.time()
        one_minute_ago = now - 60
        
        # Initialize if not exists
        if customer_id not in self.rate_limits:
            self.rate_limits[customer_id] = []
        
        # Remove old requests
        self.rate_limits[customer_id] = [
            t for t in self.rate_limits[customer_id] 
            if t > one_minute_ago
        ]
        
        # Check limit
        if len(self.rate_limits[customer_id]) >= self.max_requests_per_minute:
            return False
        
        # Add current request
        self.rate_limits[customer_id].append(now)
        return True
    
    def authenticate(self, request, client_type):
        """
        Authenticate client with multiple methods:
        1. Legacy: password field
        2. API Key: api_key field
        3. Customer ID + API Key
        """
        password = request.get('password', '')
        api_key = request.get('api_key', '')
        customer_id = request.get('customer_id', '')
        
        if client_type == 'admin':
            # Admin hanya pakai password
            return password == self.admin_password
        
        elif client_type == 'customer':
            # Method 1: Legacy password (backward compatibility)
            if password and password == self.customer_password:
                self.log_info(f"Customer authenticated via legacy password: {customer_id}")
                return True
            
            # Method 2: API Key authentication
            if api_key:
                # Check if API key exists
                for cust_id, key in self.customer_api_keys.items():
                    if api_key == key:
                        # Jika customer_id disediakan, harus match
                        if customer_id and customer_id != cust_id:
                            continue
                        self.log_info(f"Customer authenticated via API key: {cust_id}")
                        return True
            
            # Method 3: Customer ID + API Key validation
            if customer_id and api_key:
                expected_key = self.customer_api_keys.get(customer_id)
                if expected_key and api_key == expected_key:
                    self.log_info(f"Customer authenticated via customer_id+api_key: {customer_id}")
                    return True
            
            self.log_warning(f"Authentication failed for customer: {customer_id}")
            return False
        
        return False
    
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
            self.log_info(f"🔒 Security: API Key authentication enabled")
            self.log_info(f"⚡ Rate limit: {self.max_requests_per_minute} requests/minute")
            
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
                
                for customer_id in list(self.rate_limits.keys()):
                    # Hapus entries yang lebih dari 5 menit
                    self.rate_limits[customer_id] = [
                        t for t in self.rate_limits[customer_id] 
                        if t > five_minutes_ago
                    ]
                    
                    # Jika kosong, hapus key
                    if not self.rate_limits[customer_id]:
                        del self.rate_limits[customer_id]
                
                self.log_info(f"🧹 Rate limits cleanup: {len(self.rate_limits)} active customers")
                
            except Exception as e:
                self.log_error(f"Error in rate limit cleanup: {e}")
    
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
                
                # Log ke database - dengan error handling
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
            
            # === RATE LIMITING ===
            customer_id = request.get('customer_id', f"IP_{address[0]}")
            if not self.check_rate_limit(customer_id):
                response = {
                    'status': 'error', 
                    'message': f'Rate limit exceeded. Maximum {self.max_requests_per_minute} requests per minute.'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                client_socket.close()
                self.log_warning(f"Rate limit exceeded for {customer_id}")
                return
            
            # Authentikasi
            client_type = request.get('client_type', 'customer')
            if not self.authenticate(request, client_type):
                response = {'status': 'error', 'message': 'Authentication failed'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                client_socket.close()
                self.log_warning(f"Authentication failed from {address}")
                return
            
            # Identifikasi tipe client
            client_type = request.get('client_type', 'customer')
            
            # Log ke database - UPDATE client_type yang benar
            if DB_ENABLED:
                try:
                    database.add_client_connection(client_type, str(address))
                except Exception as db_err:
                    self.log_warning(f"Database update warning: {db_err}")
            
            if client_type == 'admin':
                self.handle_admin(client_socket, request, address)
            elif client_type == 'customer':
                self.handle_customer(client_socket, request, address)
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
    
    def handle_admin(self, client_socket, request, address):
        """Handle admin client"""
        try:
            if request.get('action') == 'send_signal':
                # Validasi data signal dengan TP
                required_fields = ['symbol', 'price', 'sl', 'tp', 'type']
                for field in required_fields:
                    if field not in request:
                        response = {'status': 'error', 'message': f'Missing field: {field}'}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                
                # Validasi type
                signal_type = request['type'].lower()
                if signal_type not in ['buy', 'sell']:
                    response = {'status': 'error', 'message': 'Type must be "buy" or "sell"'}
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    return
                
                # Validasi TP berdasarkan type
                try:
                    price = float(request['price'])
                    sl = float(request['sl'])
                    tp = float(request['tp'])
                except ValueError:
                    response = {'status': 'error', 'message': 'Price, SL, and TP must be numbers'}
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    return
                
                if signal_type == 'buy':
                    if tp <= price:
                        response = {'status': 'error', 'message': 'TP must be greater than entry price for BUY'}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                    if sl >= price:
                        response = {'status': 'error', 'message': 'SL must be less than entry price for BUY'}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                else:  # sell
                    if tp >= price:
                        response = {'status': 'error', 'message': 'TP must be less than entry price for SELL'}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        return
                    if sl <= price:
                        response = {'status': 'error', 'message': 'SL must be greater than entry price for SELL'}
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
                        'admin_address': str(address)
                    }
                    
                    # Tambahkan ke active signals
                    self.active_signals.append(new_signal)
                    
                    # Batasi jumlah active signals
                    if len(self.active_signals) > self.max_active_signals:
                        # Hapus yang paling tua
                        removed = self.active_signals.pop(0)
                        self.log_info(f"🧹 Removed old signal: {removed['signal_id']}")
                    
                    self.log_info(f"📡 New Signal #{signal_id} received from admin {address}")
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
                        'total_active_signals': len(self.active_signals)
                    }
                    
                    client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif request.get('action') == 'get_history':
                # Kirim history dari database
                if DB_ENABLED:
                    try:
                        history = database.get_signal_history(limit=50)
                        response = {
                            'status': 'success',
                            'history': history
                        }
                    except Exception as db_err:
                        response = {
                            'status': 'error',
                            'message': f'Database error: {db_err}'
                        }
                else:
                    response = {
                        'status': 'error',
                        'message': 'Database not available'
                    }
                client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif request.get('action') == 'get_stats':
                # Kirim statistik
                try:
                    stats = self.get_system_stats()
                    response = {
                        'status': 'success',
                        'stats': stats
                    }
                except Exception as e:
                    response = {
                        'status': 'error',
                        'message': f'Error getting stats: {e}'
                    }
                client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif request.get('action') == 'get_health':
                # Health check endpoint
                health_stats = self.get_health_status()
                response = {
                    'status': 'success',
                    'health': health_stats
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                
            else:
                response = {'status': 'error', 'message': 'Invalid action'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except KeyError as e:
            response = {'status': 'error', 'message': f'Field {e} not found'}
            client_socket.send(json.dumps(response).encode('utf-8'))
            self.log_error(f"Key error in admin request: {e}")
        except ValueError as e:
            response = {'status': 'error', 'message': f'Invalid value: {e}'}
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
            'rate_limited_customers': len(self.rate_limits),
            'timestamp': datetime.now().isoformat()
        }
    
    def handle_customer(self, client_socket, request, address):
        """Handle customer client - Customer dapat SETIAP active signal SEKALI"""
        try:
            action = request.get('action', 'check_signal')
            customer_id = request.get('customer_id', f"CUST_{address[0]}_{address[1]}")
            
            if action == 'check_signal':
                self._handle_customer_check_signal(client_socket, customer_id, address)
            elif action == 'get_all_signals':
                self._handle_customer_get_all_signals(client_socket, customer_id)
            else:
                self._handle_customer_check_signal(client_socket, customer_id, address)
                
        except Exception as e:
            self.log_error(f"Error in handle_customer: {e}")
            traceback.print_exc()
            error_response = {
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def _handle_customer_check_signal(self, client_socket, customer_id, address):
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
            
            # Kirim response
            if new_signals_for_customer:
                response = {
                    'status': 'success',
                    'signal_available': True,
                    'new_signals_count': len(new_signals_for_customer),
                    'signals': new_signals_for_customer,
                    'customer_id': customer_id,
                    'total_active_signals': len(self.active_signals),
                    'server_time': datetime.now().isoformat()
                }
            else:
                response = {
                    'status': 'success',
                    'signal_available': False,
                    'message': 'No new signals available',
                    'customer_id': customer_id,
                    'total_active_signals': len(self.active_signals),
                    'total_received_signals': len(self.customer_received_signals.get(customer_id, set())),
                    'server_time': datetime.now().isoformat()
                }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error in _handle_customer_check_signal: {e}")
            traceback.print_exc()
            error_response = {
                'status': 'error',
                'message': f'Server processing error: {str(e)}'
            }
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def _handle_customer_get_all_signals(self, client_socket, customer_id):
        """Handle customer getting all active signals (including already received)"""
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
                'server_time': datetime.now().isoformat()
            }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error in _handle_customer_get_all_signals: {e}")
            error_response = {
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def get_system_stats(self):
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
                    'rate_limited_customers': len(self.rate_limits)
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
                            'expires_in': int((self.expiry_minutes * 60) - signal_age)
                        })
                
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
                    
                    # Log rate limiting stats
                    if self.rate_limits:
                        self.log_info(f"⚡ Rate Limits: {len(self.rate_limits)} customers being tracked")
                            
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
    # === PERBAIKAN: Dapatkan port dari environment ===
    port = int(os.environ.get('PORT', 9999))
    
    print("=" * 60)
    print("        TRADING SIGNAL SERVER v3.0 - MULTI-SIGNAL")
    print("                  WITH API KEY SECURITY")
    print("=" * 60)
    print("🔔 FEATURE: Each customer gets EACH active signal ONCE")
    print("🔒 SECURITY: API Key authentication + Rate limiting")
    print("=" * 60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version}")
    print(f"🌐 Port: {port}")
    print(f"📊 Database: {'Enabled' if DB_ENABLED else 'Disabled (fallback mode)'}")
    print(f"👥 Max Connections: 100")
    print(f"⚡ Rate Limit: 60 requests/minute")
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