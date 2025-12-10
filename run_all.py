import subprocess
import sys
import time
import os
import webbrowser
from threading import Thread

def run_command(title, command):
    """Run a command in new window"""
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'start "{title}" cmd /k "{command}"', shell=True)
        else:
            subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'{command}; exec bash'])
        print(f"✅ Started: {title}")
        return True
    except Exception as e:
        print(f"❌ Failed to start {title}: {e}")
        return False

def check_port(port):
    """Check if port is in use"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except:
        return False

def main():
    print("=" * 50)
    print("      TRADING SIGNAL SYSTEM - LAUNCHER")
    print("=" * 50)
    print()
    
    # Create directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Check ports
    print("🔍 Checking ports...")
    if check_port(9999):
        print("⚠️  Port 9999 already in use (Server)")
    if check_port(5000):
        print("⚠️  Port 5000 already in use (Web Dashboard)")
    
    print()
    print("🚀 Starting components...")
    print()
    
    # Start components
    components = [
        ("Trading Server", "python server.py"),
        ("Web Dashboard", "python web_dashboard.py"),
        ("Admin Client", "python admin_client.py"),
        ("Customer Client", "python customer_client.py"),
    ]
    
    for title, command in components:
        if run_command(title, command):
            time.sleep(2)  # Wait between starting components
    
    print()
    print("=" * 50)
    print("✅ SYSTEM STARTED SUCCESSFULLY!")
    print("=" * 50)
    print()
    print("📍 Access Points:")
    print("   • Web Dashboard: http://localhost:5000")
    print("   • Server: localhost:9999")
    print()
    print("📊 Files created:")
    print("   • signals.db - Database")
    print("   • logs/ - Log files directory")
    print("   • signals.log - Signal history")
    print()
    
    # Ask to open browser
    response = input("🌐 Open Web Dashboard in browser? (y/n): ").lower()
    if response == 'y':
        webbrowser.open('http://localhost:5000')
        print("✅ Opening browser...")
    
    print()
    print("📝 To stop: Close all terminal windows")
    print("=" * 50)

if __name__ == "__main__":
    main()