#!/usr/bin/env python3
"""
Trading Signal Server v4.2 - PRODUCTION READY
Production version tanpa data hardcoded
"""

import socket
import threading
import json
import time
from datetime import datetime
import sys
import os
import uuid
import traceback
import hashlib
from typing import Dict, List, Optional, Tuple

# Global flag untuk database
GLOBAL_DB_ENABLED = True

class UserStatus:
    """Status management untuk user"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    
    @staticmethod
    def is_valid(status: str) -> bool:
        return status in [UserStatus.ACTIVE, UserStatus.INACTIVE]

class APIManager:
    """Centralized API Key Management dengan status"""
    
    def __init__(self, server):
        self.server = server
        self.api_keys_file = 'api_keys_secure.json'
        self.user_status_file = 'user_status.json'
        self.api_keys = self.load_api_keys()
        self.user_status = self.load_user_status()
        
    def load_api_keys(self) -> Dict:
        """Load API keys from secure file"""
        try:
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r') as f:
                    keys = json.load(f)
                    self.server.log_info(f"Loaded API keys: {len(keys.get('admins', {}))} admins, {len(keys.get('customers', {}))} customers")
                    return keys
        except Exception as e:
            self.server.log_warning(f"Error loading API keys: {e}")
        
        # Create empty file for production
        empty_structure = {
            "admins": {},
            "customers": {}
        }
        
        try:
            with open(self.api_keys_file, 'w') as f:
                json.dump(empty_structure, f, indent=2)
            self.server.log_info("Created empty API keys file for production")
        except Exception as e:
            self.server.log_error(f"Failed to create API keys file: {e}")
        
        return empty_structure
    
    def load_user_status(self) -> Dict:
        """Load user status from file"""
        try:
            if os.path.exists(self.user_status_file):
                with open(self.user_status_file, 'r') as f:
                    status = json.load(f)
                    return status
        except Exception as e:
            self.server.log_warning(f"Error loading user status: {e}")
        
        # Create empty file for production
        empty_structure = {
            "admins": {},
            "customers": {}
        }
        
        try:
            with open(self.user_status_file, 'w') as f:
                json.dump(empty_structure, f, indent=2)
            self.server.log_info("Created empty user status file for production")
        except Exception as e:
            self.server.log_error(f"Failed to create user status file: {e}")
        
        return empty_structure
    
    def save_user_status(self) -> bool:
        """Save user status to file"""
        try:
            with open(self.user_status_file, 'w') as f:
                json.dump(self.user_status, f, indent=2)
            return True
        except Exception as e:
            self.server.log_error(f"Failed to save user status: {e}")
            return False
    
    def validate_api_key(self, user_type: str, user_id: str, api_key: str) -> bool:
        """Validate API key dengan cek status user"""
        if user_type not in ["admins", "customers"]:
            return False
        
        # Cek apakah user ada
        if user_id not in self.api_keys.get(user_type, {}):
            return False
        
        # Cek API key
        expected_key = self.api_keys[user_type][user_id]
        if api_key != expected_key:
            return False
        
        # Cek status user
        user_status_info = self.user_status.get(user_type, {}).get(user_id, {})
        if user_status_info.get('status') == UserStatus.INACTIVE:
            self.server.log_warning(f"User {user_type}/{user_id} is inactive")
            return False
        
        return True
    
    def add_api_key(self, user_type: str, user_id: str, api_key: str) -> bool:
        """Add new API key dengan status default active"""
        if user_type not in self.api_keys:
            self.api_keys[user_type] = {}
        
        # Add to keys
        self.api_keys[user_type][user_id] = api_key
        
        # Add to status dengan default active
        if user_type not in self.user_status:
            self.user_status[user_type] = {}
        
        self.user_status[user_type][user_id] = {
            "status": UserStatus.ACTIVE,
            "created": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
        
        # Save both files
        return self.save_api_keys() and self.save_user_status()
    
    def revoke_api_key(self, user_type: str, user_id: str) -> bool:
        """Revoke API key"""
        if user_type in self.api_keys and user_id in self.api_keys[user_type]:
            del self.api_keys[user_type][user_id]
            
            # Also remove from status
            if user_type in self.user_status and user_id in self.user_status[user_type]:
                del self.user_status[user_type][user_id]
            
            return self.save_api_keys() and self.save_user_status()
        return False
    
    def set_user_status(self, user_type: str, user_id: str, status: str) -> bool:
        """Set user status (active/inactive)"""
        if not UserStatus.is_valid(status):
            return False
        
        if user_type not in self.user_status:
            self.user_status[user_type] = {}
        
        if user_id not in self.user_status[user_type]:
            # Create new entry if doesn't exist
            self.user_status[user_type][user_id] = {
                "created": datetime.now().isoformat()
            }
        
        self.user_status[user_type][user_id].update({
            "status": status,
            "last_modified": datetime.now().isoformat()
        })
        
        return self.save_user_status()
    
    def get_user_status(self, user_type: str, user_id: str) -> Optional[str]:
        """Get user status"""
        return self.user_status.get(user_type, {}).get(user_id, {}).get('status', UserStatus.ACTIVE)
    
    def get_all_users_with_status(self) -> Dict:
        """Get all users with their status"""
        result = {
            "admins": {},
            "customers": {}
        }
        
        for user_type in ["admins", "customers"]:
            for user_id in self.api_keys.get(user_type, {}):
                status_info = self.user_status.get(user_type, {}).get(user_id, {})
                masked_key = self.mask_api_key(self.api_keys[user_type][user_id])
                
                result[user_type][user_id] = {
                    "api_key": masked_key,
                    "status": status_info.get('status', UserStatus.ACTIVE),
                    "created": status_info.get('created', datetime.now().isoformat()),
                    "last_modified": status_info.get('last_modified', None)
                }
        
        return result
    
    def save_api_keys(self) -> bool:
        """Save API keys to file"""
        try:
            with open(self.api_keys_file, 'w') as f:
                json.dump(self.api_keys, f, indent=2)
            return True
        except Exception as e:
            self.server.log_error(f"Failed to save API keys: {e}")
            return False
    
    def mask_api_key(self, api_key: str) -> str:
        """Mask API key for display"""
        if len(api_key) <= 12:
            return "***"
        return f"{api_key[:8]}...{api_key[-4:]}"
    
    def list_keys(self, mask: bool = True) -> Dict:
        """List API keys (with masking)"""
        keys_copy = {k: v.copy() for k, v in self.api_keys.items()}
        
        if mask:
            for user_type in keys_copy:
                for user_id in keys_copy[user_type]:
                    keys_copy[user_type][user_id] = self.mask_api_key(keys_copy[user_type][user_id])
        
        return keys_copy

class TradingSignalServer:
    def __init__(self, config_file='config.json'):
        self._setup_logging()
        self.config = self.load_config(config_file)
        
        # Server settings
        self.host = self.config.get('server', {}).get('host', '0.0.0.0')
        self.port = int(os.environ.get('PORT', self.config.get('server', {}).get('port', 9999)))
        
        # Initialize API Manager dengan status
        self.api_manager = APIManager(self)
        
        # Security settings
        security_config = self.config.get('security', {})
        self.customer_rate_limit = security_config.get('rate_limit_per_minute', 60)
        self.admin_rate_limit = security_config.get('admin_rate_limit', 120)
        self.max_connections = security_config.get('max_connections', 100)
        self.session_timeout = security_config.get('session_timeout_minutes', 30) * 60
        
        # Signal settings
        signal_settings = self.config.get('signal_settings', {})
        self.expiry_minutes = signal_settings.get('expiry_minutes', 5)
        self.max_active_signals = signal_settings.get('max_active_signals', 10)
        
        # Data storage
        self.active_signals = []
        self.signal_lock = threading.Lock()
        self.running = True
        
        # Database integration
        self.db_enabled = GLOBAL_DB_ENABLED
        if self.db_enabled:
            try:
                from database import database as db
                self.db = db
                self.db.log_system('INFO', 'server', 'Server starting', 
                                 {'version': '4.2', 'port': self.port})
                self.log_info("✅ Database initialized successfully")
            except Exception as e:
                self.log_error(f"❌ Database initialization failed: {e}")
                self.db_enabled = False
        else:
            self.log_warning("⚠️ Database disabled (GLOBAL_DB_ENABLED = False)")
        
        # Connection tracking
        self.active_connections = 0
        self.connection_lock = threading.Lock()
        
        # Rate limiting
        self.rate_limits = {}
        
        # Session management
        self.active_sessions = {}
        
        # Customer tracking
        self.customer_received_signals = {}
        
        # Admin activities
        self.admin_activities = []
        
        # Server socket
        self.server_socket = None
        
        # Uptime tracking
        self.start_time = time.time()
        
        # Database
        self.DB_ENABLED = GLOBAL_DB_ENABLED
        if self.DB_ENABLED:
            self.init_database()
        
        self.log_info("=" * 60)
        self.log_info("TRADING SIGNAL SERVER v4.2 - PRODUCTION READY")
        self.log_info("=" * 60)
        self.log_info(f"Server: {self.host}:{self.port}")
        self.log_info(f"Users: {self.count_users()} total users")
        self.log_info(f"Rate Limits: Admins={self.admin_rate_limit}/min, Customers={self.customer_rate_limit}/min")
        self.log_info(f"User Status: Active/Inactive tracking enabled")
        self.log_info("=" * 60)
    
    def count_users(self) -> int:
        """Count total users"""
        total = 0
        for user_type in ["admins", "customers"]:
            total += len(self.api_manager.api_keys.get(user_type, {}))
        return total
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration file"""
        default_config = {
            'server': {'host': '0.0.0.0', 'port': 9999},
            'security': {
                'rate_limit_per_minute': 60,
                'admin_rate_limit': 120,
                'max_connections': 100,
                'session_timeout_minutes': 30
            },
            'signal_settings': {
                'expiry_minutes': 5,
                'max_active_signals': 10,
                'check_interval_seconds': 60
            }
        }
        
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.log_warning(f"Config file {config_file} not found, using defaults")
            return default_config
        except json.JSONDecodeError as e:
            self.log_warning(f"Error parsing config: {e}, using defaults")
            return default_config
    
    def _setup_logging(self):
        """Setup logging"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] INFO: Logging initialized")
    
    def log_info(self, message: str):
        """Log info message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] INFO: {message}")
    
    def log_error(self, message: str):
        """Log error message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ERROR: {message}")
    
    def log_warning(self, message: str):
        """Log warning message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] WARNING: {message}")
    
    def authenticate_user(self, request: Dict) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Unified authentication dengan cek status user
        Returns: (success, user_type, user_id, session_id)
        """
        api_key = request.get('api_key', '')
        session_id = request.get('session_id', '')
        action = request.get('action', '')
        
        # 1. Check session first
        if session_id:
            valid, user_data = self.validate_session(session_id)
            if valid:
                user_id = user_data['user_id']
                user_type = user_data['user_type']
                self.active_sessions[session_id]['last_activity'] = time.time()
                self.log_info(f"Session validated for {user_type} {user_id}")
                return True, user_type, user_id, session_id
        
        # 2. Determine user type
        user_type = None
        user_id = None
        
        if 'admin_id' in request:
            user_type = 'admins'
            user_id = request['admin_id']
        elif 'customer_id' in request:
            user_type = 'customers'
            user_id = request['customer_id']
        else:
            self.log_warning("No user identifier found in request")
            return False, None, None, None
        
        # 3. Validate API key dan status
        if not api_key:
            self.log_warning(f"No API key provided for {user_type} {user_id}")
            return False, None, None, None
        
        if self.api_manager.validate_api_key(user_type, user_id, api_key):
            session_id = self.create_session(user_id, user_type)
            self.log_info(f"Authentication successful for {user_type} {user_id}")
            
            if user_type == 'admins' and action:
                self.log_admin_activity(user_id, "login", f"Action: {action}")
            
            return True, user_type, user_id, session_id
        
        self.log_warning(f"Authentication failed for {user_type} {user_id}")
        return False, None, None, None
    
    def create_session(self, user_id: str, user_type: str) -> str:
        """Create new session"""
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'user_type': user_type,
            'login_time': time.time(),
            'last_activity': time.time()
        }
        return session_id
    
    def validate_session(self, session_id: str) -> Tuple[bool, Optional[Dict]]:
        """Validate session"""
        if session_id not in self.active_sessions:
            return False, None
        
        session = self.active_sessions[session_id]
        current_time = time.time()
        
        if current_time - session['last_activity'] > self.session_timeout:
            del self.active_sessions[session_id]
            return False, None
        
        session['last_activity'] = current_time
        return True, session
    
    def check_rate_limit(self, user_id: str, user_type: str) -> bool:
        """Check rate limit"""
        max_requests = self.admin_rate_limit if user_type == 'admins' else self.customer_rate_limit
        
        now = time.time()
        one_minute_ago = now - 60
        
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = []
        
        self.rate_limits[user_id] = [t for t in self.rate_limits[user_id] if t > one_minute_ago]
        
        if len(self.rate_limits[user_id]) >= max_requests:
            return False
        
        self.rate_limits[user_id].append(now)
        return True
    
    def handle_client(self, client_socket, address):
        """Handle client connection"""
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
            
            request = json.loads(data)
            
            # Authentication
            auth_success, user_type, user_id, session_id = self.authenticate_user(request)
            
            if not auth_success:
                response = {
                    'status': 'error',
                    'message': 'Authentication failed. Check your API Key or user status.',
                    'code': 'AUTH_FAILED'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            # Rate limiting
            if not self.check_rate_limit(user_id, user_type):
                response = {
                    'status': 'error',
                    'message': f'Rate limit exceeded. Max {self.admin_rate_limit if user_type == "admins" else self.customer_rate_limit} requests per minute.',
                    'code': 'RATE_LIMIT'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            response_base = {'session_id': session_id}
            
            # Route to appropriate handler
            if user_type == 'admins':
                self.handle_admin_request(client_socket, request, user_id, session_id, response_base)
            elif user_type == 'customers':
                self.handle_customer_request(client_socket, request, user_id, session_id, response_base)
            else:
                response = {
                    'status': 'error',
                    'message': 'Invalid user type',
                    'code': 'INVALID_USER_TYPE'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except json.JSONDecodeError:
            error_response = {'status': 'error', 'message': 'Invalid JSON format', 'code': 'INVALID_JSON'}
            client_socket.send(json.dumps(error_response).encode('utf-8'))
        except Exception as e:
            self.log_error(f"Error handling client: {e}")
            error_response = {'status': 'error', 'message': 'Internal server error', 'code': 'SERVER_ERROR'}
            client_socket.send(json.dumps(error_response).encode('utf-8'))
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def handle_admin_request(self, client_socket, request, admin_id, session_id, response_base):
        """Handle admin requests termasuk user management"""
        action = request.get('action', '')
        
        if action == 'send_signal':
            self.handle_send_signal(client_socket, request, admin_id, session_id, response_base)
        elif action == 'get_stats':
            self.handle_get_stats(client_socket, admin_id, session_id, response_base)
        elif action == 'list_api_keys':
            self.handle_list_keys(client_socket, admin_id, session_id, response_base)
        elif action == 'list_users_with_status':
            self.handle_list_users_with_status(client_socket, admin_id, session_id, response_base)
        elif action == 'add_api_key':
            self.handle_add_key(client_socket, request, admin_id, session_id, response_base)
        elif action == 'set_user_status':
            self.handle_set_user_status(client_socket, request, admin_id, session_id, response_base)
        elif action == 'revoke_api_key':
            self.handle_revoke_key(client_socket, request, admin_id, session_id, response_base)
        else:
            response = {
                'status': 'error',
                'message': f'Unknown action: {action}',
                'code': 'UNKNOWN_ACTION'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_customer_request(self, client_socket, request, customer_id, session_id, response_base):
        """Handle customer requests"""
        action = request.get('action', 'check_signal')
        
        if action == 'check_signal':
            self.handle_check_signal(client_socket, customer_id, session_id, response_base)
        elif action == 'get_all_signals':
            self.handle_get_all_signals(client_socket, customer_id, session_id, response_base)
        else:
            response = {
                'status': 'error',
                'message': f'Unknown action: {action}',
                'code': 'UNKNOWN_ACTION'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_list_users_with_status(self, client_socket, admin_id, session_id, response_base):
        """List all users with their status"""
        try:
            users_with_status = self.api_manager.get_all_users_with_status()
            
            response = {
                'status': 'success',
                'users': users_with_status,
                'total_admins': len(users_with_status.get('admins', {})),
                'total_customers': len(users_with_status.get('customers', {})),
                'admin_id': admin_id
            }
            response.update(response_base)
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error listing users with status: {e}")
            response = {
                'status': 'error',
                'message': f'Error listing users: {str(e)}',
                'code': 'LIST_USERS_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_set_user_status(self, client_socket, request, admin_id, session_id, response_base):
        """Set user status (active/inactive)"""
        try:
            user_type = request.get('user_type', '').lower()
            user_id = request.get('user_id', '')
            status = request.get('status', '').lower()
            
            if not user_type or user_type not in ['admins', 'customers']:
                response = {
                    'status': 'error',
                    'message': 'user_type must be "admins" or "customers"',
                    'code': 'INVALID_USER_TYPE'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            if not user_id:
                response = {
                    'status': 'error',
                    'message': 'user_id is required',
                    'code': 'MISSING_FIELD'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            if not UserStatus.is_valid(status):
                response = {
                    'status': 'error',
                    'message': 'status must be "active" or "inactive"',
                    'code': 'INVALID_STATUS'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            # Cek apakah user ada
            if user_id not in self.api_manager.api_keys.get(user_type, {}):
                response = {
                    'status': 'error',
                    'message': f'User {user_id} not found in {user_type}',
                    'code': 'USER_NOT_FOUND'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            success = self.api_manager.set_user_status(user_type, user_id, status)
            
            if success:
                response = {
                    'status': 'success',
                    'message': f'User {user_type}/{user_id} status changed to {status}',
                    'user_type': user_type,
                    'user_id': user_id,
                    'status': status,
                    'admin_id': admin_id
                }
                self.log_admin_activity(admin_id, "set_user_status", 
                                      f"Changed {user_type}/{user_id} to {status}")
            else:
                response = {
                    'status': 'error',
                    'message': 'Failed to change user status',
                    'code': 'STATUS_CHANGE_ERROR'
                }
            
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error setting user status: {e}")
            response = {
                'status': 'error',
                'message': f'Error setting user status: {str(e)}',
                'code': 'STATUS_CHANGE_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_send_signal(self, client_socket, request, admin_id, session_id, response_base):
        """Handle sending new signal"""
        try:
            required_fields = ['symbol', 'price', 'sl', 'tp', 'type']
            for field in required_fields:
                if field not in request:
                    response = {
                        'status': 'error',
                        'message': f'Missing required field: {field}',
                        'code': 'MISSING_FIELD'
                    }
                    response.update(response_base)
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    return
            
            signal_type = request['type'].lower()
            if signal_type not in ['buy', 'sell']:
                response = {
                    'status': 'error',
                    'message': 'Signal type must be "buy" or "sell"',
                    'code': 'INVALID_TYPE'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            try:
                price = float(request['price'])
                sl = float(request['sl'])
                tp = float(request['tp'])
            except ValueError:
                response = {
                    'status': 'error',
                    'message': 'Price, SL, and TP must be numbers',
                    'code': 'INVALID_NUMBER'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            with self.signal_lock:
                signal_id = f"SIG_{int(time.time())}_{len(self.active_signals)}"
                
                signal_data = {
                    'signal_id': signal_id,
                    'symbol': request['symbol'],
                    'price': price,
                    'sl': sl,
                    'tp': tp,
                    'type': signal_type,
                    'timestamp': datetime.now().isoformat(),
                    'created_at': time.time(),
                    'admin_id': admin_id,
                    'expires_at': time.time() + (self.expiry_minutes * 60)
                }
                
                self.active_signals.append(signal_data)
                
                # ✅ SIMPAN KE DATABASE
                if self.db_enabled:
                    try:
                        success = self.db.add_signal(
                            symbol=request['symbol'],
                            price=price,
                            sl=sl,
                            tp=tp,
                            signal_type=signal_type,
                            admin_address=client_socket.getpeername()[0] if hasattr(client_socket, 'getpeername') else 'unknown',
                            admin_id=admin_id,
                            expiry_minutes=self.expiry_minutes
                        )
                        if success:
                            self.log_info(f"Signal {signal_id} saved to database")
                            self.db.log_admin_activity(
                                admin_id=admin_id,
                                action="send_signal",
                                details=f"{request['symbol']} {signal_type} at {price}",
                                ip_address=client_socket.getpeername()[0] if hasattr(client_socket, 'getpeername') else ''
                            )
                    except Exception as e:
                        self.log_error(f"Failed to save signal to database: {e}")
                
                if len(self.active_signals) > self.max_active_signals:
                    removed = self.active_signals.pop(0)
                    self.log_info(f"Removed old signal: {removed['signal_id']}")
                
                self.log_info(f"New signal {signal_id} from admin {admin_id}: {request['symbol']} {signal_type}")
                
                response = {
                    'status': 'success',
                    'message': 'Signal created successfully',
                    'signal': {
                        'signal_id': signal_id,
                        'symbol': request['symbol'],
                        'type': signal_type,
                        'price': price,
                        'sl': sl,
                        'tp': tp,
                        'timestamp': signal_data['timestamp'],
                        'expires_in': self.expiry_minutes * 60
                    },
                    'total_active_signals': len(self.active_signals)
                }
                response.update(response_base)
                
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            self.log_error(f"Error in send_signal: {e}")
            response = {
                'status': 'error',
                'message': f'Error creating signal: {str(e)}',
                'code': 'SIGNAL_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_check_signal(self, client_socket, customer_id, session_id, response_base):
        """Handle customer checking for signals"""
        try:
            with self.signal_lock:
                current_time = time.time()
                expiry_seconds = self.expiry_minutes * 60
                
                valid_signals = []
                for signal in self.active_signals:
                    if current_time - signal['created_at'] <= expiry_seconds:
                        valid_signals.append(signal)
                
                self.active_signals = valid_signals
                
                if customer_id not in self.customer_received_signals:
                    self.customer_received_signals[customer_id] = set()
                
                received_signal_ids = self.customer_received_signals[customer_id]
                
                signals_for_customer = []
                new_signals_count = 0
                
                for signal in self.active_signals:
                    signal_id = signal['signal_id']
                    
                    signal_info = {
                        'signal_id': signal_id,
                        'symbol': signal['symbol'],
                        'price': signal['price'],
                        'sl': signal['sl'],
                        'tp': signal['tp'],
                        'type': signal['type'],
                        'timestamp': signal['timestamp'],
                        'admin_id': signal.get('admin_id', 'unknown'),
                        'age_seconds': round(current_time - signal['created_at'], 1),
                        'expires_in': round(expiry_seconds - (current_time - signal['created_at']), 1),
                        'is_new': False
                    }
                    
                    if signal_id not in received_signal_ids:
                        signal_info['is_new'] = True
                        new_signals_count += 1
                        received_signal_ids.add(signal_id)
                    
                    signals_for_customer.append(signal_info)
                
                if signals_for_customer:
                    response = {
                        'status': 'success',
                        'signal_available': True,
                        'total_signals': len(signals_for_customer),
                        'new_signals': new_signals_count,
                        'signals': signals_for_customer,
                        'customer_id': customer_id
                    }
                else:
                    response = {
                        'status': 'success',
                        'signal_available': False,
                        'message': 'No active signals available',
                        'customer_id': customer_id
                    }
                
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            self.log_error(f"Error in check_signal: {e}")
            response = {
                'status': 'error',
                'message': f'Error checking signals: {str(e)}',
                'code': 'CHECK_SIGNAL_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_list_keys(self, client_socket, admin_id, session_id, response_base):
        """List API keys (masked)"""
        try:
            keys = self.api_manager.list_keys(mask=True)
            
            response = {
                'status': 'success',
                'api_keys': keys,
                'total_admins': len(keys.get('admins', {})),
                'total_customers': len(keys.get('customers', {})),
                'admin_id': admin_id
            }
            response.update(response_base)
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error listing keys: {e}")
            response = {
                'status': 'error',
                'message': f'Error listing API keys: {str(e)}',
                'code': 'LIST_KEYS_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_add_key(self, client_socket, request, admin_id, session_id, response_base):
        """Add new API key"""
        try:
            user_type = request.get('user_type', '').lower()
            user_id = request.get('user_id', '')
            api_key = request.get('api_key', '')
            
            if not user_type or user_type not in ['admins', 'customers']:
                response = {
                    'status': 'error',
                    'message': 'user_type must be "admins" or "customers"',
                    'code': 'INVALID_USER_TYPE'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            if not user_id or not api_key:
                response = {
                    'status': 'error',
                    'message': 'user_id and api_key are required',
                    'code': 'MISSING_FIELDS'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            success = self.api_manager.add_api_key(user_type, user_id, api_key)
            
            if success:
                response = {
                    'status': 'success',
                    'message': f'API key added for {user_type} {user_id}',
                    'user_type': user_type,
                    'user_id': user_id,
                    'admin_id': admin_id
                }
                self.log_admin_activity(admin_id, "add_api_key", f"Added key for {user_type}/{user_id}")
            else:
                response = {
                    'status': 'error',
                    'message': 'Failed to add API key',
                    'code': 'ADD_KEY_ERROR'
                }
            
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error adding key: {e}")
            response = {
                'status': 'error',
                'message': f'Error adding API key: {str(e)}',
                'code': 'ADD_KEY_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_revoke_key(self, client_socket, request, admin_id, session_id, response_base):
        """Revoke API key"""
        try:
            user_type = request.get('user_type', '').lower()
            user_id = request.get('user_id', '')
            
            if not user_type or user_type not in ['admins', 'customers']:
                response = {
                    'status': 'error',
                    'message': 'user_type must be "admins" or "customers"',
                    'code': 'INVALID_USER_TYPE'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            if not user_id:
                response = {
                    'status': 'error',
                    'message': 'user_id is required',
                    'code': 'MISSING_FIELD'
                }
                response.update(response_base)
                client_socket.send(json.dumps(response).encode('utf-8'))
                return
            
            success = self.api_manager.revoke_api_key(user_type, user_id)
            
            if success:
                response = {
                    'status': 'success',
                    'message': f'API key revoked for {user_type} {user_id}',
                    'user_type': user_type,
                    'user_id': user_id,
                    'admin_id': admin_id
                }
                self.log_admin_activity(admin_id, "revoke_api_key", f"Revoked key for {user_type}/{user_id}")
            else:
                response = {
                    'status': 'error',
                    'message': 'Key not found or already revoked',
                    'code': 'KEY_NOT_FOUND'
                }
            
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error revoking key: {e}")
            response = {
                'status': 'error',
                'message': f'Error revoking API key: {str(e)}',
                'code': 'REVOKE_KEY_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_get_stats(self, client_socket, admin_id, session_id, response_base):
        """Get system statistics"""
        try:
            stats = {
                'server_status': 'running',
                'uptime_seconds': int(time.time() - self.start_time),
                'active_signals': len(self.active_signals),
                'total_customers': len(self.customer_received_signals),
                'active_connections': self.active_connections,
                'max_connections': self.max_connections,
                'rate_limited_users': len(self.rate_limits),
                'active_sessions': len(self.active_sessions),
                'admin_activities': len(self.admin_activities),
                'timestamp': datetime.now().isoformat(),
                'admin_id': admin_id
            }
            
            response = {
                'status': 'success',
                'stats': stats
            }
            response.update(response_base)
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.log_error(f"Error getting stats: {e}")
            response = {
                'status': 'error',
                'message': f'Error getting statistics: {str(e)}',
                'code': 'STATS_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def handle_get_all_signals(self, client_socket, customer_id, session_id, response_base):
        """Get all active signals for customer"""
        try:
            with self.signal_lock:
                current_time = time.time()
                expiry_seconds = self.expiry_minutes * 60
                
                active_signals = []
                for signal in self.active_signals:
                    if current_time - signal['created_at'] <= expiry_seconds:
                        signal_info = signal.copy()
                        signal_info['age_seconds'] = round(current_time - signal['created_at'], 1)
                        signal_info['expires_in'] = round(expiry_seconds - (current_time - signal['created_at']), 1)
                        active_signals.append(signal_info)
                
                response = {
                    'status': 'success',
                    'active_signals': active_signals,
                    'total_signals': len(active_signals),
                    'customer_id': customer_id
                }
                response.update(response_base)
                
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            self.log_error(f"Error getting all signals: {e}")
            response = {
                'status': 'error',
                'message': f'Error getting signals: {str(e)}',
                'code': 'GET_SIGNALS_ERROR'
            }
            response.update(response_base)
            client_socket.send(json.dumps(response).encode('utf-8'))
    
    def log_admin_activity(self, admin_id, action, details=""):
        """Log admin activity"""
        activity = {
            'admin_id': admin_id,
            'action': action,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.admin_activities.append(activity)
        
        if len(self.admin_activities) > 100:
            self.admin_activities = self.admin_activities[-100:]
    
    def init_database(self):
        """Initialize database"""
        if self.DB_ENABLED:
            try:
                from database import database
                self.log_info("Database initialized")
            except Exception as e:
                self.log_warning(f"Database initialization warning: {e}")
    
    def start(self):
        """Start the server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.log_info(f"✅ Server running at {self.host}:{self.port}")
            self.log_info("Ready for connections...")
            
            accept_thread = threading.Thread(target=self.accept_connections, name="AcceptThread")
            accept_thread.daemon = True
            accept_thread.start()
            
            cleanup_thread = threading.Thread(target=self.periodic_cleanup, name="CleanupThread")
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            while self.running:
                time.sleep(1)
                
        except OSError as e:
            if "Address already in use" in str(e):
                self.log_error(f"❌ Port {self.port} already in use!")
            else:
                self.log_error(f"❌ Failed to start server: {e}")
        except Exception as e:
            self.log_error(f"❌ Server error: {e}")
            traceback.print_exc()
        finally:
            self.stop()
    
    def accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                
                with self.connection_lock:
                    if self.active_connections >= self.max_connections:
                        self.log_warning(f"Connection limit reached, rejecting {address}")
                        error_response = {'status': 'error', 'message': 'Server busy, too many connections'}
                        try:
                            client_socket.send(json.dumps(error_response).encode('utf-8'))
                        except:
                            pass
                        client_socket.close()
                        continue
                    
                    self.active_connections += 1
                
                self.log_info(f"New connection from {address} (Active: {self.active_connections}/{self.max_connections})")
                
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.log_error(f"Error accepting connection: {e}")
    
    def periodic_cleanup(self):
        """Periodic cleanup tasks"""
        while self.running:
            time.sleep(60)
            
            try:
                with self.signal_lock:
                    current_time = time.time()
                    expiry_seconds = self.expiry_minutes * 60
                    
                    before = len(self.active_signals)
                    self.active_signals = [
                        s for s in self.active_signals 
                        if current_time - s['created_at'] <= expiry_seconds
                    ]
                    after = len(self.active_signals)
                    
                    if before > after:
                        self.log_info(f"Cleaned up {before - after} expired signals")
                
                current_time = time.time()
                expired_sessions = []
                
                for session_id, session in self.active_sessions.items():
                    if current_time - session['last_activity'] > self.session_timeout:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    del self.active_sessions[session_id]
                
                if expired_sessions:
                    self.log_info(f"Cleaned up {len(expired_sessions)} expired sessions")
                    
            except Exception as e:
                self.log_error(f"Error in periodic cleanup: {e}")
    
    def stop(self):
        """Stop the server"""
        self.log_info("Stopping server...")
        self.running = False
        
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        
        self.log_info("Server stopped")

def main():
    """Main function"""
    print("=" * 60)
    print("   TRADING SIGNAL SERVER v4.2 - PRODUCTION READY")
    print("=" * 60)
    print("Features:")
    print("  • User status management (active/inactive)")
    print("  • Web admin panel for user management")
    print("  • API endpoints for user status control")
    print("  • Enhanced security with user deactivation")
    print("  • Session management with timeout")
    print("  • Rate limiting per user type")
    print("  • No hardcoded data - production ready")
    print("=" * 60)
    
    server = TradingSignalServer()
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nServer error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()