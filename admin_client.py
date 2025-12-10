#!/usr/bin/env python3
"""
Admin Trading Client v3.0 - WITH API KEY AUTHENTICATION
Full API Key support for secure admin authentication
"""

import socket
import json
import time
from datetime import datetime
import os
import sys

class AdminClient:
    def __init__(self, server_host='localhost', server_port=9999):
        """
        Initialize Admin Client with API Key support
        """
        self.server_host = server_host
        self.server_port = server_port
        
        # Load configuration
        self.config = self.load_config()
        
        # Authentication
        self.use_api_key = self.config.get('use_api_key', True)
        self.api_key = self.config.get('api_key', '')
        self.admin_id = self.config.get('admin_id', 'ADMIN_001')
        self.password = self.config.get('password', 'admin123')  # Legacy fallback
        
        # Session management
        self.session_id = None
        self.last_activity = None
        
        print(f"🛠️  Admin ID: {self.admin_id}")
        print(f"🔐 Auth Method: {'API Key' if self.use_api_key else 'Password (Legacy)'}")
        print(f"🌐 Server: {self.server_host}:{self.server_port}")
    
    def load_config(self):
        """Load admin configuration from file"""
        config_file = 'admin_config.json'
        default_config = {
            'use_api_key': True,
            'api_key': '',
            'admin_id': 'ADMIN_001',
            'password': 'admin123',
            'server_host': 'localhost',
            'server_port': 9999,
            'last_connection': None
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
        except Exception as e:
            print(f"⚠️  Error loading config: {e}")
        
        return default_config.copy()
    
    def save_config(self):
        """Save configuration to file"""
        config_file = 'admin_config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving config: {e}")
    
    def build_request(self, action, data=None):
        """Build admin request with proper authentication"""
        request = {
            'client_type': 'admin',
            'action': action,
            'admin_id': self.admin_id,
            'client_version': '3.0',
            'timestamp': datetime.now().isoformat()
        }
        
        # Add session ID if available
        if self.session_id:
            request['session_id'] = self.session_id
        
        # Add authentication
        if self.use_api_key and self.api_key:
            request['api_key'] = self.api_key
        else:
            request['password'] = self.password
        
        # Add action-specific data
        if data:
            request.update(data)
        
        return request
    
    def send_request(self, request):
        """Send request to server and get response"""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)
            client_socket.connect((self.server_host, self.server_port))
            
            client_socket.send(json.dumps(request).encode('utf-8'))
            
            # Receive response
            response_data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if len(chunk) < 4096:
                    break
            
            client_socket.close()
            
            # Parse response
            response = json.loads(response_data.decode('utf-8'))
            
            # Save session ID if provided
            if 'session_id' in response:
                self.session_id = response['session_id']
            
            # Update last activity
            self.last_activity = datetime.now()
            
            return response
            
        except socket.timeout:
            return {'status': 'error', 'message': 'Connection timeout'}
        except ConnectionRefusedError:
            return {'status': 'error', 'message': 'Cannot connect to server'}
        except json.JSONDecodeError:
            return {'status': 'error', 'message': 'Invalid response from server'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def send_signal(self, symbol, price, sl, tp, signal_type):
        """Send trading signal"""
        print(f"\n📤 Sending signal: {symbol} {signal_type.upper()}")
        
        data = {
            'symbol': symbol,
            'price': float(price),
            'sl': float(sl),
            'tp': float(tp),
            'type': signal_type.lower()
        }
        
        request = self.build_request('send_signal', data)
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            print("✅ Signal sent successfully!")
            signal_data = response.get('signal', {})
            print(f"📋 Signal ID: {signal_data.get('signal_id')}")
            print(f"📊 Total active signals: {response.get('total_active_signals')}")
            print(f"👤 Admin: {response.get('admin_id')}")
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def get_stats(self):
        """Get server statistics"""
        print("\n📊 Requesting server statistics...")
        
        request = self.build_request('get_stats')
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            stats = response.get('stats', {})
            print("\n" + "="*60)
            print("📊 SERVER STATISTICS")
            print("="*60)
            print(f"Server Status     : {stats.get('server_status')}")
            print(f"Uptime            : {self.format_seconds(stats.get('uptime_seconds', 0))}")
            print(f"Active Signals    : {stats.get('active_signals_count', 0)}")
            print(f"Total Customers   : {stats.get('total_customers_served', 0)}")
            print(f"Active Connections: {stats.get('active_connections', 0)}/{stats.get('max_connections', 0)}")
            print(f"Signal Deliveries : {stats.get('total_signal_deliveries', 0)}")
            print(f"Active Sessions   : {stats.get('active_sessions', 0)}")
            print(f"Admin Activities  : {stats.get('admin_activities_count', 0)}")
            
            # Show admin-specific stats
            if 'your_signals_active' in stats:
                print(f"\n👤 YOUR STATS:")
                print(f"  Your active signals : {stats.get('your_signals_active', 0)}")
                print(f"  Your recent activities: {len(stats.get('your_recent_activities', []))}")
            
            # Show recent signals
            if 'active_signals_info' in stats and stats['active_signals_info']:
                print(f"\n🔔 RECENT ACTIVE SIGNALS:")
                for signal in stats['active_signals_info']:
                    age = self.format_seconds(signal.get('age_seconds', 0))
                    expires = self.format_seconds(signal.get('expires_in', 0))
                    print(f"  • {signal['symbol']} {signal['type']} | "
                          f"ID: {signal['signal_id'][:8]}... | "
                          f"Age: {age} | Expires: {expires}")
            
            # Database stats if available
            if 'database_stats' in stats:
                db_stats = stats['database_stats']
                if db_stats.get('available', False):
                    print(f"\n🗄️ DATABASE STATS:")
                    print(f"  Total Signals  : {db_stats.get('total_signals', 0)}")
                    print(f"  Active Signals : {db_stats.get('active_signals', 0)}")
                    print(f"  Total Customers: {db_stats.get('total_customers', 0)}")
                    print(f"  Total Admins   : {db_stats.get('total_admins', 0)}")
            
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def format_seconds(self, seconds):
        """Format seconds to human readable time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m"
        elif seconds < 86400:
            return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"
        else:
            return f"{int(seconds/86400)}d {int((seconds%86400)/3600)}h"
    
    def get_history(self, limit=20):
        """Get signal history"""
        print(f"\n📜 Requesting signal history (last {limit} signals)...")
        
        request = self.build_request('get_history', {'limit': limit})
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            history = response.get('history', [])
            print(f"\n📋 SIGNAL HISTORY ({len(history)} signals)")
            print("="*60)
            
            for i, signal in enumerate(history, 1):
                print(f"\nSignal #{i}:")
                print(f"  ID     : {signal.get('id')}")
                print(f"  Symbol : {signal.get('symbol')}")
                print(f"  Type   : {signal.get('type', '').upper()}")
                print(f"  Price  : {signal.get('price')}")
                print(f"  SL     : {signal.get('sl')}")
                print(f"  TP     : {signal.get('tp')}")
                print(f"  Admin  : {signal.get('admin_id', 'unknown')}")
                print(f"  Time   : {signal.get('created_at')}")
                print(f"  Status : {signal.get('status', 'active')}")
                print(f"  Expires: {signal.get('expires_at')}")
            
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def get_health(self):
        """Check server health"""
        print("\n🏥 Performing server health check...")
        
        request = self.build_request('get_health')
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            health = response.get('health', {})
            print("\n" + "="*60)
            print("🏥 SERVER HEALTH CHECK")
            print("="*60)
            print(f"Status           : {health.get('status', 'unknown')}")
            print(f"Connections      : {health.get('connections', 0)}")
            print(f"Active Signals   : {health.get('active_signals', 0)}")
            print(f"Total Customers  : {health.get('total_customers', 0)}")
            print(f"Uptime           : {self.format_seconds(health.get('uptime_seconds', 0))}")
            print(f"Memory Usage     : {health.get('memory_mb', 0)} MB")
            print(f"CPU Usage        : {health.get('cpu_percent', 0)}%")
            print(f"Active Sessions  : {health.get('active_sessions', 0)}")
            print(f"Rate Limited     : {health.get('rate_limited_users', 0)}")
            print(f"Timestamp        : {health.get('timestamp')}")
            
            # Status indicator
            status = health.get('status', '').lower()
            if status == 'healthy':
                print("✅ Server is healthy!")
            elif status == 'warning':
                print("⚠️  Server has warnings!")
            else:
                print("❌ Server may have issues!")
            
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def get_admin_activity(self, limit=10):
        """Get admin activity log"""
        print(f"\n📝 Requesting admin activity log (last {limit} activities)...")
        
        request = self.build_request('get_admin_activity', {'limit': limit})
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            activities = response.get('activities', [])
            print(f"\n📝 ADMIN ACTIVITY LOG ({len(activities)} activities)")
            print("="*60)
            
            for i, activity in enumerate(activities, 1):
                timestamp = activity.get('timestamp', '')
                if 'T' in timestamp:
                    timestamp = timestamp.replace('T', ' ').split('.')[0]
                
                print(f"\nActivity #{i}:")
                print(f"  Admin    : {activity.get('admin_id')}")
                print(f"  Action   : {activity.get('action')}")
                print(f"  Details  : {activity.get('details', 'N/A')}")
                print(f"  Time     : {timestamp}")
                print(f"  IP/Source: {activity.get('ip', 'N/A')}")
            
            print(f"\n📊 Total activities: {response.get('total_activities', 0)}")
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def list_api_keys(self):
        """List API keys (masked)"""
        print("\n🔑 Requesting API key list...")
        
        request = self.build_request('list_api_keys')
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            admin_keys = response.get('admin_keys', {})
            customer_keys = response.get('customer_keys', {})
            
            print("\n🔑 API KEY LIST (MASKED FOR SECURITY)")
            print("="*60)
            
            print("\n🛠️  ADMIN KEYS:")
            if admin_keys:
                for admin_id, masked_key in admin_keys.items():
                    print(f"  {admin_id}: {masked_key}")
            else:
                print("  No admin keys found")
            
            print("\n👥 CUSTOMER KEYS:")
            if customer_keys:
                for cust_id, masked_key in customer_keys.items():
                    print(f"  {cust_id}: {masked_key}")
            else:
                print("  No customer keys found")
            
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def test_connection(self):
        """Test connection to server"""
        print(f"\n🔗 Testing connection to {self.server_host}:{self.server_port}...")
        
        request = self.build_request('get_health')
        response = self.send_request(request)
        
        if response.get('status') == 'success':
            print("✅ Connection successful!")
            print("✅ Authentication successful!")
            
            # Show auth method
            if self.use_api_key:
                masked_key = self.api_key[:8] + "..." + self.api_key[-4:] if len(self.api_key) > 12 else "***"
                print(f"🔐 Using API Key: {masked_key}")
            else:
                print(f"🔐 Using Password authentication (Legacy)")
            
            # Show session info
            if self.session_id:
                print(f"🔑 Session ID: {self.session_id[:8]}...")
            
            return True
        else:
            print(f"❌ Error: {response.get('message')}")
            return False
    
    def configure_auth(self):
        """Configure authentication method"""
        print("\n🔐 CONFIGURE AUTHENTICATION")
        print("="*40)
        print("1. Use API Key (Recommended)")
        print("2. Use Password (Legacy)")
        print("3. Enter/Change API Key")
        print("4. Change Admin ID")
        print("5. Back to Menu")
        
        choice = input("Select [1-5]: ").strip()
        
        if choice == '1':
            if self.api_key:
                self.use_api_key = True
                self.config['use_api_key'] = True
                self.save_config()
                print("✅ Using API Key authentication")
            else:
                print("❌ No API Key configured. Use option 3 to enter one.")
        
        elif choice == '2':
            self.use_api_key = False
            self.config['use_api_key'] = False
            self.save_config()
            print("✅ Using Password authentication (Legacy)")
        
        elif choice == '3':
            print("\nEnter your Admin API Key:")
            print("(Get this from server administrator)")
            new_api_key = input("API Key: ").strip()
            if new_api_key:
                self.api_key = new_api_key
                self.use_api_key = True
                self.config['api_key'] = new_api_key
                self.config['use_api_key'] = True
                self.save_config()
                print("✅ API Key saved and enabled!")
            else:
                print("❌ API Key cannot be empty")
        
        elif choice == '4':
            print("\nEnter your Admin ID:")
            new_admin_id = input("Admin ID: ").strip()
            if new_admin_id:
                self.admin_id = new_admin_id
                self.config['admin_id'] = new_admin_id
                self.save_config()
                print("✅ Admin ID updated!")
            else:
                print("❌ Admin ID cannot be empty")
        
        elif choice == '5':
            return
        
        else:
            print("❌ Invalid choice")
    
    def configure_server(self):
        """Configure server connection"""
        print("\n🌐 CONFIGURE SERVER CONNECTION")
        print("="*40)
        
        new_host = input(f"Server host [{self.server_host}]: ").strip()
        if new_host:
            self.server_host = new_host
            self.config['server_host'] = new_host
        
        new_port = input(f"Server port [{self.server_port}]: ").strip()
        if new_port:
            try:
                self.server_port = int(new_port)
                self.config['server_port'] = self.server_port
            except ValueError:
                print("❌ Port must be a number")
        
        self.save_config()
        print("✅ Server configuration updated!")
    
    def view_session_info(self):
        """View current session information"""
        print("\n🔐 SESSION INFORMATION")
        print("="*40)
        print(f"Admin ID      : {self.admin_id}")
        print(f"Auth Method   : {'API Key' if self.use_api_key else 'Password'}")
        print(f"Session ID    : {self.session_id[:8] + '...' if self.session_id else 'Not established'}")
        print(f"Last Activity : {self.last_activity.strftime('%Y-%m-%d %H:%M:%S') if self.last_activity else 'Never'}")
        print(f"Server        : {self.server_host}:{self.server_port}")
    
    def menu(self):
        """Admin main menu"""
        while True:
            print("\n" + "="*60)
            print("🛠️  ADMIN TRADING CLIENT v3.0")
            print("="*60)
            print(f"Admin ID   : {self.admin_id}")
            print(f"Auth Method: {'🔐 API Key' if self.use_api_key else '🔓 Password'}")
            print(f"Server     : {self.server_host}:{self.server_port}")
            print(f"Session    : {self.session_id[:8] + '...' if self.session_id else '❌ No session'}")
            print(f"Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-"*60)
            print("1. 📤 Send Trading Signal")
            print("2. 📊 View Server Statistics")
            print("3. 📜 View Signal History")
            print("4. 📝 View Admin Activity Log")
            print("5. 🏥 Server Health Check")
            print("6. 🔑 List API Keys")
            print("7. 🔗 Test Connection")
            print("8. 🔐 Configure Authentication")
            print("9. 🌐 Configure Server")
            print("10. 👁️  View Session Info")
            print("11. 🚪 Exit")
            print("="*60)
            
            choice = input("Select [1-11]: ").strip()
            
            if choice == '1':
                print("\n📝 ENTER SIGNAL DETAILS:")
                symbol = input("Symbol (e.g., BTCUSD): ").strip().upper()
                signal_type = input("Type (buy/sell): ").strip().lower()
                price = input("Entry Price: ").strip()
                sl = input("Stop Loss: ").strip()
                tp = input("Take Profit: ").strip()
                
                if not all([symbol, signal_type, price, sl, tp]):
                    print("❌ All fields are required!")
                    continue
                
                if signal_type not in ['buy', 'sell']:
                    print("❌ Type must be 'buy' or 'sell'!")
                    continue
                
                try:
                    self.send_signal(symbol, price, sl, tp, signal_type)
                except ValueError:
                    print("❌ Price, SL, and TP must be numbers!")
            
            elif choice == '2':
                self.get_stats()
            
            elif choice == '3':
                limit = input("Number of signals to show [20]: ").strip()
                try:
                    limit = int(limit) if limit else 20
                    self.get_history(limit)
                except ValueError:
                    print("❌ Invalid number, using 20")
                    self.get_history()
            
            elif choice == '4':
                limit = input("Number of activities to show [10]: ").strip()
                try:
                    limit = int(limit) if limit else 10
                    self.get_admin_activity(limit)
                except ValueError:
                    print("❌ Invalid number, using 10")
                    self.get_admin_activity()
            
            elif choice == '5':
                self.get_health()
            
            elif choice == '6':
                self.list_api_keys()
            
            elif choice == '7':
                self.test_connection()
            
            elif choice == '8':
                self.configure_auth()
            
            elif choice == '9':
                self.configure_server()
            
            elif choice == '10':
                self.view_session_info()
            
            elif choice == '11':
                print("\n👋 Exiting Admin Client...")
                break
            
            else:
                print("❌ Invalid choice!")
        
        # Clear session on exit
        self.session_id = None

def main():
    """Main function"""
    print("🛠️  ADMIN TRADING CLIENT v3.0")
    print("="*50)
    print("🔔 FEATURES:")
    print("  • API Key Authentication")
    print("  • Session Management")
    print("  • Admin Activity Monitoring")
    print("  • Server Health Check")
    print("="*50)
    
    # Get server info
    server_host = 'localhost'
    server_port = 9999
    
    # Load config if exists
    config_file = 'admin_config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                server_host = config.get('server_host', 'localhost')
                server_port = config.get('server_port', 9999)
        except:
            pass
    
    print(f"\n📡 Server: {server_host}:{server_port}")
    
    change_server = input("Change server? (y/n): ").strip().lower()
    if change_server == 'y':
        server_host = input("Server host [localhost]: ").strip() or 'localhost'
        server_port = input("Server port [9999]: ").strip() or '9999'
        try:
            server_port = int(server_port)
        except ValueError:
            print("❌ Port must be a number! Using 9999")
            server_port = 9999
    
    # Create admin client
    try:
        admin = AdminClient(server_host=server_host, server_port=server_port)
        admin.menu()
    except KeyboardInterrupt:
        print("\n\n👋 Admin client stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()