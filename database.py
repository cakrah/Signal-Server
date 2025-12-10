import sqlite3
import json
from datetime import datetime
from threading import Lock
import os
import time
import traceback

class SignalDatabase:
    def __init__(self, db_file='signals.db'):
        self.db_file = db_file
        self.global_lock = Lock()
        self.connection_lock = Lock()
        self.init_database()
    
    def get_connection(self):
        """Get database connection with row factory and timeout"""
        with self.connection_lock:
            conn = sqlite3.connect(self.db_file, check_same_thread=False, timeout=30.0)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
            return conn
    
    def migrate_database(self):
        """Migrate existing database to new schema"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Cek apakah perlu migrasi
            cursor.execute("PRAGMA table_info(clients)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Cek constraint di clients table
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='clients'")
            table_sql = cursor.fetchone()
            
            if table_sql and 'CHECK(client_type IN (\'admin\', \'customer\'))' in table_sql[0]:
                print("⚠️  Old database schema detected, migrating...")
                
                # Backup old data
                cursor.execute("SELECT * FROM clients")
                old_clients = cursor.fetchall()
                
                # Drop old table
                cursor.execute("DROP TABLE IF EXISTS clients_old")
                cursor.execute("ALTER TABLE clients RENAME TO clients_old")
                
                # Create new table dengan schema yang benar
                cursor.execute('''
                    CREATE TABLE clients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_type TEXT NOT NULL CHECK(client_type IN ('admin', 'customer', 'unknown')),
                        client_id TEXT,
                        address TEXT NOT NULL,
                        connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_activity DATETIME,
                        status TEXT DEFAULT 'connected' CHECK(status IN ('connected', 'disconnected'))
                    )
                ''')
                
                # Insert old data dengan fix client_type
                for client in old_clients:
                    client_type = client[1] if client[1] in ['admin', 'customer', 'unknown'] else 'unknown'
                    cursor.execute('''
                        INSERT INTO clients (id, client_type, client_id, address, connected_at, last_activity, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (client[0], client_type, client[2], client[3], client[4], client[5], client[6]))
                
                print("✅ Clients table migrated successfully")
            
            # Cek dan migrasi signals table jika perlu
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='signals'")
            signals_sql = cursor.fetchone()
            
            if signals_sql:
                # Cek constraint untuk expiry_minutes
                if 'expiry_minutes INTEGER DEFAULT 5' in signals_sql[0] and 'NOT NULL' not in signals_sql[0]:
                    print("⚠️  Migrating signals table...")
                    
                    # Backup signals data
                    cursor.execute("SELECT * FROM signals")
                    old_signals = cursor.fetchall()
                    
                    # Drop old table
                    cursor.execute("DROP TABLE IF EXISTS signals_old")
                    cursor.execute("ALTER TABLE signals RENAME TO signals_old")
                    
                    # Create new table
                    cursor.execute('''
                        CREATE TABLE signals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            symbol TEXT NOT NULL,
                            price REAL NOT NULL,
                            sl REAL NOT NULL,
                            tp REAL NOT NULL,
                            type TEXT NOT NULL CHECK(type IN ('buy', 'sell')),
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            expiry_minutes INTEGER DEFAULT 5 NOT NULL,
                            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'expired', 'executed')),
                            sent_to_customers BOOLEAN DEFAULT 0 NOT NULL,
                            admin_address TEXT,
                            profit REAL,
                            notes TEXT
                        )
                    ''')
                    
                    # Insert old data
                    for signal in old_signals:
                        cursor.execute('''
                            INSERT INTO signals (id, symbol, price, sl, tp, type, timestamp, 
                                               expiry_minutes, status, sent_to_customers, 
                                               admin_address, profit, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, 5), COALESCE(?, 'active'), 
                                    COALESCE(?, 0), ?, ?, ?)
                        ''', signal)
                    
                    print("✅ Signals table migrated successfully")
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            print(f"❌ Migration error: {e}")
            traceback.print_exc()
        finally:
            try:
                conn.close()
            except:
                pass
    
    def init_database(self):
        """Initialize database tables with TP - dengan migration"""
        with self.global_lock:
            # Jalankan migration terlebih dahulu
            self.migrate_database()
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            try:
                # Signals table with TP - dengan NOT NULL constraints
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        price REAL NOT NULL,
                        sl REAL NOT NULL,
                        tp REAL NOT NULL,
                        type TEXT NOT NULL CHECK(type IN ('buy', 'sell')),
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        expiry_minutes INTEGER DEFAULT 5 NOT NULL,
                        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'expired', 'executed')),
                        sent_to_customers BOOLEAN DEFAULT 0 NOT NULL,
                        admin_address TEXT,
                        profit REAL,
                        notes TEXT
                    )
                ''')
                
                # Clients table - perbolehkan 'unknown' sebagai client_type
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS clients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_type TEXT NOT NULL CHECK(client_type IN ('admin', 'customer', 'unknown')),
                        client_id TEXT,
                        address TEXT NOT NULL,
                        connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_activity DATETIME,
                        status TEXT DEFAULT 'connected' CHECK(status IN ('connected', 'disconnected'))
                    )
                ''')
                
                # Signal history table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS signal_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id INTEGER,
                        action TEXT NOT NULL,
                        details TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (signal_id) REFERENCES signals (id)
                    )
                ''')
                
                # Performance table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id INTEGER,
                        entry_price REAL,
                        exit_price REAL,
                        pnl REAL,
                        pnl_percent REAL,
                        duration_minutes INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (signal_id) REFERENCES signals (id)
                    )
                ''')
                
                # Customer signal tracking table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS customer_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id TEXT NOT NULL,
                        signal_id INTEGER NOT NULL,
                        received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_new BOOLEAN DEFAULT 1,
                        FOREIGN KEY (signal_id) REFERENCES signals (id),
                        UNIQUE(customer_id, signal_id)
                    )
                ''')
                
                # Buat index untuk performa lebih baik
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_address ON clients(address)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_customer_signals_composite ON customer_signals(customer_id, signal_id)')
                
                conn.commit()
                print(f"✅ Database initialized with TP support: {self.db_file}")
                
            except sqlite3.Error as e:
                print(f"❌ Database initialization error: {e}")
                traceback.print_exc()
                raise
            finally:
                try:
                    conn.close()
                except:
                    pass
    
    def fix_database_issues(self):
        """Fix potential database issues"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # FIX 1: Pastikan semua signals memiliki expiry_minutes default
            cursor.execute('''
                UPDATE signals 
                SET expiry_minutes = 5 
                WHERE expiry_minutes IS NULL OR expiry_minutes = ''
            ''')
            
            fixed_null = cursor.rowcount
            if fixed_null > 0:
                print(f"✅ Fixed {fixed_null} signals with NULL/empty expiry_minutes")
            
            # FIX 2: Pastikan status ada dan valid
            cursor.execute('''
                UPDATE signals 
                SET status = 'expired'
                WHERE status IS NULL 
                AND datetime(timestamp, '+' || CAST(COALESCE(expiry_minutes, 5) AS TEXT) || ' minutes') < datetime('now')
            ''')
            
            cursor.execute('''
                UPDATE signals 
                SET status = 'active'
                WHERE status IS NULL 
                AND datetime(timestamp, '+' || CAST(COALESCE(expiry_minutes, 5) AS TEXT) || ' minutes') >= datetime('now')
            ''')
            
            fixed_status = cursor.rowcount
            if fixed_status > 0:
                print(f"✅ Fixed {fixed_status} signals with NULL status")
            
            # FIX 3: Update sent_to_customers jika NULL
            cursor.execute('''
                UPDATE signals 
                SET sent_to_customers = 0 
                WHERE sent_to_customers IS NULL
            ''')
            
            # FIX 4: Update client_type yang 'unknown' untuk existing records
            cursor.execute('''
                UPDATE clients 
                SET client_type = 'unknown'
                WHERE client_type IS NULL OR client_type NOT IN ('admin', 'customer', 'unknown')
            ''')
            
            conn.commit()
            conn.close()
            
            print("✅ Database fixes applied")
            
        except sqlite3.Error as e:
            print(f"❌ Error fixing database: {e}")
            traceback.print_exc()
        except Exception as e:
            print(f"❌ Unexpected error fixing database: {e}")
            traceback.print_exc()
        finally:
            try:
                conn.close()
            except:
                pass
    
    def add_client_connection(self, client_type, address, client_id=None):
        """Add client connection to database - SAFE VERSION"""
        try:
            # Validate and sanitize client_type
            if client_type not in ['admin', 'customer', 'unknown']:
                client_type = 'unknown'
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Coba INSERT dengan client_type yang valid
            cursor.execute('''
                INSERT INTO clients (client_type, client_id, address, status)
                VALUES (?, ?, ?, 'connected')
            ''', (client_type, client_id, address))
            
            conn.commit()
            conn.close()
            
        except sqlite3.IntegrityError as e:
            # Jika constraint error, coba dengan 'unknown'
            if 'CHECK constraint failed' in str(e):
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO clients (client_type, client_id, address, status)
                        VALUES ('unknown', ?, ?, 'connected')
                    ''', (client_id, address))
                    conn.commit()
                    conn.close()
                    print(f"⚠️  Fixed client_type constraint for {address}")
                except:
                    pass
            else:
                print(f"⚠️  Database integrity error: {e}")
        except sqlite3.Error as e:
            print(f"⚠️  Error adding client connection: {e}")
        except Exception as e:
            print(f"⚠️  Unexpected error in add_client_connection: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
    
    def add_signal(self, symbol, price, sl, tp, signal_type, admin_address, expiry_minutes=5):
        """Add new signal to database with TP"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Pastikan expiry_minutes valid
                if not expiry_minutes or expiry_minutes <= 0:
                    expiry_minutes = 5
                
                cursor.execute('''
                    INSERT INTO signals 
                    (symbol, price, sl, tp, type, admin_address, expiry_minutes, status, sent_to_customers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, price, sl, tp, signal_type, admin_address, expiry_minutes, 'active', 0))
                
                signal_id = cursor.lastrowid
                
                # Add to history
                cursor.execute('''
                    INSERT INTO signal_history (signal_id, action, details)
                    VALUES (?, ?, ?)
                ''', (signal_id, 'CREATED', f'Signal created: {symbol} {signal_type} at {price}, SL: {sl}, TP: {tp}'))
                
                conn.commit()
                conn.close()
                
                print(f"✅ Signal added to database: ID={signal_id}, {symbol} {signal_type} at {price}")
                return signal_id
                
            except sqlite3.OperationalError as e:
                retry_count += 1
                if "database is locked" in str(e) and retry_count < max_retries:
                    print(f"⚠️  Database locked, retrying ({retry_count}/{max_retries})...")
                    time.sleep(0.1 * retry_count)  # Exponential backoff
                    continue
                else:
                    print(f"❌ Failed to add signal after {max_retries} retries: {e}")
                    raise
            except Exception as e:
                print(f"❌ Error adding signal: {e}")
                traceback.print_exc()
                raise
            finally:
                try:
                    conn.close()
                except:
                    pass
    
    def get_active_signal(self):
        """Get current active signal"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Cari signal yang active dan belum expired
            cursor.execute('''
                SELECT * FROM signals 
                WHERE status = 'active' 
                AND datetime(timestamp, '+' || CAST(COALESCE(expiry_minutes, 5) AS TEXT) || ' minutes') >= datetime('now')
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            
            signal = cursor.fetchone()
            conn.close()
            
            if signal:
                return dict(signal)
            return None
            
        except sqlite3.Error as e:
            print(f"❌ Error getting active signal: {e}")
            traceback.print_exc()
            return None
        finally:
            try:
                conn.close()
            except:
                pass
    
    def mark_signal_sent(self, signal_id, customer_id=None):
        """Mark signal as sent to customers"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Update sent flag
            cursor.execute('''
                UPDATE signals 
                SET sent_to_customers = 1 
                WHERE id = ?
            ''', (signal_id,))
            
            # Add to history
            cursor.execute('''
                INSERT INTO signal_history (signal_id, action, details)
                VALUES (?, ?, ?)
            ''', (signal_id, 'SENT', f'Signal sent to customers{customer_id if customer_id else ""}'))
            
            # Jika ada customer_id, simpan tracking
            if customer_id:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO customer_signals (customer_id, signal_id, is_new)
                        VALUES (?, ?, 1)
                    ''', (customer_id, signal_id))
                except:
                    pass  # Ignore jika gagal, tidak critical
            
            conn.commit()
            conn.close()
            
            print(f"✅ Signal marked as sent: ID={signal_id}")
            
        except sqlite3.Error as e:
            print(f"⚠️  Error marking signal as sent: {e}")
        except Exception as e:
            print(f"⚠️  Unexpected error marking signal: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
    
    def expire_old_signals(self):
        """Mark old signals as expired - FIXED VERSION"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Gunakan COALESCE untuk handle NULL expiry_minutes
            cursor.execute('''
                UPDATE signals 
                SET status = 'expired' 
                WHERE status = 'active' 
                AND datetime(timestamp, '+' || CAST(COALESCE(expiry_minutes, 5) AS TEXT) || ' minutes') < datetime('now')
            ''')
            
            expired_count = cursor.rowcount
            
            if expired_count > 0:
                # Add to history
                cursor.execute('''
                    INSERT INTO signal_history (signal_id, action, details)
                    SELECT id, 'EXPIRED', 'Signal expired automatically'
                    FROM signals 
                    WHERE status = 'expired' 
                    AND datetime(timestamp, '+' || CAST(COALESCE(expiry_minutes, 5) AS TEXT) || ' minutes') < datetime('now')
                ''')
            
            conn.commit()
            conn.close()
            
            if expired_count > 0:
                print(f"✅ {expired_count} signals expired")
            
            return expired_count
                
        except sqlite3.Error as e:
            print(f"⚠️  Error expiring signals: {e}")
            traceback.print_exc()
            return 0
        except Exception as e:
            print(f"⚠️  Unexpected error in expire_old_signals: {e}")
            traceback.print_exc()
            return 0
        finally:
            try:
                conn.close()
            except:
                pass
    
    def get_signal_history(self, limit=50):
        """Get signal history"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.*, 
                       COUNT(sh.id) as history_count,
                       COUNT(DISTINCT cs.customer_id) as customer_count
                FROM signals s
                LEFT JOIN signal_history sh ON s.id = sh.signal_id
                LEFT JOIN customer_signals cs ON s.id = cs.signal_id
                GROUP BY s.id
                ORDER BY s.timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            signals = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return signals
            
        except sqlite3.Error as e:
            print(f"❌ Error getting signal history: {e}")
            return []
        finally:
            try:
                conn.close()
            except:
                pass
    
    def update_client_disconnect(self, address):
        """Update client status to disconnected"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE clients 
                SET status = 'disconnected', last_activity = datetime('now')
                WHERE address = ?
            ''', (address,))
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            print(f"⚠️  Error updating client disconnect: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
    
    def get_connected_clients(self):
        """Get currently connected clients"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) as count FROM clients 
                WHERE status = 'connected'
            ''')
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
            
        except sqlite3.Error as e:
            print(f"❌ Error getting connected clients: {e}")
            return 0
        finally:
            try:
                conn.close()
            except:
                pass
    
    def get_statistics(self):
        """Get system statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Total signals
            cursor.execute("SELECT COUNT(*) FROM signals")
            stats['total_signals'] = cursor.fetchone()[0]
            
            # Today's signals
            cursor.execute("""
                SELECT COUNT(*) FROM signals 
                WHERE date(timestamp) = date('now')
            """)
            stats['today_signals'] = cursor.fetchone()[0]
            
            # Active signals
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'active'")
            stats['active_signals'] = cursor.fetchone()[0]
            
            # Expired signals
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'expired'")
            stats['expired_signals'] = cursor.fetchone()[0]
            
            # Buy vs Sell ratio
            cursor.execute("""
                SELECT type, COUNT(*) as count 
                FROM signals 
                GROUP BY type
            """)
            stats['buy_sell_ratio'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Total customers served
            cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM customer_signals")
            stats['total_customers'] = cursor.fetchone()[0]
            
            # Signal delivery stats
            cursor.execute("""
                SELECT COUNT(*) as total_deliveries, 
                       COUNT(DISTINCT signal_id) as unique_signals_delivered
                FROM customer_signals
            """)
            delivery_stats = cursor.fetchone()
            stats['delivery_stats'] = {
                'total_deliveries': delivery_stats[0] if delivery_stats[0] else 0,
                'unique_signals_delivered': delivery_stats[1] if delivery_stats[1] else 0
            }
            
            # Performance summary
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(pnl_percent) as avg_profit_percent,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades
                FROM performance
            """)
            perf = cursor.fetchone()
            stats['performance'] = {
                'total_trades': perf[0] if perf[0] else 0,
                'avg_profit_percent': perf[1] if perf[1] else 0,
                'winning_trades': perf[2] if perf[2] else 0,
                'losing_trades': perf[3] if perf[3] else 0
            }
            
            # Connection stats
            cursor.execute("SELECT COUNT(*) FROM clients")
            stats['total_connections'] = cursor.fetchone()[0]
            
            conn.close()
            return stats
            
        except sqlite3.Error as e:
            print(f"❌ Error getting statistics: {e}")
            traceback.print_exc()
            return {
                'total_signals': 0,
                'today_signals': 0,
                'active_signals': 0,
                'expired_signals': 0,
                'buy_sell_ratio': {},
                'total_customers': 0,
                'delivery_stats': {
                    'total_deliveries': 0,
                    'unique_signals_delivered': 0
                },
                'performance': {
                    'total_trades': 0,
                    'avg_profit_percent': 0,
                    'winning_trades': 0,
                    'losing_trades': 0
                },
                'total_connections': 0,
                'error': True
            }
        finally:
            try:
                conn.close()
            except:
                pass
    
    def get_customer_signal_history(self, customer_id, limit=20):
        """Get signal history for specific customer"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.*, cs.received_at, cs.is_new
                FROM signals s
                JOIN customer_signals cs ON s.id = cs.signal_id
                WHERE cs.customer_id = ?
                ORDER BY cs.received_at DESC
                LIMIT ?
            ''', (customer_id, limit))
            
            signals = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return signals
            
        except sqlite3.Error as e:
            print(f"❌ Error getting customer history: {e}")
            return []
        finally:
            try:
                conn.close()
            except:
                pass
    
    def has_customer_received_signal(self, customer_id, signal_id):
        """Check if customer has already received a specific signal"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) as count 
                FROM customer_signals 
                WHERE customer_id = ? AND signal_id = ?
            ''', (customer_id, signal_id))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except sqlite3.Error as e:
            print(f"❌ Error checking customer signal: {e}")
            return False
        finally:
            try:
                conn.close()
            except:
                pass
    
    def reset_customer_signal(self, customer_id, signal_id):
        """Reset customer signal tracking (allow to receive again)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM customer_signals 
                WHERE customer_id = ? AND signal_id = ?
            ''', (customer_id, signal_id))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted > 0:
                print(f"✅ Reset signal {signal_id} for customer {customer_id}")
                return True
            return False
            
        except sqlite3.Error as e:
            print(f"❌ Error resetting customer signal: {e}")
            return False
        finally:
            try:
                conn.close()
            except:
                pass
    
    def cleanup_old_data(self, days_to_keep=30):
        """Cleanup old data from database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Cleanup old signals
            cursor.execute('''
                DELETE FROM signals 
                WHERE timestamp < datetime('now', ?)
            ''', (f'-{days_to_keep} days',))
            
            signals_deleted = cursor.rowcount
            
            # Cleanup old connections
            cursor.execute('''
                DELETE FROM clients 
                WHERE connected_at < datetime('now', ?)
            ''', (f'-{days_to_keep} days',))
            
            clients_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            print(f"✅ Cleanup: {signals_deleted} old signals, {clients_deleted} old connections")
            return signals_deleted + clients_deleted
            
        except sqlite3.Error as e:
            print(f"❌ Error cleaning up old data: {e}")
            return 0
        finally:
            try:
                conn.close()
            except:
                pass

# Singleton instance
database = SignalDatabase()

if __name__ == "__main__":
    # Test database
    print("Testing database connection with TP support...")
    db = SignalDatabase()
    
    # Add test signal with TP
    signal_id = db.add_signal(
        symbol="TEST",
        price=100.0,
        sl=95.0,
        tp=110.0,
        signal_type="buy",
        admin_address="test:1234"
    )
    
    # Get active signal
    signal = db.get_active_signal()
    print(f"Active signal: {signal}")
    
    # Get statistics
    stats = db.get_statistics()
    print(f"Statistics: {stats}")
    
    # Get history
    history = db.get_signal_history()
    print(f"History count: {len(history)}")
    
    # Test expire
    expired = db.expire_old_signals()
    print(f"Expired signals: {expired}")
    
    print("✅ Database test completed successfully!")