import socket
import json
import time
from datetime import datetime
import random
import string
import os

class CustomerClient:
    def __init__(self, server_host='localhost', server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.password = "cust123"  # Default password
        self.received_signals = []  # Menyimpan semua signal yang diterima
        self.received_signal_ids = set()  # Track signal IDs yang sudah diterima
        self.total_checks = 0
        self.successful_checks = 0
        
        # Generate unique customer ID
        self.customer_id = self.generate_customer_id()
        print(f"👤 Your Customer ID: {self.customer_id}")
    
    def generate_customer_id(self):
        """Generate unique customer ID"""
        timestamp = int(time.time())
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"CUST_{timestamp}_{random_str}"
    
    def connect_and_check(self, action='check_signal'):
        """Koneksi ke server dan check signal"""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)
            client_socket.connect((self.server_host, self.server_port))
            
            request = {
                'client_type': 'customer',
                'password': self.password,
                'action': action,
                'customer_id': self.customer_id  # Kirim ID unik
            }
            
            client_socket.send(json.dumps(request).encode('utf-8'))
            
            response_data = client_socket.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            client_socket.close()
            return response
            
        except socket.timeout:
            return {'status': 'error', 'message': 'Connection timeout'}
        except ConnectionRefusedError:
            return {'status': 'error', 'message': 'Cannot connect to server'}
        except json.JSONDecodeError:
            return {'status': 'error', 'message': 'Invalid response from server'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def check_signal(self, display=True):
        """Check signal dari server - UPDATED untuk MULTIPLE SIGNALS"""
        self.total_checks += 1
        
        if display:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Checking signal...")
            print(f"👤 Customer ID: {self.customer_id}")
        
        response = self.connect_and_check('check_signal')
        
        if response['status'] == 'success':
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
                    
                    # Skip jika sudah pernah terima
                    if signal_id in self.received_signal_ids:
                        if display:
                            print(f"⚠️  Skipping signal {signal_id} (already received)")
                        continue
                    
                    # Process signal baru
                    self.received_signals.append(signal)
                    self.received_signal_ids.add(signal_id)
                    new_signals_list.append(signal)
                    processed_count += 1
                    
                    if display:
                        self._display_signal(signal)
                        self._execute_trading(signal)
                
                self.successful_checks += processed_count
                
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
            if display:
                print(f"❌ Error: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
    
    def _display_signal(self, signal):
        """Display single signal information"""
        print("\n" + "="*60)
        print("🎯 TRADING SIGNAL DITERIMA!")
        print("="*60)
        print(f"Signal ID : {signal.get('signal_id')}")
        print(f"Symbol    : {signal['symbol']}")
        print(f"Type      : {signal['type'].upper()}")
        print(f"Entry     : {signal['price']}")
        print(f"Stop Loss : {signal['sl']}")
        print(f"Take Profit: {signal['tp']}")
        print(f"Time      : {signal['timestamp']}")
        
        # Hitung risk/reward
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
        
        # Tampilkan age jika ada
        if 'age_seconds' in signal:
            age_min = signal['age_seconds'] / 60
            print(f"Signal Age : {age_min:.1f} minutes")
        
        print("="*60)
    
    def _execute_trading(self, signal):
        """Execute trading for a signal"""
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
        
        if response['status'] == 'success':
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
                
                print(f"\nSignal #{i}:")
                print(f"  ID    : {signal_id}")
                print(f"  Symbol: {signal['symbol']}")
                print(f"  Type  : {signal['type'].upper()}")
                print(f"  Price : {signal['price']}")
                print(f"  Status: {'NEW' if is_new else 'Already received'}")
                print(f"  Time  : {signal['timestamp']}")
                
                if 'age_seconds' in signal:
                    age_min = signal['age_seconds'] / 60
                    expires_in = signal.get('expires_in', 0) / 60
                    print(f"  Age   : {age_min:.1f} minutes")
                    print(f"  Expires in: {expires_in:.1f} minutes")
            
            return signals
        else:
            print(f"❌ Error: {response.get('message')}")
            return []
    
    def auto_trading_mode(self, interval=60):
        """Mode auto trading - UPDATED untuk MULTIPLE SIGNALS"""
        print("\n" + "="*60)
        print("🤖 AUTO TRADING MODE")
        print("="*60)
        print(f"Customer ID : {self.customer_id}")
        print(f"Check interval : {interval} detik")
        print(f"Server         : {self.server_host}:{self.server_port}")
        print(f"Start time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Unique signals : {len(self.received_signal_ids)}")
        print("="*60)
        print("\n🚀 Starting auto trading...")
        print("⏸️  Press Ctrl+C to stop\n")
        
        check_count = 0
        total_new_signals = 0
        
        try:
            while True:
                check_count += 1
                print(f"\n[Check #{check_count}]")
                
                result = self.check_signal()
                
                if result['success']:
                    new_count = result.get('new_signals_count', 0)
                    if new_count > 0:
                        total_new_signals += new_count
                        wait_time = interval * 2  # Tunggu lebih lama setelah dapat signal BARU
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
                    else:
                        print(f"⚠️  {result.get('message', 'Error')}, waiting {interval} seconds...")
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            print("\n\n📊 TRADING STATISTICS:")
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
        """Mode manual check - UPDATED untuk MULTIPLE SIGNALS"""
        print("\n" + "="*60)
        print("👤 MANUAL CHECK MODE")
        print("="*60)
        print(f"Customer ID: {self.customer_id}")
        print(f"Unique signals: {len(self.received_signal_ids)}")
        print("Press Enter to check signal")
        print("Type 'stats' for server stats")
        print("Type 'all' to view all active signals")
        print("Type 'exit' to quit")
        print("="*60)
        
        check_count = 0
        total_new_signals = 0
        
        while True:
            cmd = input("\n↵ Press Enter to check (or 'stats'/'all'/'exit'): ").strip().lower()
            
            if cmd == 'exit':
                break
            elif cmd == 'stats':
                self._show_server_stats()
                continue
            elif cmd == 'all':
                self.get_all_active_signals()
                continue
            
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
        
        print(f"\n📊 Session Summary:")
        print(f"Customer ID: {self.customer_id}")
        print(f"Checks: {check_count}")
        print(f"New signals received: {total_new_signals}")
        print(f"Total unique signals: {len(self.received_signal_ids)}")
    
    def _show_server_stats(self):
        """Show server statistics"""
        print("\n📡 Requesting server statistics...")
        
        try:
            # Buat request khusus untuk stats
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)
            client_socket.connect((self.server_host, self.server_port))
            
            request = {
                'client_type': 'customer',
                'password': self.password,
                'action': 'check_signal',  # Akan dapat response dengan stats
                'customer_id': self.customer_id
            }
            
            client_socket.send(json.dumps(request).encode('utf-8'))
            response = json.loads(client_socket.recv(4096).decode('utf-8'))
            client_socket.close()
            
            if response['status'] == 'success':
                total_active = response.get('total_active_signals', 0)
                print(f"\n📊 SERVER STATISTICS:")
                print(f"Active signals: {total_active}")
                print(f"Your received signals: {len(self.received_signal_ids)}")
                if total_active > 0:
                    print(f"Signals pending: {total_active - len(self.received_signal_ids)}")
            else:
                print(f"❌ Could not get server stats")
                
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
    
    def view_history(self):
        """Lihat signal yang diterima"""
        print(f"\n📋 RECEIVED SIGNALS HISTORY")
        print("="*60)
        print(f"Customer ID: {self.customer_id}")
        print(f"Total signals received: {len(self.received_signals)}")
        print(f"Unique signal IDs: {len(self.received_signal_ids)}")
        print("="*60)
        
        if not self.received_signals:
            print("No signals received yet.")
            return
        
        # Tampilkan hanya signal unik (berdasarkan signal_id)
        unique_signals = {}
        for signal in self.received_signals:
            signal_id = signal.get('signal_id')
            if signal_id not in unique_signals:
                unique_signals[signal_id] = signal
        
        for i, (signal_id, signal) in enumerate(unique_signals.items(), 1):
            print(f"\nSignal #{i} (ID: {signal_id}):")
            print(f"  Symbol: {signal['symbol']}")
            print(f"  Type  : {signal['type'].upper()}")
            print(f"  Price : {signal['price']}")
            print(f"  SL    : {signal['sl']}")
            print(f"  TP    : {signal['tp']}")
            print(f"  Time  : {signal['timestamp']}")
            
            # Hitung risk/reward
            if signal['type'] == 'buy':
                risk = signal['price'] - signal['sl']
                reward = signal['tp'] - signal['price']
                if risk > 0:
                    rr_ratio = reward / risk
                    print(f"  R/R   : 1:{rr_ratio:.2f}")
            else:
                risk = signal['sl'] - signal['price']
                reward = signal['price'] - signal['tp']
                if risk > 0:
                    rr_ratio = reward / risk
                    print(f"  R/R   : 1:{rr_ratio:.2f}")
            
            print("-"*40)
        
        # Hitung berapa kali setiap signal diterima
        signal_count = {}
        for signal in self.received_signals:
            signal_id = signal.get('signal_id')
            signal_count[signal_id] = signal_count.get(signal_id, 0) + 1
        
        if len(self.received_signals) > len(unique_signals):
            print(f"\n📊 Reception Statistics:")
            for signal_id, count in signal_count.items():
                if count > 1:
                    print(f"  Signal {signal_id}: received {count} times")
    
    def view_statistics(self):
        """Lihat statistik"""
        print("\n📊 CUSTOMER STATISTICS")
        print("="*50)
        print(f"Customer ID        : {self.customer_id}")
        print(f"Total checks made  : {self.total_checks}")
        print(f"Successful checks  : {self.successful_checks}")
        print(f"Signals received   : {len(self.received_signals)}")
        print(f"Unique signals     : {len(self.received_signal_ids)}")
        
        if self.total_checks > 0:
            success_rate = (self.successful_checks / self.total_checks) * 100
            print(f"Check success rate : {success_rate:.1f}%")
        
        # Hitung duplikat
        if len(self.received_signals) > 0:
            duplicates = len(self.received_signals) - len(self.received_signal_ids)
            if duplicates > 0:
                print(f"Duplicate signals  : {duplicates}")
        
        if len(self.received_signals) > 0:
            print(f"\nLast signal received:")
            last_signal = self.received_signals[-1]
            signal_id = last_signal.get('signal_id', 'N/A')
            print(f"  Signal ID: {signal_id}")
            print(f"  Symbol   : {last_signal['symbol']}")
            print(f"  Type     : {last_signal['type'].upper()}")
            print(f"  Price    : {last_signal['price']}")
            print(f"  SL       : {last_signal['sl']}")
            print(f"  TP       : {last_signal['tp']}")
            print(f"  Time     : {last_signal['timestamp']}")
    
    def test_connection(self):
        """Test koneksi ke server"""
        print("\n🔗 Testing connection to server...")
        print(f"Customer ID: {self.customer_id}")
        
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(5)
            test_socket.connect((self.server_host, self.server_port))
            test_socket.close()
            print("✅ Connection successful!")
            
            # Test dengan check signal
            print("Testing authentication and signal check...")
            result = self.check_signal(display=False)
            
            if result['success'] or result['message'] == 'No new signals':
                print("✅ Authentication successful!")
                print(f"Server has {result.get('total_active_signals', 0)} active signals")
            else:
                print(f"⚠️  Authentication issue: {result['message']}")
                
        except socket.timeout:
            print("❌ Timeout: Server tidak merespons")
        except ConnectionRefusedError:
            print("❌ Cannot connect to server")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def change_password(self):
        """Ganti password customer"""
        print("\n🔐 Ganti Password Customer")
        print("="*40)
        
        new_pass = input("Password baru: ").strip()
        confirm_pass = input("Konfirmasi password: ").strip()
        
        if new_pass != confirm_pass:
            print("❌ Password tidak cocok!")
            return
        
        if len(new_pass) < 4:
            print("❌ Password minimal 4 karakter!")
            return
        
        self.password = new_pass
        print("✅ Password berhasil diubah!")
    
    def clear_history(self):
        """Clear signal history"""
        confirm = input("\n⚠️  Clear all signal history? (y/n): ").strip().lower()
        if confirm == 'y':
            self.received_signals.clear()
            self.received_signal_ids.clear()
            self.total_checks = 0
            self.successful_checks = 0
            print("✅ History cleared!")
        else:
            print("❌ Cancelled")
    
    def menu(self):
        """Menu utama"""
        while True:
            print("\n" + "="*60)
            print("👤 CUSTOMER TRADING CLIENT v3.0")
            print("="*60)
            print(f"Customer ID: {self.customer_id}")
            print(f"Server     : {self.server_host}:{self.server_port}")
            print(f"Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Signals    : {len(self.received_signals)} received")
            print(f"Unique     : {len(self.received_signal_ids)} unique signals")
            print("-"*60)
            print("1. 🤖 Auto Trading Mode (Get ALL new signals)")
            print("2. 👤 Manual Check Mode (Get ALL new signals)")
            print("3. 📡 View All Active Signals on Server")
            print("4. 📋 View Received Signals History")
            print("5. 📊 View Statistics")
            print("6. 🔐 Change Password")
            print("7. 🔗 Test Connection")
            print("8. 🧹 Clear History")
            print("9. 🚪 Exit")
            print("="*60)
            
            choice = input("Select [1-9]: ").strip()
            
            if choice == '1':
                interval = input("Check interval in seconds [60]: ").strip()
                try:
                    interval = int(interval) if interval else 60
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
                self.change_password()
            elif choice == '7':
                self.test_connection()
            elif choice == '8':
                self.clear_history()
            elif choice == '9':
                print("\n👋 Exiting Customer Client...")
                break
            else:
                print("❌ Invalid choice!")

if __name__ == "__main__":
    print("🚀 Starting Customer Trading Client v3.0")
    print("="*50)
    print("🔔 FEATURE: Get ALL active signals (once each)")
    print("="*50)
    
    # Konfigurasi server
    server_host = input(f"Server host [localhost]: ").strip() or 'localhost'
    server_port = input(f"Server port [9999]: ").strip() or '9999'
    
    try:
        server_port = int(server_port)
    except ValueError:
        print("❌ Port harus angka! Menggunakan port 9999")
        server_port = 9999
    
    client = CustomerClient(server_host=server_host, server_port=server_port)
    client.menu()