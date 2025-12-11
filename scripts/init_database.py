#!/usr/bin/env python3
"""
Initialize database for Trading System
VERSION: 2.1 - REMOVED user_stats table (using JSON files instead)
"""

import sqlite3
import os
import json
import sys
from datetime import datetime
import hashlib

def init_database():
    """Initialize database with required tables"""
    # Get database path from environment or use default
    db_path = os.environ.get('DB_PATH', 'signals.db')
    
    print(f"📁 Database path: {db_path}")
    print(f"📂 Current directory: {os.getcwd()}")
    
    # Create directory if doesn't exist
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"✅ Created directory: {db_dir}")
    
    # Check if database already exists
    if os.path.exists(db_path):
        print("📊 Database already exists, checking structure...")
        
        # Verify database structure
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            
            # ✅ user_stats TIDAK LAGI DIPERLUKAN
            required_tables = ['signals', 'signal_deliveries', 'admin_activities', 'system_logs']
            missing_tables = [t for t in required_tables if t not in table_names]
            
            if missing_tables:
                print(f"⚠️  Missing tables: {missing_tables}")
                print("🔧 Adding missing tables...")
                create_tables(cursor)
            else:
                print("✅ Database structure is complete")
                
                # ⚠️ Check if user_stats exists and warn
                if 'user_stats' in table_names:
                    print("⚠️  WARNING: 'user_stats' table found but will not be used")
                    print("   User management uses JSON files, not database")
                
        except Exception as e:
            print(f"⚠️  Error checking database: {e}")
            print("🔧 Recreating database...")
            create_tables(cursor)
            
        finally:
            conn.commit()
            conn.close()
            
        return
    
    print("💾 Creating new database...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign keys and WAL mode for better performance
    cursor.execute('PRAGMA foreign_keys = ON')
    cursor.execute('PRAGMA journal_mode = WAL')
    cursor.execute('PRAGMA synchronous = NORMAL')
    
    # Create tables
    create_tables(cursor)
    
    # Insert default data
    insert_default_data(cursor)
    
    conn.commit()
    conn.close()
    
    print("✅ Database initialized successfully!")
    
    # Initialize API keys file
    init_api_keys_file()

def create_tables(cursor):
    """Create all required tables - VERSION 2.1: NO user_stats table"""
    
    # Signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT UNIQUE NOT NULL,
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
            notes TEXT,
            INDEX idx_signals_status (status),
            INDEX idx_signals_expires (expires_at),
            INDEX idx_signals_admin (admin_id)
        )
    ''')
    print("✅ Created 'signals' table")
    
    # Signal deliveries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'delivered',
            FOREIGN KEY (signal_id) REFERENCES signals (signal_id) ON DELETE CASCADE,
            UNIQUE(signal_id, customer_id),
            INDEX idx_deliveries_signal (signal_id),
            INDEX idx_deliveries_customer (customer_id),
            INDEX idx_deliveries_time (delivered_at)
        )
    ''')
    print("✅ Created 'signal_deliveries' table")
    
    # Admin activities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_admin_activities_admin (admin_id),
            INDEX idx_admin_activities_time (created_at)
        )
    ''')
    print("✅ Created 'admin_activities' table")
    
    # System logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            module TEXT,
            message TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_system_logs_level (level),
            INDEX idx_system_logs_time (created_at)
        )
    ''')
    print("✅ Created 'system_logs' table")
    
    # Client connections table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_type TEXT,
            client_id TEXT,
            address TEXT,
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            disconnected_at TIMESTAMP,
            duration_seconds INTEGER,
            session_id TEXT,
            request_count INTEGER DEFAULT 1,
            INDEX idx_client_connections_time (connected_at),
            INDEX idx_client_connections_client (client_id)
        )
    ''')
    print("✅ Created 'client_connections' table")
    
    # ❌❌❌ PERHATIAN: user_stats table TIDAK DIBUAT LAGI ❌❌❌
    # User management menggunakan file JSON: api_keys_secure.json dan user_status.json
    print("ℹ️  User management menggunakan file JSON, bukan database table")
    print("   - api_keys_secure.json untuk authentication")
    print("   - user_status.json untuk status management")

def insert_default_data(cursor):
    """Insert default data into database"""
    
    # Insert initial system log
    cursor.execute('''
        INSERT INTO system_logs (level, module, message, details)
        VALUES (?, ?, ?, ?)
    ''', ('INFO', 'database', 'Database initialized v2.1 (no user_stats table)', 
          json.dumps({'version': '2.1', 'timestamp': datetime.now().isoformat()})))
    
    # Insert default admin activity
    cursor.execute('''
        INSERT INTO admin_activities (admin_id, action, details)
        VALUES (?, ?, ?)
    ''', ('SYSTEM', 'init_database', 'Database initialized - User management via JSON files'))
    
    print("✅ Inserted default data")

def init_api_keys_file():
    """Initialize API keys file if it doesn't exist"""
    api_keys_file = 'api_keys_secure.json'
    user_status_file = 'user_status.json'
    
    # Create API keys file
    if not os.path.exists(api_keys_file):
        default_keys = {
            "admins": {},
            "customers": {}
        }
        with open(api_keys_file, 'w') as f:
            json.dump(default_keys, f, indent=2)
        print(f"✅ Created {api_keys_file}")
    
    # Create user status file
    if not os.path.exists(user_status_file):
        default_status = {
            "admins": {},
            "customers": {}
        }
        with open(user_status_file, 'w') as f:
            json.dump(default_status, f, indent=2)
        print(f"✅ Created {user_status_file}")
    
    print("⚠️  IMPORTANT: User management uses JSON files, NOT database")
    print("   To add admin user: python scripts/add_admin.py --admin-id ADMIN_001 --api-key your-key")

if __name__ == '__main__':
    try:
        init_database()
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)