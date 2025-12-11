#!/usr/bin/env python3
"""
Backup database for Trading System
"""

import sqlite3
import os
import shutil
import sys
from datetime import datetime
import gzip
import json

def backup_database():
    """Backup database to backup directory"""
    
    # Configuration
    db_path = os.environ.get('DB_PATH', 'signals.db')
    backup_dir = os.environ.get('DB_BACKUP_DIR', 'backups')
    retention_days = int(os.environ.get('DB_BACKUP_RETENTION_DAYS', 7))
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Create backup directory
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"✅ Created backup directory: {backup_dir}")
    
    # Generate backup filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'signals_{timestamp}.db.gz')
    backup_file_json = os.path.join(backup_dir, f'signals_{timestamp}.json.gz')
    
    try:
        # 1. Backup database file (compressed)
        print(f"📦 Creating backup: {backup_file}")
        
        with open(db_path, 'rb') as f_in:
            with gzip.open(backup_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 2. Create JSON backup for easy inspection
        print(f"📄 Creating JSON backup: {backup_file_json}")
        create_json_backup(db_path, backup_file_json)
        
        # 3. Create backup manifest
        manifest = {
            'backup_time': datetime.now().isoformat(),
            'database_size': os.path.getsize(db_path),
            'backup_size': os.path.getsize(backup_file),
            'database_path': db_path,
            'backup_files': [backup_file, backup_file_json]
        }
        
        manifest_file = os.path.join(backup_dir, f'manifest_{timestamp}.json')
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # 4. Clean old backups
        clean_old_backups(backup_dir, retention_days)
        
        print("✅ Backup completed successfully!")
        
        # Log backup activity
        log_backup_activity(manifest)
        
        return True
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_json_backup(db_path, output_file):
    """Create JSON backup of database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    backup_data = {
        'backup_time': datetime.now().isoformat(),
        'tables': {}
    }
    
    for table in tables:
        table_name = table['name']
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Convert rows to dict
        table_data = []
        for row in rows:
            table_data.append(dict(row))
        
        backup_data['tables'][table_name] = {
            'count': len(table_data),
            'data': table_data
        }
    
    conn.close()
    
    # Write compressed JSON
    json_str = json.dumps(backup_data, indent=2, default=str)
    with gzip.open(output_file, 'wt', encoding='utf-8') as f:
        f.write(json_str)

def clean_old_backups(backup_dir, retention_days):
    """Clean backups older than retention days"""
    import time
    
    now = time.time()
    cutoff = now - (retention_days * 24 * 60 * 60)
    
    deleted_count = 0
    for filename in os.listdir(backup_dir):
        filepath = os.path.join(backup_dir, filename)
        
        # Skip if not a backup file
        if not (filename.startswith('signals_') or filename.startswith('manifest_')):
            continue
        
        # Check file age
        if os.path.getmtime(filepath) < cutoff:
            try:
                os.remove(filepath)
                print(f"🗑️  Deleted old backup: {filename}")
                deleted_count += 1
            except Exception as e:
                print(f"⚠️  Could not delete {filename}: {e}")
    
    if deleted_count > 0:
        print(f"✅ Cleaned {deleted_count} old backups")

def log_backup_activity(manifest):
    """Log backup activity to database"""
    try:
        db_path = os.environ.get('DB_PATH', 'signals.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO system_logs (level, module, message, details)
            VALUES (?, ?, ?, ?)
        ''', ('INFO', 'backup', 'Database backup created', 
              json.dumps(manifest)))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"⚠️  Could not log backup activity: {e}")

def restore_backup(backup_file):
    """Restore database from backup"""
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        return False
    
    db_path = os.environ.get('DB_PATH', 'signals.db')
    
    # Backup current database first
    if os.path.exists(db_path):
        temp_backup = f"{db_path}.backup"
        shutil.copy2(db_path, temp_backup)
        print(f"📦 Created temporary backup: {temp_backup}")
    
    try:
        # Restore from compressed backup
        print(f"🔄 Restoring from: {backup_file}")
        
        with gzip.open(backup_file, 'rb') as f_in:
            with open(db_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print("✅ Restore completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        
        # Restore from temporary backup
        if os.path.exists(temp_backup):
            print("🔄 Restoring from temporary backup...")
            shutil.copy2(temp_backup, db_path)
            print("✅ Restored from temporary backup")
        
        return False

def list_backups(backup_dir):
    """List all available backups"""
    if not os.path.exists(backup_dir):
        print(f"❌ Backup directory not found: {backup_dir}")
        return
    
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith('manifest_'):
            manifest_file = os.path.join(backup_dir, filename)
            try:
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    backups.append(manifest)
            except:
                pass
    
    if not backups:
        print("📭 No backups found")
        return
    
    print("📋 Available Backups:")
    print("=" * 80)
    for i, backup in enumerate(backups, 1):
        print(f"{i}. Time: {backup['backup_time']}")
        print(f"   Size: {backup['backup_size']:,} bytes")
        print(f"   Files: {', '.join(backup['backup_files'])}")
        print("-" * 80)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Backup Utility')
    parser.add_argument('--backup', action='store_true', help='Create backup')
    parser.add_argument('--restore', type=str, help='Restore from backup file')
    parser.add_argument('--list', action='store_true', help='List backups')
    parser.add_argument('--dir', type=str, default='backups', help='Backup directory')
    
    args = parser.parse_args()
    
    if args.backup:
        os.environ['DB_BACKUP_DIR'] = args.dir
        success = backup_database()
        sys.exit(0 if success else 1)
    
    elif args.restore:
        success = restore_backup(args.restore)
        sys.exit(0 if success else 1)
    
    elif args.list:
        list_backups(args.dir)
    
    else:
        # Default: create backup
        success = backup_database()
        sys.exit(0 if success else 1)