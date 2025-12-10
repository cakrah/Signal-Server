import socket
import json
import time
from datetime import datetime

class AdminClient:
    def __init__(self, server_host='localhost', server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.password = "admin123"  # Default, bisa diubah
        
    def connect_and_send(self, data):
        """Koneksi ke server dan kirim data"""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)
            client_socket.connect((self.server_host, self.server_port))
            
            # Tambahkan kredensial
            data['password'] = self.password
            data['client_type'] = 'admin'
            
            client_socket.send(json.dumps(data).encode('utf-8'))
            
            # Terima response
            response_data = client_socket.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            client_socket.close()
            return response
            
        except socket.timeout:
            return {'status': 'error', 'message': 'Connection timeout'}
        except ConnectionRefusedError:
            return {'status': 'error', 'message': 'Cannot connect to server'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def send_signal(self):
        """Kirim signal trading dengan TP"""
        print("\n" + "="*60)
        print("📤 KIRIM SIGNAL TRADING")
        print("="*60)
        
        symbol = input("Symbol (contoh: BTCUSD, EURUSD): ").strip().upper()
        
        if not symbol:
            print("❌ Symbol tidak boleh kosong!")
            return
        
        try:
            price = float(input("Entry Price: ").strip())
            sl = float(input("Stop Loss: ").strip())
            tp = float(input("Take Profit: ").strip())
        except ValueError:
            print("❌ Error: Price, SL, dan TP harus angka!")
            return
        
        while True:
            signal_type = input("Type (buy/sell): ").strip().lower()
            if signal_type in ['buy', 'sell']:
                break
            print("❌ Error: Type harus 'buy' atau 'sell'!")
        
        # Validasi TP berdasarkan type
        if signal_type == 'buy':
            if tp <= price:
                print("❌ Error: TP harus lebih besar dari Entry Price untuk BUY")
                return
            if sl >= price:
                print("❌ Error: SL harus lebih kecil dari Entry Price untuk BUY")
                return
        else:  # sell
            if tp >= price:
                print("❌ Error: TP harus lebih kecil dari Entry Price untuk SELL")
                return
            if sl <= price:
                print("❌ Error: SL harus lebih besar dari Entry Price untuk SELL")
                return
        
        # Konfirmasi
        print(f"\n📝 Konfirmasi Signal:")
        print(f"   Symbol: {symbol}")
        print(f"   Price: {price}")
        print(f"   SL: {sl}")
        print(f"   TP: {tp}")
        print(f"   Type: {signal_type.upper()}")
        
        # Hitung risk/reward
        if signal_type == 'buy':
            risk = price - sl
            reward = tp - price
            if risk > 0:
                rr_ratio = reward / risk
                print(f"   Risk/Reward: 1:{rr_ratio:.2f}")
        else:
            risk = sl - price
            reward = price - tp
            if risk > 0:
                rr_ratio = reward / risk
                print(f"   Risk/Reward: 1:{rr_ratio:.2f}")
        
        confirm = input("\nKirim signal ini? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Dibatalkan!")
            return
        
        # Kirim ke server
        request = {
            'action': 'send_signal',
            'symbol': symbol,
            'price': price,
            'sl': sl,
            'tp': tp,
            'type': signal_type
        }
        
        print("\n📡 Mengirim signal ke server...")
        response = self.connect_and_send(request)
        
        if response['status'] == 'success':
            print("✅ Signal berhasil dikirim!")
            signal_info = response.get('signal', {})
            print(f"\n📋 Detail Signal:")
            print(f"   Signal ID: {signal_info.get('signal_id', 'N/A')}")
            print(f"   Symbol: {signal_info.get('symbol')}")
            print(f"   Type: {signal_info.get('type').upper()}")
            print(f"   Price: {signal_info.get('price')}")
            print(f"   SL: {signal_info.get('sl')}")
            print(f"   TP: {signal_info.get('tp')}")
            print(f"   Time: {signal_info.get('timestamp')}")
            
            # Hitung risk/reward dari response
            price_val = signal_info.get('price')
            sl_val = signal_info.get('sl')
            tp_val = signal_info.get('tp')
            
            if price_val and sl_val and tp_val:
                if signal_type == 'buy':
                    risk = price_val - sl_val
                    reward = tp_val - price_val
                    if risk > 0:
                        rr_ratio = reward / risk
                        print(f"   Risk/Reward Ratio: 1:{rr_ratio:.2f}")
                        print(f"   Risk Amount: {risk:.4f}")
                        print(f"   Reward Amount: {reward:.4f}")
                else:
                    risk = sl_val - price_val
                    reward = price_val - tp_val
                    if risk > 0:
                        rr_ratio = reward / risk
                        print(f"   Risk/Reward Ratio: 1:{rr_ratio:.2f}")
                        print(f"   Risk Amount: {risk:.4f}")
                        print(f"   Reward Amount: {reward:.4f}")
        else:
            print(f"❌ Gagal: {response.get('message')}")
    
    def get_history(self):
        """Dapatkan history signal dari server"""
        print("\n📊 Mendapatkan history signal...")
        
        request = {'action': 'get_history'}
        response = self.connect_and_send(request)
        
        if response['status'] == 'success':
            history = response.get('history', [])
            print(f"\n📋 HISTORY SIGNAL ({len(history)} signal)")
            print("="*80)
            
            for i, signal in enumerate(history[:10], 1):  # Tampilkan 10 terbaru
                print(f"\nSignal #{i}:")
                print(f"   ID: {signal.get('id', 'N/A')}")
                print(f"   Symbol: {signal.get('symbol', 'N/A')}")
                print(f"   Type: {signal.get('type', 'N/A').upper()}")
                print(f"   Price: {signal.get('price', 'N/A')}")
                print(f"   SL: {signal.get('sl', 'N/A')}")
                print(f"   TP: {signal.get('tp', 'N/A')}")
                print(f"   Time: {signal.get('timestamp', 'N/A')}")
                print(f"   Status: {signal.get('status', 'N/A')}")
                print("-"*40)
            
            if len(history) > 10:
                print(f"\n... dan {len(history) - 10} signal lainnya")
        else:
            print(f"❌ Gagal: {response.get('message')}")
    
    def get_statistics(self):
        """Dapatkan statistik sistem"""
        print("\n📈 Mendapatkan statistik sistem...")
        
        request = {'action': 'get_stats'}
        response = self.connect_and_send(request)
        
        if response['status'] == 'success':
            stats = response.get('stats', {})
            print(f"\n📊 STATISTIK SISTEM")
            print("="*50)
            print(f"Total Signal: {stats.get('total_signals', 0)}")
            print(f"Signal Hari Ini: {stats.get('today_signals', 0)}")
            print(f"Signal Aktif: {stats.get('active_signals', 0)}")
            
            if 'buy_sell_ratio' in stats:
                print(f"\nRasio Buy/Sell:")
                for type_name, count in stats['buy_sell_ratio'].items():
                    print(f"   {type_name.upper()}: {count}")
            
            if 'performance' in stats:
                perf = stats['performance']
                print(f"\n📈 Performance:")
                print(f"   Total Trading: {perf.get('total_trades', 0)}")
                print(f"   Rata-rata Profit: {perf.get('avg_profit_percent', 0):.2f}%")
                print(f"   Trading Menang: {perf.get('winning_trades', 0)}")
                print(f"   Trading Kalah: {perf.get('losing_trades', 0)}")
                
                if perf.get('total_trades', 0) > 0:
                    win_rate = (perf.get('winning_trades', 0) / perf.get('total_trades', 0)) * 100
                    print(f"   Win Rate: {win_rate:.1f}%")
        else:
            print(f"❌ Gagal: {response.get('message')}")
    
    def change_password(self):
        """Ganti password admin"""
        print("\n🔐 Ganti Password Admin")
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
    
    def test_connection(self):
        """Test koneksi ke server"""
        print("\n🔗 Testing koneksi ke server...")
        
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(3)
            test_socket.connect((self.server_host, self.server_port))
            test_socket.close()
            print("✅ Koneksi berhasil!")
            
            # Test dengan ping request
            request = {
                'client_type': 'admin',
                'password': self.password,
                'action': 'get_stats'
            }
            
            # Coba kirim request sederhana
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.server_host, self.server_port))
            sock.send(json.dumps(request).encode('utf-8'))
            
            # Coba terima response kecil
            data = sock.recv(1024)
            sock.close()
            
            if data:
                print("✅ Server merespons dengan baik!")
            else:
                print("⚠️  Server tidak merespons dengan data")
                
        except socket.timeout:
            print("❌ Timeout: Server tidak merespons")
        except ConnectionRefusedError:
            print("❌ Tidak dapat terhubung ke server")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def menu(self):
        """Menu utama"""
        while True:
            print("\n" + "="*60)
            print("👨‍💼 ADMIN TRADING SIGNAL (with TP)")
            print("="*60)
            print(f"Server: {self.server_host}:{self.server_port}")
            print(f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-"*60)
            print("1. 📤 Kirim Signal Trading (with TP)")
            print("2. 📊 Lihat History Signal")
            print("3. 📈 Lihat Statistik Sistem")
            print("4. 🔐 Ganti Password")
            print("5. 🔗 Test Koneksi")
            print("6. 🚪 Keluar")
            print("="*60)
            
            choice = input("Pilihan [1-6]: ").strip()
            
            if choice == '1':
                self.send_signal()
            elif choice == '2':
                self.get_history()
            elif choice == '3':
                self.get_statistics()
            elif choice == '4':
                self.change_password()
            elif choice == '5':
                self.test_connection()
            elif choice == '6':
                print("\n👋 Keluar dari Admin Client...")
                break
            else:
                print("❌ Pilihan tidak valid!")
            
            input("\n↵ Tekan Enter untuk kembali ke menu...")

if __name__ == "__main__":
    print("🚀 Starting Admin Trading Signal Client (with TP)...")
    print("="*50)
    
    # Konfigurasi server
    server_host = input(f"Server host [localhost]: ").strip() or 'localhost'
    server_port = input(f"Server port [9999]: ").strip() or '9999'
    
    try:
        server_port = int(server_port)
    except ValueError:
        print("❌ Port harus angka! Menggunakan port 9999")
        server_port = 9999
    
    client = AdminClient(server_host=server_host, server_port=server_port)
    client.menu()