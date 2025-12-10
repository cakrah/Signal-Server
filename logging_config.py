import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime

def setup_logging(app_name='TradingSignal', log_dir=None):
    """
    Setup comprehensive logging system with cloud support
    """
    
    # === PERBAIKAN UNTUK CLOUD DEPLOYMENT ===
    if log_dir is None:
        # Gunakan environment variable jika ada
        log_dir = os.environ.get('LOG_DIR', 'logs')
    
    # Untuk cloud environments, gunakan /tmp jika logs/ tidak writable
    cloud_env = os.environ.get('RENDER') or os.environ.get('GAE_ENV') or os.environ.get('CLOUD_RUN') or os.environ.get('GOOGLE_CLOUD_PROJECT')
    
    if cloud_env:
        # Coba buat logs directory, jika gagal gunakan /tmp
        try:
            os.makedirs(log_dir, exist_ok=True)
            # Test write permission
            test_file = os.path.join(log_dir, 'test_write.log')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✅ Log directory {log_dir} is writable")
        except (PermissionError, OSError) as e:
            # Jika gagal, gunakan /tmp/logs
            log_dir = '/tmp/logs'
            os.makedirs(log_dir, exist_ok=True)
            print(f"⚠️  Using {log_dir} for logs (cloud environment: {cloud_env})")
    # ========================================
    
    # Create logs directory if not exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        print(f"📁 Created logs directory: {log_dir}")
    
    # Create logger
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Formatter untuk umum
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. Console Handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 2. File Handler for all logs (rotates by size)
    try:
        all_logs_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, 'trading_system.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        all_logs_handler.setLevel(logging.INFO)
        all_logs_handler.setFormatter(formatter)
    except Exception as e:
        print(f"⚠️  Could not create all_logs_handler: {e}")
        all_logs_handler = console_handler  # Fallback to console
    
    # 3. Error Handler (ERROR and above only)
    try:
        error_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, 'errors.log'),
            maxBytes=5*1024*1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
    except Exception as e:
        print(f"⚠️  Could not create error_handler: {e}")
        error_handler = console_handler  # Fallback to console
    
    # 4. Signal Handler (for trading signals only)
    try:
        signal_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, 'signals.log'),
            when='midnight',  # Rotate daily
            interval=1,
            backupCount=30,   # Keep 30 days
            encoding='utf-8'
        )
        signal_handler.setLevel(logging.INFO)
        signal_formatter = logging.Formatter(
            '%(asctime)s - SIGNAL - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        signal_handler.setFormatter(signal_formatter)
    except Exception as e:
        print(f"⚠️  Could not create signal_handler: {e}")
        signal_handler = console_handler  # Fallback to console
    
    # 5. Access Handler (for client connections)
    try:
        access_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, 'access.log'),
            maxBytes=5*1024*1024,
            backupCount=7,
            encoding='utf-8'
        )
        access_handler.setLevel(logging.INFO)
        access_formatter = logging.Formatter(
            '%(asctime)s - ACCESS - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        access_handler.setFormatter(access_formatter)
    except Exception as e:
        print(f"⚠️  Could not create access_handler: {e}")
        access_handler = console_handler  # Fallback to console
    
    # Add all handlers
    logger.addHandler(console_handler)
    logger.addHandler(all_logs_handler)
    logger.addHandler(error_handler)
    logger.addHandler(signal_handler)
    logger.addHandler(access_handler)
    
    # Create signal-specific logger
    signal_logger = logging.getLogger(f'{app_name}.Signals')
    signal_logger.addHandler(signal_handler)
    signal_logger.propagate = False
    
    # Create access-specific logger
    access_logger = logging.getLogger(f'{app_name}.Access')
    access_logger.addHandler(access_handler)
    access_logger.propagate = False
    
    print(f"✅ Logging system initialized. Logs directory: {log_dir}")
    print(f"   Log files: {os.listdir(log_dir) if os.path.exists(log_dir) else 'Directory not found'}")
    return logger, signal_logger, access_logger

def log_signal(signal_logger, action, **details):
    """Log trading signal activity"""
    log_data = {
        'action': action,
        'timestamp': datetime.now().isoformat(),
        **details
    }
    signal_logger.info(f"{action}: {log_data}")

def log_access(access_logger, client_type, address, action, **details):
    """Log client access"""
    log_data = {
        'client_type': client_type,
        'address': address,
        'action': action,
        'timestamp': datetime.now().isoformat(),
        **details
    }
    access_logger.info(f"{client_type} {action}: {log_data}")

# Usage example
if __name__ == "__main__":
    # Setup logging
    logger, signal_logger, access_logger = setup_logging()
    
    # Test logs
    logger.info("System started successfully")
    logger.warning("Test warning message")
    logger.error("Test error message")
    
    # Test signal logging
    log_signal(signal_logger, "SIGNAL_CREATED", 
               symbol="BTCUSD", price=50000, type="buy")
    
    # Test access logging
    log_access(access_logger, "admin", "127.0.0.1:1234", 
               "CONNECTED", user="admin1")
    
    print("✅ Logging test completed. Check logs/ directory.")