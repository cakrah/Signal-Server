#!/usr/bin/env python3
"""
Customer Trading Client v4.0 - WITH API KEY AUTHENTICATION
Support for API Key authentication with backward compatibility
"""

import socket
import json
import time
from datetime import datetime
import random
import string
import os
import sys
import hashlib

class CustomerClient:
    def __init__(self, server_host='localhost', server_port=9999):
        """
        Initialize Customer Client with API Key support
        """
        self.server_host = server_host
        self.server_port = server_port
        
        # Load configuration
        self.config = self.load_config()
        
        # Authentication methods
        self.use_api_key = self.config.get('use_api_key', True)
        self.api_key = self.config.get('api_key', '')
        self.customer_id = self.config.get('customer_id', '')
        self.password = self.config.get('password', 'cust123')  # Legacy fallback
        
        # If no customer_id, generate one
        if not self.customer_id:
            self.customer_id = self.generate_customer_id()
            self.config['customer_id'] = self.customer_id
            self.save_config()
        
        # Tracking
        self.received_signals = []  # All signals received
        self.received_signal_ids = set()  # Unique signal IDs
        self.total_checks = 0
        self.successful_checks = 0
        self.connection_stats = {
            'total_attempts': 0,
            'successful': 0,
            'failed': 0,
            'auth_errors': 0
        }
        
        print(f"👤 Customer ID: {self.customer_id}")
        print(f"🔐 Auth Method: {'API Key' if self.use_api_key else 'Password (Legacy)'}")
        print(f"🌐 Server: {self.server_host}:{self.server_port}")
    
    def load_config(self):
        """Load configuration from file"""
        config_file = 'customer_config.json'
        default_config = {
            'use_api_key': True,
            'api_key': '',
            'customer_id': '',
            'password': 'cust123',
            'server_host': 'localhost',
            'server_port': 9999,
            'auto_save_history': True,
            'check_interval': 60,
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
        config_file = 'customer_config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving config: {e}")
    
    def generate_customer_id(self):
        """Generate unique customer ID"""
        timestamp = int(time.time())
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"CUST_{timestamp}_{random_str}"
    
    def build_request(self, action='check_signal'):
        """
        Build request with proper authentication method
        """
        request = {
            'client_type': 'customer',
            'action': action,
            'customer_id': self.customer_id,
            'client_version': '4.0',
            'timestamp': datetime.now().isoformat()
        }
        
        if self.use_api_key and self.api_key:
            # Use API Key authentication
            request['api_key'] = self.api_key
        else:
            # Use legacy password authentication
            request['password'] = self.password
        
        return request
    
    def connect_and_check(self, action='check_signal'):
        """Connect to server and check signal with error handling"""
        self.connection_stats['total_attempts'] += 1
        
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)
            
            # Connect
            client_socket.connect((self.server_host, self.server_port))
            
            # Build and send request
            request = self.build_request(action)
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
            self.connection_stats['successful'] += 1
            
            # Update last successful connection
            self.config['last_connection'] = datetime.now().isoformat()
            self.save_config()
            
            return response
            
        except socket.timeout:
            self.connection_stats['failed'] += 1
            return {'status': 'error', 'message': 'Connection timeout'}
        except ConnectionRefusedError:
            self.connection_stats['failed'] += 1
            return {'status': 'error', 'message': 'Cannot connect to server'}
        except json.JSONDecodeError:
            self.connection_stats['failed'] += 1
            return {'status': 'error', 'message': 'Invalid response from server'}
        except Exception as e:
            self.connection_stats['failed'] += 1
            return {'status': 'error', 'message': str(e)}
    
    def check_signal(self, display=True):
        """Check for new signals from server"""
        self.total_checks += 1
        
        if display:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Checking signals...")
            print(f"👤 Customer: {self.customer_id}")
            if self.use_api_key:
                masked_key = self.api_key[:8] + "..." + self.api_key[-4:] if len(self.api_key) > 12 else "***"
                print(f"🔐 API Key: {masked_key}")
        
        response = self.connect_and_check('check_signal')
        
        if response.get('status') == 'success':
            if response.get('signal_available'):
                signals = response.get('signals', [])
                new_signals_count = response.get('new_signals_count', 0)
                total_active_signals = response.get('total_active_signals', 0)
                
                if display:
                    print(f"📡 Active signals on server: {total_active_signals}")
                    print(f"📥 New signals available: {new_signals_count}")
                
                if new_signals_count == 0:
                    if display:
                        print("📭 No new signals available")
                    return {
                        'success': False,
                        'message': 'No new signals',
                        'new_signals_count': 0,
                        'total_active_signals': total_active_signals
                    }
                
                # Process each new signal
                processed_count = 0
                new_signals_list = []
                
                for signal in signals:
                    signal_id = signal.get('signal_id')
                    
                    # Skip if already received
                    if signal_id in self.received_signal_ids:
                        if display:
                            print(f"⚠️  Skipping signal {signal_id[:8]}... (already received)")
                        continue
                    
                    # Add to received signals
                    self.received_signals.append(signal)
                    self.received_signal_ids.add(signal_id)
                    new_signals_list.append(signal)
                    processed_count += 1
                    
                    if display:
                        self._display_signal(signal)
                        self._execute_trading(signal)
                
                self.successful_checks += processed_count
                
                # Save history if enabled
                if self.config.get('auto_save_history', True) and processed_count > 0:
                    self.save_signal_history()
                
                if display and processed_count > 0:
                    print(f"\n✅ Successfully received {processed_count} new signal(s)")
                    print(f"📊 Total unique signals received: {len(self.received_signal_ids)}")
                
                return {
                    'success': True,
                    'new_signals_count': processed_count,
                    'new_signals': new_signals_list,
                    'total_active_signals': total_active_signals
                }
            else:
                message = response.get('message', 'No signal available')
                if display:
                    print(f"📭 {message}")
                return {
                    'success': False,
                    'message': message,
                    'total_active_signals': response.get('total_active_signals', 0)
                }
        else:
            error_msg = response.get('message', 'Unknown error')
            
            # Check if it's an authentication error
            if 'authentication' in error_msg.lower() or 'auth' in error_msg.lower():
                self.connection_stats['auth_errors'] += 1
                if display:
                    print(f"🔐 Authentication Error: {error_msg}")
                    print("💡 Try reconfiguring your API Key in settings")
            else:
                if display:
                    print(f"❌ Error: {error_msg}")
            
            return {
                'success': False,
                'message': error_msg
            }
    
    def _display_signal(self, signal):
        """Display single signal information"""
        print("\n" + "="*60)
        print("🎯 NEW TRADING SIGNAL RECEIVED!")
        print("="*60)
        print(f"Signal ID : {signal.get('signal_id')}")
        print(f"Symbol    : {signal['symbol']}")
        print(f"Type      : {signal['type'].upper()}")
        print(f"Entry     : {signal['price']}")
        print(f"Stop Loss : {signal['sl']}")
        print(f"Take Profit: {signal['tp']}")
        print(f"Time      : {signal['timestamp']}")
        
        # Calculate risk/reward
        price_val = signal['price']
        sl_val = signal['sl']
        tp_val = signal['tp']
        
        if signal['type'] == 'buy':
            risk = price_val - sl_val
            reward = tp_val - price_val
            if risk > 0:
                rr_ratio = reward / risk
                print(f"Risk/Reward: 1:{rr_ratio:.2f}")
                print(f"Risk Amount: {risk:.4f}")
                print(f"Reward Amount: {reward:.4f}")
        else:
            risk = sl_val - price_val
            reward = price_val - tp_val
            if risk > 0:
                rr_ratio = reward / risk
                print(f"Risk/Reward: 1:{rr_ratio:.2f}")
                print(f"Risk Amount: {risk:.4f}")
                print(f"Reward Amount: {reward:.4f}")
        
        # Show age if available
        if 'age_seconds' in signal:
            age_min = signal['age_seconds'] / 60
            expires_in = signal.get('expires_in', 0) / 60
            print(f"Signal Age : {age_min:.1f} minutes")
            print(f"Expires in : {expires_in:.1f} minutes")
        
        print("="*60)
    
    def _execute_trading(self, signal):
        """Simulate trading execution"""
        print("\n⚡ AUTO TRADING EXECUTION:")
        print(f"1. Opening {signal['type']} position for {signal['symbol']}")
        print(f"2. Entry price: {signal['price']}")
        print(f"3. Stop Loss: {signal['sl']}")
        print(f"4. Take Profit: {signal['tp']}")
        print(f"5. Order submitted at {datetime.now().strftime('%H:%M:%S')}")
        print("✅ Trading execution completed!")
    
    def get_all_active_signals(self):
        """Get all active signals from server"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📡 Getting all active signals...")
        
        response = self.connect_and_check('get_all_signals')
        
        if response.get('status') == 'success':
            signals = response.get('signals', [])
            active_count = response.get('active_signals_count', 0)
            
            print(f"\n📊 ACTIVE SIGNALS ON SERVER: {active_count}")
            print("="*60)
            
            if active_count == 0:
                print("No active signals on server")
                return []
            
            for i, signal in enumerate(signals, 1):
                signal_id = signal.get('signal_id')
                is_new = signal.get('is_new', False)
                symbol = signal.get('symbol', 'N/A')
                signal_type = signal.get('type', 'N/A').upper()
                price = signal.get('price', 0)
                
                print(f"\nSignal #{i}:")
                print(f"  ID    : {signal_id}")
                print(f"  Symbol: {symbol}")
                print(f"  Type  : {signal_type}")
                print(f"  Price : {price}")
                print(f"  Status: {'🆕 NEW' if is_new else '📭 Already received'}")
                print(f"  Time  : {signal.get('timestamp', 'N/A')}")
                
                if 'age_seconds' in signal:
                    age_min = signal['age_seconds'] / 60
                    expires_in = signal.get('expires_in', 0) / 60
                    print(f"  Age   : {age_min:.1f} minutes")
                    print(f"  Expires in: {expires_in:.1f} minutes")
            
            return signals
        else:
            print(f"❌ Error: {response.get('message')}")
            return []
    
    def auto_trading_mode(self, interval=None):
        """Auto trading mode"""
        if interval is None:
            interval = self.config.get('check_interval', 60)
        
        print("\n" + "="*60)
        print("🤖 AUTO TRADING MODE")
        print("="*60)
        print(f"Customer ID  : {self.customer_id}")
        print(f"Auth Method  : {'API Key' if self.use_api_key else 'Password'}")
        print(f"Check interval: {interval} seconds")
        print(f"Server       : {self.server_host}:{self.server_port}")
        print(f"Start time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Unique signals: {len(self.received_signal_ids)}")
        print("="*60)
        print("\n🚀 Starting auto trading...")
        print("⏸️  Press Ctrl+C to stop\n")
        
        check_count = 0
        total_new_signals = 0
        
        try:
            while True:
                check_count += 1
                print(f"\n[Check #{check_count}] {datetime.now().strftime('%H:%M:%S')}")
                
                result = self.check_signal()
                
                if result['success']:
                    new_count = result.get('new_signals_count', 0)
                    if new_count > 0:
                        total_new_signals += new_count
                        wait_time = interval * 2  # Wait longer after new signals
                        print(f"\n✅ Received {new_count} new signal(s)! Total: {total_new_signals}")
                        print(f"⏳ Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"⏭️  No new signals, waiting {interval} seconds...")
                        time.sleep(interval)
                else:
                    if result['message'] == 'No new signals':
                        print(f"📭 No new signals, waiting {interval} seconds...")
                    elif 'Already received' in result.get('message', ''):
                        print(f"⏭️  Signals already received, waiting {interval} seconds...")
                    elif 'authentication' in result['message'].lower():
                        print(f"🔐 Authentication failed! Please check your API Key")
                        print(f"⏳ Waiting {interval} seconds before retry...")
                    else:
                        print(f"⚠️  {result.get('message', 'Error')}, waiting {interval} seconds...")
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            print("\n\n📊 TRADING SESSION STATISTICS:")
            print("="*40)
            print(f"Customer ID      : {self.customer_id}")
            print(f"Total checks     : {self.total_checks}")
            print(f"Unique signals   : {len(self.received_signal_ids)}")
            print(f"Session checks   : {check_count}")
            print(f"Session signals  : {total_new_signals}")
            if self.total_checks > 0:
                success_rate = (self.successful_checks / self.total_checks) * 100
                print(f"Success rate     : {success_rate:.1f}%")
            print("\n👋 Auto trading stopped")
    
    def manual_mode(self):
        """Manual check mode"""
        print("\n" + "="*60)
        print("👤 MANUAL CHECK MODE")
        print("="*60)
        print(f"Customer ID: {self.customer_id}")
        print(f"Unique signals: {len(self.received_signal_ids)}")
        print("Commands: check, all, stats, history, exit")
        print("="*60)
        
        check_count = 0
        total_new_signals = 0
        
        while True:
            cmd = input("\nCommand (check/all/stats/history/exit): ").strip().lower()
            
            if cmd == 'exit':
                break
            elif cmd == 'stats':
                self._show_server_stats()
                continue
            elif cmd == 'all':
                self.get_all_active_signals()
                continue
            elif cmd == 'history':
                self.view_history()
                continue
            elif cmd == 'check' or cmd == '':
                check_count += 1
                result = self.check_signal()
                
                if result['success']:
                    new_count = result.get('new_signals_count', 0)
                    if new_count > 0:
                        total_new_signals += new_count
                        print(f"✅ Received {new_count} new signal(s)")
                    else:
                        print("📭 No new signals")
                else:
                    print(f"⚠️  {result.get('message', 'Error')}")
            else:
                print("❌ Unknown command. Use: check, all, stats, history, exit")
        
        print(f"\n📊 Session Summary:")
        print(f"Customer ID: {self.customer_id}")
        print(f"Checks: {check_count}")
        print(f"New signals received: {total_new_signals}")
        print(f"Total unique signals: {len(self.received_signal_ids)}")
    
    def save_signal_history(self):
        """Save signal history to file"""
        history_file = f'signals_history_{self.customer_id}.json'
        try:
            # Save only unique signals
            unique_history = []
            seen_ids = set()
            
            for signal in reversed(self.received_signals):
                signal_id = signal.get('signal_id')
                if signal_id not in seen_ids:
                    seen_ids.add(signal_id)
                    unique_history.append(signal)
            
            # Reverse back to chronological order
            unique_history.reverse()
            
            with open(history_file, 'w') as f:
                json.dump({
                    'customer_id': self.customer_id,
                    'total_signals': len(unique_history),
                    'saved_at': datetime.now().isoformat(),
                    'signals': unique_history
                }, f, indent=2)
            
            print(f"💾 History saved to {history_file}")
        except Exception as e:
            print(f"⚠️  Could not save history: {e}")
    
    def load_signal_history(self):
        """Load signal history from file"""
        history_file = f'signals_history_{self.customer_id}.json'
        try:
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    signals = data.get('signals', [])
                    
                    # Add to received signals
                    for signal in signals:
                        signal_id = signal.get('signal_id')
                        if signal_id:
                            self.received_signal_ids.add(signal_id)
                    self.received_signals.extend(signals)
                    
                    print(f"📂 Loaded {len(signals)} signals from history")
                    return True
        except Exception as e:
            print(f"⚠️  Error loading history: {e}")
        
        return False
    
    def _show_server_stats(self):
        """Show server statistics"""
        print("\n📡 Requesting server statistics...")
        
        response = self.connect_and_check('check_signal')
        
        if response.get('status') == 'success':
            total_active = response.get('total_active_signals', 0)
            print(f"\n📊 SERVER STATISTICS:")
            print(f"Active signals: {total_active}")
            print(f"Your received signals: {len(self.received_signal_ids)}")
            if total_active > 0:
                print(f"Signals pending: {total_active - len(self.received_signal_ids)}")
        else:
            print(f"❌ Could not get server stats: {response.get('message')}")
    
    def view_history(self):
        """View signal history"""
        print(f"\n📋 RECEIVED SIGNALS HISTORY")
        print("="*60)
        print(f"Customer ID: {self.customer_id}")
        print(f"Total signals received: {len(self.received_signals)}")
        print(f"Unique signal IDs: {len(self.received_signal_ids)}")
        print("="*60)
        
        if not self.received_signals:
            print("No signals received yet.")
            return
        
        # Show only unique signals
        unique_signals = {}
        for signal in self.received_signals:
            signal_id = signal.get('signal_id')
            if signal_id not in unique_signals:
                unique_signals[signal_id] = signal
        
        for i, (signal_id, signal) in enumerate(unique_signals.items(), 1):
            signal_id_short = signal_id[:8] + "..." if len(signal_id) > 8 else signal_id
            print(f"\nSignal #{i} (ID: {signal_id_short}):")
            print(f"  Symbol: {signal.get('symbol', 'N/A')}")
            print(f"  Type  : {signal.get('type', 'N/A').upper()}")
            print(f"  Price : {signal.get('price', 0)}")
            print(f"  SL    : {signal.get('sl', 0)}")
            print(f"  TP    : {signal.get('tp', 0)}")
            print(f"  Time  : {signal.get('timestamp', 'N/A')}")
        
        print(f"\n📊 Total unique signals: {len(unique_signals)}")
    
    def view_statistics(self):
        """View detailed statistics"""
        print("\n📊 CUSTOMER STATISTICS")
        print("="*50)
        print(f"Customer ID        : {self.customer_id}")
        print(f"Authentication     : {'API Key' if self.use_api_key else 'Password'}")
        print(f"Server             : {self.server_host}:{self.server_port}")
        print(f"Total checks made  : {self.total_checks}")
        print(f"Successful checks  : {self.successful_checks}")
        print(f"Signals received   : {len(self.received_signals)}")
        print(f"Unique signals     : {len(self.received_signal_ids)}")
        
        if self.total_checks > 0:
            success_rate = (self.successful_checks / self.total_checks) * 100
            print(f"Check success rate : {success_rate:.1f}%")
        
        # Connection statistics
        print(f"\n🔗 CONNECTION STATISTICS:")
        print(f"Total attempts     : {self.connection_stats['total_attempts']}")
        print(f"Successful         : {self.connection_stats['successful']}")
        print(f"Failed             : {self.connection_stats['failed']}")
        print(f"Auth errors        : {self.connection_stats['auth_errors']}")
        
        if self.connection_stats['total_attempts'] > 0:
            success_rate = (self.connection_stats['successful'] / self.connection_stats['total_attempts']) * 100
            print(f"Connection rate    : {success_rate:.1f}%")
        
        # Last connection
        if self.config.get('last_connection'):
            last_conn = datetime.fromisoformat(self.config['last_connection'])
            print(f"Last connection    : {last_conn.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def test_connection(self):
        """Test connection to server"""
        print("\n🔗 Testing connection to server...")
        print(f"Customer ID: {self.customer_id}")
        print(f"Auth Method: {'API Key' if self.use_api_key else 'Password'}")
        
        response = self.connect_and_check('check_signal')
        
        if response.get('status') == 'success':
            print("✅ Connection successful!")
            print(f"✅ Authentication successful!")
            print(f"📡 Server has {response.get('total_active_signals', 0)} active signals")
            
            # Show authentication method used
            if self.use_api_key:
                print("🔐 Authentication: API Key")
            else:
                print("🔐 Authentication: Password (Legacy)")
        else:
            error_msg = response.get('message', 'Unknown error')
            print(f"❌ Connection failed: {error_msg}")
            
            # Provide troubleshooting tips
            if 'authentication' in error_msg.lower():
                print("\n💡 TROUBLESHOOTING:")
                print("1. Check if your API Key is correct")
                print("2. Make sure your Customer ID matches the API Key")
                print("3. Try switching to password authentication")
    
    def configure_auth(self):
        """Configure authentication method"""
        print("\n🔐 CONFIGURE AUTHENTICATION")
        print("="*40)
        print("1. Use API Key (Recommended)")
        print("2. Use Password (Legacy)")
        print("3. Enter API Key Manually")
        print("4. Back to Menu")
        
        choice = input("Select [1-4]: ").strip()
        
        if choice == '1':
            # Use API Key from config
            if self.api_key:
                self.use_api_key = True
                self.config['use_api_key'] = True
                self.save_config()
                print("✅ Using API Key authentication")
            else:
                print("❌ No API Key configured. Use option 3 to enter one.")
        elif choice == '2':
            # Use Password
            self.use_api_key = False
            self.config['use_api_key'] = False
            self.save_config()
            print("✅ Using Password authentication (Legacy)")
        elif choice == '3':
            # Enter API Key manually
            print("\nEnter your API Key (get from server administrator):")
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
    
    def clear_history(self):
        """Clear signal history"""
        confirm = input("\n⚠️  Clear ALL signal history? (y/n): ").strip().lower()
        if confirm == 'y':
            self.received_signals.clear()
            self.received_signal_ids.clear()
            self.total_checks = 0
            self.successful_checks = 0
            
            # Clear history file
            history_file = f'signals_history_{self.customer_id}.json'
            if os.path.exists(history_file):
                os.remove(history_file)
            
            print("✅ History cleared!")
        else:
            print("❌ Cancelled")
    
    def export_signals(self):
        """Export signals to CSV file"""
        if not self.received_signals:
            print("❌ No signals to export")
            return
        
        csv_file = f'signals_export_{self.customer_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        try:
            with open(csv_file, 'w') as f:
                # Write header
                f.write("signal_id,symbol,type,price,sl,tp,timestamp,age_seconds,is_new\n")
                
                # Write data
                for signal in self.received_signals:
                    signal_id = signal.get('signal_id', '')
                    symbol = signal.get('symbol', '')
                    signal_type = signal.get('type', '')
                    price = signal.get('price', 0)
                    sl = signal.get('sl', 0)
                    tp = signal.get('tp', 0)
                    timestamp = signal.get('timestamp', '')
                    age = signal.get('age_seconds', 0)
                    is_new = signal.get('is_new', False)
                    
                    f.write(f'{signal_id},{symbol},{signal_type},{price},{sl},{tp},{timestamp},{age},{is_new}\n')
            
            print(f"✅ Signals exported to {csv_file}")
            print(f"📊 Total signals exported: {len(self.received_signals)}")
            
        except Exception as e:
            print(f"❌ Error exporting: {e}")
    
    def menu(self):
        """Main menu"""
        # Load history on startup
        self.load_signal_history()
        
        while True:
            print("\n" + "="*60)
            print("👤 CUSTOMER TRADING CLIENT v4.0")
            print("="*60)
            print(f"Customer ID: {self.customer_id}")
            print(f"Auth Method: {'🔐 API Key' if self.use_api_key else '🔓 Password'}")
            print(f"Server     : {self.server_host}:{self.server_port}")
            print(f"Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Signals    : {len(self.received_signal_ids)} unique")
            print("-"*60)
            print("1. 🤖 Auto Trading Mode")
            print("2. 👤 Manual Check Mode")
            print("3. 📡 View All Active Signals")
            print("4. 📋 View Signal History")
            print("5. 📊 View Statistics")
            print("6. 🔐 Configure Authentication")
            print("7. 🌐 Configure Server")
            print("8. 🔗 Test Connection")
            print("9. 📤 Export Signals to CSV")
            print("10. 🧹 Clear History")
            print("11. 🚪 Exit")
            print("="*60)
            
            choice = input("Select [1-11]: ").strip()
            
            if choice == '1':
                interval = input("Check interval in seconds [60]: ").strip()
                try:
                    interval = int(interval) if interval else self.config.get('check_interval', 60)
                    self.auto_trading_mode(interval)
                except ValueError:
                    print("❌ Invalid interval, using 60 seconds")
                    self.auto_trading_mode()
            elif choice == '2':
                self.manual_mode()
            elif choice == '3':
                self.get_all_active_signals()
            elif choice == '4':
                self.view_history()
            elif choice == '5':
                self.view_statistics()
            elif choice == '6':
                self.configure_auth()
            elif choice == '7':
                self.configure_server()
            elif choice == '8':
                self.test_connection()
            elif choice == '9':
                self.export_signals()
            elif choice == '10':
                self.clear_history()
            elif choice == '11':
                print("\n👋 Exiting Customer Client...")
                # Save before exit
                if self.config.get('auto_save_history', True):
                    self.save_signal_history()
                break
            else:
                print("❌ Invalid choice!")

def main():
    """Main function"""
    print("🚀 CUSTOMER TRADING CLIENT v4.0")
    print("="*50)
    print("🔔 FEATURES:")
    print("  • API Key Authentication")
    print("  • Multiple Signal Support")
    print("  • Auto & Manual Trading Modes")
    print("  • Signal History & Statistics")
    print("="*50)
    
    # Get server configuration
    config_file = 'customer_config.json'
    server_host = 'localhost'
    server_port = 9999
    
    try:
        if os.path.exists(config_file):
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
    
    # Create client
    try:
        client = CustomerClient(server_host=server_host, server_port=server_port)
        client.menu()
    except KeyboardInterrupt:
        print("\n\n👋 Client stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()