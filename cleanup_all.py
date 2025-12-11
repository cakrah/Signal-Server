#!/usr/bin/env python3
"""
Auto Cleanup for Production - Enhanced Version
"""

import os
import time
import glob
import shutil
from datetime import datetime, timedelta
import sys
import psutil  # pip install psutil (optional, untuk check file usage)

def safe_delete_file(filepath, max_retries=3):
    """Safely delete file with retry mechanism"""
    for attempt in range(max_retries):
        try:
            # Check if file exists and is accessible
            if not os.path.exists(filepath):
                return True
                
            # Check file size before deletion (for logging)
            file_size = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
            
            # Try to delete
            if os.path.isfile(filepath):
                os.remove(filepath)
            elif os.path.isdir(filepath):
                shutil.rmtree(filepath)
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Deleted: {os.path.basename(filepath)} "
                  f"({file_size/1024:.1f} KB)" if file_size > 0 else "")
            return True
                
        except PermissionError:
            # File might be in use, wait and retry
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            print(f"❌ Cannot delete {filepath} (file in use)")
            return False
        except Exception as e:
            print(f"❌ Error deleting {filepath}: {e}")
            return False
    return False

def cleanup_log_files(log_folder='logs', days_to_keep=7):
    """Cleanup log files older than X days"""
    try:
        if not os.path.exists(log_folder):
            os.makedirs(log_folder, exist_ok=True)
            print(f"📁 Created log folder: {log_folder}")
            return 0
        
        cutoff = time.time() - (days_to_keep * 86400)
        deleted = 0
        total_size = 0
        
        for filename in os.listdir(log_folder):
            if filename.endswith('.log'):
                filepath = os.path.join(log_folder, filename)
                
                # Skip current day's log
                if datetime.fromtimestamp(os.path.getmtime(filepath)).date() == datetime.now().date():
                    continue
                
                if os.path.getmtime(filepath) < cutoff:
                    file_size = os.path.getsize(filepath)
                    if safe_delete_file(filepath):
                        deleted += 1
                        total_size += file_size
        
        if deleted > 0:
            print(f"✅ Log cleanup: {deleted} files ({total_size/1024/1024:.2f} MB)")
        return deleted
        
    except Exception as e:
        print(f"❌ Log cleanup error: {e}")
        return 0

def cleanup_old_backups(days_to_keep=30):
    """Cleanup old backup files"""
    try:
        backup_folder = 'backup'
        if not os.path.exists(backup_folder):
            return 0
        
        cutoff = time.time() - (days_to_keep * 86400)
        deleted = 0
        
        patterns = [
            'api_keys_secure.json.*.bak',
            'user_status.json.*.bak',
            'signals_backup_*.db',
            'export_*.json'
        ]
        
        for pattern in patterns:
            for filepath in glob.glob(os.path.join(backup_folder, pattern)):
                try:
                    if os.path.getmtime(filepath) < cutoff:
                        if safe_delete_file(filepath):
                            deleted += 1
                except:
                    continue
        
        # Keep minimum 3 latest backups regardless of age
        for backup_type in ['api_keys_secure.json', 'user_status.json']:
            backups = sorted(glob.glob(os.path.join(backup_folder, f"{backup_type}.*.bak")), 
                           key=os.path.getmtime, reverse=True)
            for old_backup in backups[3:]:  # Keep only 3 latest
                if safe_delete_file(old_backup):
                    deleted += 1
        
        if deleted > 0:
            print(f"✅ Backup cleanup: {deleted} files")
        return deleted
        
    except Exception as e:
        print(f"❌ Backup cleanup error: {e}")
        return 0

def cleanup_signal_history(max_file_size_mb=10, days_to_keep=14):
    """Cleanup large or old signal history files"""
    try:
        deleted = 0
        
        # Pattern for signal history files
        patterns = [
            'signals_history_*.json',
            'signals_export_*.csv',
            'signal_report_*.json'
        ]
        
        for pattern in patterns:
            for filepath in glob.glob(pattern):
                try:
                    file_age = time.time() - os.path.getmtime(filepath)
                    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    
                    # Delete if too large OR too old
                    if file_size_mb > max_file_size_mb or file_age > (days_to_keep * 86400):
                        if safe_delete_file(filepath):
                            deleted += 1
                            print(f"  Deleted: {os.path.basename(filepath)} "
                                  f"({file_size_mb:.1f} MB, {int(file_age/86400)} days old)")
                except:
                    continue
        
        if deleted > 0:
            print(f"✅ Signal history cleanup: {deleted} files")
        return deleted
        
    except Exception as e:
        print(f"❌ Signal history cleanup error: {e}")
        return 0

def cleanup_temp_files():
    """Cleanup temporary files safely"""
    try:
        deleted = 0
        
        # Safer patterns - only target known temp locations
        temp_patterns = [
            '__pycache__',
            '*.pyc',
            '*.pyo',
            'temp_*.log',
            'session_*.tmp'
        ]
        
        for pattern in temp_patterns:
            for filepath in glob.glob(pattern, recursive=True):
                try:
                    # Skip if in important directories
                    if 'venv' in filepath or '.git' in filepath or 'node_modules' in filepath:
                        continue
                        
                    # For __pycache__, only delete if empty or old
                    if '__pycache__' in filepath:
                        if os.path.isdir(filepath):
                            # Check if directory is old (modified more than 1 day ago)
                            if time.time() - os.path.getmtime(filepath) > 86400:
                                if safe_delete_file(filepath):
                                    deleted += 1
                    else:
                        if safe_delete_file(filepath):
                            deleted += 1
                except:
                    continue
        
        if deleted > 0:
            print(f"✅ Temp files cleanup: {deleted} files")
        return deleted
        
    except Exception as e:
        print(f"❌ Temp files cleanup error: {e}")
        return 0

def check_disk_usage():
    """Check disk usage and trigger cleanup if needed"""
    try:
        # Get disk usage for current directory
        disk_usage = psutil.disk_usage('.')
        usage_percent = disk_usage.percent
        
        if usage_percent > 85:  # If disk usage > 85%
            print(f"⚠️  High disk usage: {usage_percent}% - Starting emergency cleanup")
            return True
        return False
    except:
        return False

def main():
    """Main cleanup service"""
    print("=" * 60)
    print("🔄 PRODUCTION CLEANUP SERVICE")
    print("=" * 60)
    print("Settings:")
    print("  • Log files: Keep 7 days")
    print("  • Backups: Keep 30 days (min 3 latest)")
    print("  • Signal files: >10MB OR >14 days")
    print("  • Temp files: Auto daily")
    print("  • Emergency cleanup: >85% disk usage")
    print("=" * 60)
    
    # Create necessary folders
    os.makedirs('logs', exist_ok=True)
    os.makedirs('backup', exist_ok=True)
    
    cleanup_count = 0
    last_full_cleanup = datetime.now() - timedelta(hours=25)  # Force first run
    
    while True:
        try:
            now = datetime.now()
            
            # Emergency cleanup (if disk usage high)
            emergency = check_disk_usage()
            
            # Full cleanup setiap 24 jam (atau emergency)
            if (now - last_full_cleanup).total_seconds() >= 86400 or emergency:
                print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🧹 STARTING CLEANUP {'(EMERGENCY)' if emergency else ''}")
                print("-" * 50)
                
                total_deleted = 0
                total_deleted += cleanup_log_files()
                total_deleted += cleanup_old_backups()
                total_deleted += cleanup_signal_history()
                total_deleted += cleanup_temp_files()
                
                print("-" * 50)
                print(f"[{now.strftime('%H:%M:%S')}] ✅ CLEANUP COMPLETED: {total_deleted} files")
                
                last_full_cleanup = now
                cleanup_count += 1
                
                # Jika emergency cleanup, tunggu 1 jam
                if emergency:
                    time.sleep(3600)
                else:
                    time.sleep(300)  # 5 menit setelah normal cleanup
            else:
                # Status update setiap 6 jam
                if now.hour % 6 == 0 and now.minute == 0:
                    hours_since = (now - last_full_cleanup).total_seconds() / 3600
                    print(f"[{now.strftime('%H:%M:%S')}] ⏰ Next cleanup in {24 - hours_since:.1f} hours")
                
                # Check every 15 minutes
                time.sleep(900)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Cleanup service stopped. Total cleanups: {cleanup_count}")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            time.sleep(300)  # Wait 5 minutes before retry

if __name__ == '__main__':
    # Simple command line interface
    if len(sys.argv) > 1 and sys.argv[1] == '--now':
        print("🚀 Running immediate cleanup...")
        cleanup_log_files()
        cleanup_old_backups()
        cleanup_signal_history()
        cleanup_temp_files()
    else:
        main()