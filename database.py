"""
Database module for Trading Signal Server v2.1
ENHANCED: Removed user_stats table - User management uses JSON files
FIXED: No circular imports, better error handling
"""

import sqlite3
import json
from datetime import datetime, timedelta
import time
import os
import threading

class SignalDatabase:
    def __init__(self, db_path='signals.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.lock = threading.Lock()
        self.setup_database()
    
    def setup_database(self):
        """Setup database tables - VERSION 2.1: NO user_stats table"""
        with self.lock:
            try:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.cursor = self.conn.cursor()
                
                # Enable foreign keys
                self.cursor.execute('PRAGMA foreign_keys = ON')
                
                # ========== CREATE TABLES - NO user_stats ==========
                
                # Signals table
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id TEXT UNIQUE,
                        symbol TEXT NOT NULL,
                        price REAL NOT NULL,
                        sl REAL NOT NULL,
                        tp REAL NOT NULL,
                        type TEXT NOT NULL CHECK (type IN ('buy', 'sell')),
                        admin_address TEXT,
                        admin_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        status TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
                        delivery_count INTEGER DEFAULT 0,
                        pnl REAL DEFAULT 0,
                        closed_at TIMESTAMP,
                        notes TEXT
                    )
                ''')
                
                # Signal deliveries table
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS signal_deliveries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id TEXT,
                        customer_id TEXT,
                        delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'delivered',
                        FOREIGN KEY (signal_id) REFERENCES signals (signal_id) ON DELETE CASCADE,
                        UNIQUE(signal_id, customer_id)
                    )
                ''')
                
                # Client connections table
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS client_connections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_type TEXT,
                        client_id TEXT,
                        address TEXT,
                        connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        disconnected_at TIMESTAMP,
                        duration_seconds INTEGER,
                        session_id TEXT,
                        request_count INTEGER DEFAULT 1
                    )
                ''')
                
                # Admin activities table
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admin_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id TEXT,
                        action TEXT NOT NULL,
                        details TEXT,
                        ip_address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Customer activities table
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS customer_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id TEXT,
                        action TEXT NOT NULL,
                        details TEXT,
                        ip_address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # System logs table
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        level TEXT NOT NULL,
                        module TEXT,
                        message TEXT NOT NULL,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # ❌❌❌ PERHATIAN: user_stats table TIDAK DIBUAT ❌❌❌
                print("ℹ️  Database v2.1 initialized: User management uses JSON files")
                print("   - Authentication: api_keys_secure.json")
                print("   - User status: user_status.json")
                
                self.conn.commit()
                
                # ========== UPGRADE EXISTING DATABASE ==========
                self._safe_upgrade_database()
                
                # ========== CREATE INDEXES SAFELY ==========
                self._safe_create_indexes()
                
                print(f"✅ Database v2.1 initialized: {self.db_path}")
                
            except Exception as e:
                error_msg = f"Database setup error: {e}"
                print(f"❌ {error_msg}")
                import traceback
                traceback.print_exc()
                if self.conn:
                    self.conn.rollback()
    
    def _safe_upgrade_database(self):
        """Safely upgrade existing database schema"""
        try:
            # Check all tables and add missing columns
            self._add_missing_columns('signals', [
                ('expires_at', 'TIMESTAMP'),
                ('pnl', 'REAL DEFAULT 0'),
                ('closed_at', 'TIMESTAMP'),
                ('notes', 'TEXT')
            ])
            
            self._add_missing_columns('signal_deliveries', [
                ('status', 'TEXT DEFAULT "delivered"')
            ])
            
            self._add_missing_columns('client_connections', [
                ('client_id', 'TEXT'),
                ('session_id', 'TEXT'),
                ('request_count', 'INTEGER DEFAULT 1')
            ])
            
            # ❌ PERHATIAN: Jika ada tabel user_stats, beri warning
            if self._table_exists('user_stats'):
                print("⚠️  WARNING: 'user_stats' table exists but will not be used")
                print("   User management has been moved to JSON files")
            
            self.conn.commit()
            print("✅ Database upgrade completed")
            
        except Exception as e:
            print(f"⚠️ Database upgrade warning: {e}")
    
    def _add_missing_columns(self, table_name, columns):
        """Add missing columns to a table"""
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = [col[1] for col in self.cursor.fetchall()]
            
            for column_name, column_def in columns:
                if column_name not in existing_columns:
                    try:
                        self.cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}')
                        print(f"➕ Added column '{column_name}' to {table_name} table")
                    except Exception as e:
                        print(f"⚠️ Could not add column '{column_name}' to {table_name}: {e}")
        except Exception as e:
            print(f"⚠️ Error checking columns for {table_name}: {e}")
    
    def _safe_create_indexes(self):
        """Safely create indexes"""
        try:
            # Only create indexes after tables are confirmed to exist
            indexes = [
                ('idx_signals_status', 'signals(status)'),
                ('idx_signals_expires', 'signals(expires_at)'),
                ('idx_deliveries_signal', 'signal_deliveries(signal_id)'),
                ('idx_deliveries_customer', 'signal_deliveries(customer_id)'),
                ('idx_admin_activities_admin', 'admin_activities(admin_id)'),
                ('idx_admin_activities_time', 'admin_activities(created_at)'),
                ('idx_customer_activities_customer', 'customer_activities(customer_id)'),
                ('idx_customer_activities_time', 'customer_activities(created_at)'),
                ('idx_client_connections_time', 'client_connections(connected_at)'),
            ]
            
            # ❌ TIDAK ADA index untuk user_stats
            print("ℹ️  Creating indexes (no user_stats indexes needed)")
            
            for idx_name, idx_def in indexes:
                try:
                    # Check if table exists
                    table_name = idx_def.split('(')[0]
                    if self._table_exists(table_name):
                        self.cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}')
                        print(f"🔍 Created index '{idx_name}'")
                    else:
                        print(f"⚠️ Skipping index '{idx_name}' - table '{table_name}' doesn't exist")
                except Exception as e:
                    print(f"⚠️ Could not create index '{idx_name}': {e}")
                    
        except Exception as e:
            print(f"⚠️ Create indexes warning: {e}")
    
    def _table_exists(self, table_name):
        """Check if table exists"""
        try:
            self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            return self.cursor.fetchone() is not None
        except:
            return False
    
    def log_system(self, level, module, message, details=None):
        """Log system messages"""
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT INTO system_logs (level, module, message, details)
                    VALUES (?, ?, ?, ?)
                ''', (level, module, message, json.dumps(details) if details else None))
                self.conn.commit()
            except Exception as e:
                print(f"❌ Error logging system message: {e}")
    
    def add_signal(self, symbol, price, sl, tp, signal_type, admin_address, admin_id, expiry_minutes=5):
        """Add new trading signal"""
        with self.lock:
            try:
                # Generate unique signal ID
                timestamp = int(time.time())
                signal_id = f"SIG_{timestamp}_{symbol}"
                expires_at = datetime.now() + timedelta(minutes=expiry_minutes)
                
                self.cursor.execute('''
                    INSERT INTO signals (signal_id, symbol, price, sl, tp, type, admin_address, admin_id, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (signal_id, symbol, price, sl, tp, signal_type, admin_address, admin_id, expires_at))
                
                self.conn.commit()
                print(f"✅ Signal added: {signal_id}")
                return signal_id
                
            except Exception as e:
                error_msg = f"Error adding signal: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
                return None
    
    def mark_signal_sent(self, signal_id, customer_id, customer_address=""):
        """Mark signal as sent to customer"""
        with self.lock:
            try:
                # Check if already delivered
                self.cursor.execute('''
                    SELECT id FROM signal_deliveries 
                    WHERE signal_id = ? AND customer_id = ?
                ''', (signal_id, customer_id))
                
                if not self.cursor.fetchone():
                    # Add delivery record
                    self.cursor.execute('''
                        INSERT INTO signal_deliveries (signal_id, customer_id)
                        VALUES (?, ?)
                    ''', (signal_id, customer_id))
                    
                    # Update signal delivery count
                    self.cursor.execute('''
                        UPDATE signals 
                        SET delivery_count = delivery_count + 1 
                        WHERE signal_id = ?
                    ''', (signal_id,))
                    
                    self.conn.commit()
                    return True
                    
            except Exception as e:
                error_msg = f"Error marking signal sent: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
            
            return False
    
    def get_signal_history(self, limit=50, admin_id=None, status=None):
        """Get signal history with filters"""
        with self.lock:
            try:
                query = '''
                    SELECT 
                        id, signal_id, symbol, price, sl, tp, type, 
                        admin_id, created_at, expires_at, status, delivery_count,
                        pnl, closed_at, notes
                    FROM signals 
                '''
                params = []
                
                where_clauses = []
                if admin_id:
                    where_clauses.append('admin_id = ?')
                    params.append(admin_id)
                if status:
                    where_clauses.append('status = ?')
                    params.append(status)
                
                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)
                
                query += ' ORDER BY created_at DESC LIMIT ?'
                params.append(limit)
                
                self.cursor.execute(query, params)
                rows = self.cursor.fetchall()
                
                signals = []
                for row in rows:
                    signals.append({
                        'id': row[0],
                        'signal_id': row[1],
                        'symbol': row[2],
                        'price': row[3],
                        'sl': row[4],
                        'tp': row[5],
                        'type': row[6],
                        'admin_id': row[7],
                        'created_at': row[8],
                        'expires_at': row[9],
                        'status': row[10],
                        'delivery_count': row[11],
                        'pnl': row[12],
                        'closed_at': row[13],
                        'notes': row[14]
                    })
                
                return signals
                
            except Exception as e:
                error_msg = f"Error getting signal history: {e}"
                print(f"❌ {error_msg}")
                return []
    
    def expire_old_signals(self):
        """Expire old signals"""
        with self.lock:
            try:
                self.cursor.execute('''
                    UPDATE signals 
                    SET status = 'expired' 
                    WHERE expires_at <= datetime('now') 
                    AND status = 'active'
                ''')
                
                expired_count = self.cursor.rowcount
                if expired_count > 0:
                    print(f"✅ Expired {expired_count} signals")
                
                self.conn.commit()
                return expired_count
                
            except Exception as e:
                error_msg = f"Error expiring signals: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
                return 0
    
    def get_statistics(self):
        """Get comprehensive database statistics"""
        with self.lock:
            try:
                stats = {}
                
                # Get signal stats
                self.cursor.execute('SELECT COUNT(*) FROM signals')
                stats['total_signals'] = self.cursor.fetchone()[0]
                
                self.cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'active'")
                stats['active_signals'] = self.cursor.fetchone()[0]
                
                self.cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'expired'")
                stats['expired_signals'] = self.cursor.fetchone()[0]
                
                # Get delivery stats
                self.cursor.execute('SELECT COUNT(*) FROM signal_deliveries')
                stats['total_deliveries'] = self.cursor.fetchone()[0]
                
                # Get connection stats
                self.cursor.execute('SELECT COUNT(*) FROM client_connections')
                stats['total_connections'] = self.cursor.fetchone()[0]
                
                # Get recent activity stats
                self.cursor.execute('''
                    SELECT COUNT(*) FROM admin_activities 
                    WHERE created_at >= datetime('now', '-1 day')
                ''')
                stats['admin_activities_24h'] = self.cursor.fetchone()[0]
                
                self.cursor.execute('''
                    SELECT COUNT(*) FROM customer_activities 
                    WHERE created_at >= datetime('now', '-1 day')
                ''')
                stats['customer_activities_24h'] = self.cursor.fetchone()[0]
                
                # ❌ PERHATIAN: Tidak ada stats untuk users (pakai JSON)
                stats['user_management'] = 'via_json_files'
                
                stats['available'] = True
                stats['timestamp'] = datetime.now().isoformat()
                return stats
                
            except Exception as e:
                error_msg = f"Error getting statistics: {e}"
                print(f"❌ {error_msg}")
                return {'available': False, 'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def add_client_connection(self, client_type, address, client_id=None, session_id=None):
        """Add client connection record"""
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT INTO client_connections (client_type, client_id, address, session_id)
                    VALUES (?, ?, ?, ?)
                ''', (client_type, client_id, address, session_id))
                self.conn.commit()
                return self.cursor.lastrowid
                
            except Exception as e:
                error_msg = f"Error adding client connection: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
                return None
    
    def update_client_disconnect(self, address):
        """Update client disconnect time"""
        with self.lock:
            try:
                # Find the latest connection for this address
                self.cursor.execute('''
                    SELECT id, connected_at FROM client_connections 
                    WHERE address = ? AND disconnected_at IS NULL
                    ORDER BY connected_at DESC 
                    LIMIT 1
                ''', (address,))
                
                row = self.cursor.fetchone()
                if row:
                    conn_id, connected_at = row
                    disconnected_at = datetime.now()
                    
                    # Parse connected_at if it's string
                    if isinstance(connected_at, str):
                        try:
                            connected_dt = datetime.strptime(connected_at, '%Y-%m-%d %H:%M:%S')
                        except:
                            connected_dt = disconnected_at
                    else:
                        connected_dt = connected_at
                    
                    duration = (disconnected_at - connected_dt).total_seconds()
                    
                    self.cursor.execute('''
                        UPDATE client_connections 
                        SET disconnected_at = ?, duration_seconds = ? 
                        WHERE id = ?
                    ''', (disconnected_at, int(duration), conn_id))
                    
                    self.conn.commit()
                
            except Exception as e:
                error_msg = f"Error updating disconnect: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
    
    def log_admin_activity(self, admin_id, action, details="", ip_address=""):
        """Log admin activity for auditing"""
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT INTO admin_activities (admin_id, action, details, ip_address)
                    VALUES (?, ?, ?, ?)
                ''', (admin_id, action, details, ip_address))
                
                self.conn.commit()
                return True
                
            except Exception as e:
                error_msg = f"Error logging admin activity: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
                return False
    
    def get_admin_activities(self, limit=20, admin_id=None, days_back=7):
        """Get admin activities log with filters"""
        with self.lock:
            try:
                query = '''
                    SELECT 
                        admin_id, action, details, ip_address, created_at
                    FROM admin_activities
                    WHERE created_at >= datetime('now', ?)
                '''
                params = [f'-{days_back} days']
                
                if admin_id:
                    query += ' AND admin_id = ?'
                    params.append(admin_id)
                
                query += ' ORDER BY created_at DESC LIMIT ?'
                params.append(limit)
                
                self.cursor.execute(query, params)
                rows = self.cursor.fetchall()
                
                activities = []
                for row in rows:
                    activities.append({
                        'admin_id': row[0],
                        'action': row[1],
                        'details': row[2],
                        'ip': row[3],
                        'timestamp': row[4]
                    })
                
                return activities
                
            except Exception as e:
                error_msg = f"Error getting admin activities: {e}"
                print(f"❌ {error_msg}")
                return []
    
    def fix_database_issues(self):
        """Fix any database issues and ensure all tables exist"""
        with self.lock:
            try:
                print("🔧 Checking and fixing database issues...")
                
                # First upgrade existing tables
                self._safe_upgrade_database()
                
                # Then create indexes
                self._safe_create_indexes()
                
                # ❌ Jika ada tabel user_stats, beri warning tapi jangan hapus
                if self._table_exists('user_stats'):
                    print("⚠️  WARNING: 'user_stats' table exists but is not used")
                    print("   User management is handled by JSON files")
                    print("   You can safely ignore this table")
                
                self.conn.commit()
                print("✅ Database issues fixed")
                return True
                
            except Exception as e:
                error_msg = f"Error fixing database: {e}"
                print(f"❌ {error_msg}")
                if self.conn:
                    self.conn.rollback()
                return False
    
    def get_active_signals(self):
        """Get all active signals"""
        with self.lock:
            try:
                self.cursor.execute('''
                    SELECT 
                        signal_id, symbol, price, sl, tp, type, admin_id,
                        created_at, expires_at, delivery_count
                    FROM signals 
                    WHERE status = 'active' 
                    ORDER BY created_at DESC
                ''')
                
                rows = self.cursor.fetchall()
                signals = []
                for row in rows:
                    signals.append({
                        'signal_id': row[0],
                        'symbol': row[1],
                        'price': row[2],
                        'sl': row[3],
                        'tp': row[4],
                        'type': row[5],
                        'admin_id': row[6],
                        'created_at': row[7],
                        'expires_at': row[8],
                        'delivery_count': row[9]
                    })
                
                return signals
                
            except Exception as e:
                error_msg = f"Error getting active signals: {e}"
                print(f"❌ {error_msg}")
                return []
    
    def close(self):
        """Close database connection"""
        with self.lock:
            try:
                if self.conn:
                    self.conn.close()
                    print("✅ Database connection closed")
            except:
                pass

# Singleton instance
database = SignalDatabase()