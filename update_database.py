#!/usr/bin/env python3
"""
Update database structure for API Key Management
"""
import sqlite3
import json
import os

def update_database():
    print("🔄 Updating database for enhanced features...")
    
    db_name = 'trading_signals.db'
    
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # 1. Add user tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_type TEXT NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT
            )
        ''')
        
        # 2. Add API Key audit log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_key_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_type TEXT NOT NULL,
                action TEXT NOT NULL,
                old_key_hash TEXT,
                new_key_hash TEXT,
                changed_by TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT
            )
        ''')
        
        # 3. Add user activity log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_type TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 4. Update signals table for better tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                sl REAL NOT NULL,
                tp REAL NOT NULL,
                type TEXT NOT NULL,
                admin_id TEXT NOT NULL,
                admin_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                risk_reward_ratio REAL,
                expected_profit REAL,
                expected_loss REAL
            )
        ''')
        
        # Copy data from old signals table if exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
        if cursor.fetchone():
            cursor.execute('''
                INSERT INTO signals_new 
                (signal_id, symbol, price, sl, tp, type, admin_id, admin_address, created_at, expires_at, status)
                SELECT signal_id, symbol, price, sl, tp, type, admin_id, admin_address, created_at, expires_at, status
                FROM signals
            ''')
            cursor.execute("DROP TABLE signals")
        
        cursor.execute("ALTER TABLE signals_new RENAME TO signals")
        
        # 5. Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_status ON signals(status, expires_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions ON user_sessions(user_id, user_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_deliveries ON signal_deliveries(signal_id, customer_id)')
        
        conn.commit()
        conn.close()
        
        print("✅ Database updated successfully")
        print("   • Added user sessions tracking")
        print("   • Added API Key audit log")
        print("   • Added user activity log")
        print("   • Enhanced signals table")
        print("   • Created performance indexes")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        
        # Fallback: Create basic database if doesn't exist
        try:
            if not os.path.exists(db_name):
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()
                
                # Basic signals table
                cursor.execute('''
                    CREATE TABLE signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id TEXT UNIQUE,
                        symbol TEXT NOT NULL,
                        price REAL NOT NULL,
                        sl REAL NOT NULL,
                        tp REAL NOT NULL,
                        type TEXT NOT NULL,
                        admin_id TEXT NOT NULL,
                        admin_address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        status TEXT DEFAULT 'active'
                    )
                ''')
                
                conn.commit()
                conn.close()
                print("✅ Created basic database structure")
        except:
            print("⚠️  Could not create database")

if __name__ == "__main__":
    update_database()