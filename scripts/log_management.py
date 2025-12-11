#!/usr/bin/env python3
"""
Log management for Trading System
"""

import os
import glob
import gzip
import json
from datetime import datetime, timedelta
import shutil

def rotate_logs():
    """Rotate and compress old logs"""
    
    log_dir = os.environ.get('LOG_DIR', 'logs')
    retention_days = int(os.environ.get('LOG_RETENTION_DAYS', 30))
    rotation_size = os.environ.get('LOG_ROTATION_SIZE', '10MB')
    
    if not os.path.exists(log_dir):
        print(f"❌ Log directory not found: {log_dir}")
        return
    
    # Convert rotation size to bytes
    size_map = {'KB': 1024, 'MB': 1024*1024, 'GB': 1024*1024*1024}
    rotation_bytes = 10 * 1024 * 1024  # Default 10MB
    
    if rotation_size:
        num = int(''.join(filter(str.isdigit, rotation_size)))
        unit = ''.join(filter(str.isalpha, rotation_size)).upper()
        rotation_bytes = num * size_map.get(unit, 1024*1024)
    
    # Find log files
    log_patterns = [
        '*.log',
        '*.log.*',  # Already rotated logs
        'trading_server_*.log',
        'admin_api_*.log',
        'customer_api_*.log'
    ]
    
    rotated_count = 0
    deleted_count = 0
    
    for pattern in log_patterns:
        for log_file in glob.glob(os.path.join(log_dir, pattern)):
            # Skip already compressed files
            if log_file.endswith('.gz'):
                continue
            
            file_size = os.path.getsize(log_file)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
            file_age = datetime.now() - file_mtime
            
            # Rotate if file is too large
            if file_size > rotation_bytes:
                rotate_file(log_file)
                rotated_count += 1
            
            # Delete if too old
            elif file_age.days > retention_days:
                os.remove(log_file)
                print(f"🗑️  Deleted old log: {os.path.basename(log_file)}")
                deleted_count += 1
    
    # Clean old compressed logs
    for gz_file in glob.glob(os.path.join(log_dir, '*.log.*.gz')):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(gz_file))
        file_age = datetime.now() - file_mtime
        
        if file_age.days > retention_days:
            os.remove(gz_file)
            deleted_count += 1
    
    if rotated_count > 0 or deleted_count > 0:
        print(f"✅ Log rotation completed: {rotated_count} rotated, {deleted_count} deleted")
    else:
        print("📝 No logs needed rotation")

def rotate_file(log_file):
    """Rotate a single log file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    rotated_file = f"{log_file}.{timestamp}"
    
    try:
        # Rename current log file
        shutil.move(log_file, rotated_file)
        
        # Create new empty log file
        open(log_file, 'w').close()
        
        # Compress rotated file
        with open(rotated_file, 'rb') as f_in:
            with gzip.open(f"{rotated_file}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove uncompressed rotated file
        os.remove(rotated_file)
        
        print(f"🔄 Rotated: {os.path.basename(log_file)} -> {os.path.basename(rotated_file)}.gz")
        
    except Exception as e:
        print(f"❌ Error rotating {log_file}: {e}")

def analyze_logs():
    """Analyze logs for errors and statistics"""
    
    log_dir = os.environ.get('LOG_DIR', 'logs')
    
    if not os.path.exists(log_dir):
        print(f"❌ Log directory not found: {log_dir}")
        return
    
    print("📊 Log Analysis Report")
    print("=" * 80)
    
    # Analyze each log file
    for log_file in glob.glob(os.path.join(log_dir, '*.log')):
        if os.path.getsize(log_file) == 0:
            continue
        
        print(f"\n📄 File: {os.path.basename(log_file)}")
        print("-" * 40)
        
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            error_lines = [l for l in lines if 'ERROR' in l or 'error' in l]
            warning_lines = [l for l in lines if 'WARNING' in l or 'warning' in l]
            
            print(f"Total lines: {total_lines:,}")
            print(f"Errors: {len(error_lines):,}")
            print(f"Warnings: {len(warning_lines):,}")
            
            if error_lines:
                print("\n🔴 Recent Errors:")
                for error in error_lines[-5:]:  # Last 5 errors
                    print(f"  • {error.strip()}")
                    
        except Exception as e:
            print(f"⚠️  Could not analyze: {e}")
    
    print("=" * 80)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Log Management Utility')
    parser.add_argument('--rotate', action='store_true', help='Rotate logs')
    parser.add_argument('--analyze', action='store_true', help='Analyze logs')
    parser.add_argument('--clean', action='store_true', help='Clean old logs')
    
    args = parser.parse_args()
    
    if args.rotate:
        rotate_logs()
    elif args.analyze:
        analyze_logs()
    elif args.clean:
        # Just delete old logs
        retention_days = int(os.environ.get('LOG_RETENTION_DAYS', 30))
        log_dir = os.environ.get('LOG_DIR', 'logs')
        clean_old_logs(log_dir, retention_days)
    else:
        # Default: rotate and analyze
        rotate_logs()
        print("\n")
        analyze_logs()