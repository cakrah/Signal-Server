"""
User Stats Helper - Menggantikan fungsi user_stats table dengan JSON + Database
"""

import json
import os
from datetime import datetime
import sqlite3

class UserStatsHelper:
    def __init__(self, db_path='signals.db'):
        self.db_path = db_path
        self.api_keys_file = 'api_keys_secure.json'
        self.user_status_file = 'user_status.json'
    
    def load_user_data(self):
        """Load semua user data dari JSON files"""
        data = {
            'api_keys': {},
            'user_status': {}
        }
        
        try:
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r') as f:
                    data['api_keys'] = json.load(f)
        except Exception as e:
            print(f"Error loading API keys: {e}")
        
        try:
            if os.path.exists(self.user_status_file):
                with open(self.user_status_file, 'r') as f:
                    data['user_status'] = json.load(f)
        except Exception as e:
            print(f"Error loading user status: {e}")
        
        return data
    
    def get_customer_stats(self, customer_id):
        """Get comprehensive stats for customer"""
        stats = {
            'customer_id': customer_id,
            'delivery_stats': {},
            'connection_stats': {},
            'account_info': {}
        }
        
        try:
            # Load user data
            data = self.load_user_data()
            
            # Get account info from JSON
            stats['account_info'] = data['user_status'].get('customers', {}).get(customer_id, {})
            
            # Get delivery stats from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delivery stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_deliveries,
                    MIN(delivered_at) as first_delivery,
                    MAX(delivered_at) as last_delivery
                FROM signal_deliveries 
                WHERE customer_id = ?
            ''', (customer_id,))
            
            delivery_row = cursor.fetchone()
            if delivery_row:
                stats['delivery_stats'] = {
                    'total_deliveries': delivery_row[0],
                    'first_delivery': delivery_row[1],
                    'last_delivery': delivery_row[2]
                }
            
            # Connection stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as connection_count,
                    MAX(connected_at) as last_seen
                FROM client_connections 
                WHERE client_id = ? AND client_type = 'customer'
            ''', (customer_id,))
            
            conn_row = cursor.fetchone()
            if conn_row:
                stats['connection_stats'] = {
                    'connection_count': conn_row[0],
                    'last_seen': conn_row[1]
                }
            
            conn.close()
            
        except Exception as e:
            print(f"Error getting customer stats: {e}")
        
        return stats
    
    def get_admin_stats(self, admin_id):
        """Get comprehensive stats for admin"""
        stats = {
            'admin_id': admin_id,
            'signal_stats': {},
            'connection_stats': {},
            'account_info': {}
        }
        
        try:
            # Load user data
            data = self.load_user_data()
            
            # Get account info from JSON
            stats['account_info'] = data['user_status'].get('admins', {}).get(admin_id, {})
            
            # Get signal stats from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Signal stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_signals,
                    MIN(created_at) as first_signal,
                    MAX(created_at) as last_signal
                FROM signals 
                WHERE admin_id = ?
            ''', (admin_id,))
            
            signal_row = cursor.fetchone()
            if signal_row:
                stats['signal_stats'] = {
                    'total_signals': signal_row[0],
                    'first_signal': signal_row[1],
                    'last_signal': signal_row[2]
                }
            
            # Connection stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as connection_count,
                    MAX(connected_at) as last_seen
                FROM client_connections 
                WHERE client_id = ? AND client_type = 'admin'
            ''', (admin_id,))
            
            conn_row = cursor.fetchone()
            if conn_row:
                stats['connection_stats'] = {
                    'connection_count': conn_row[0],
                    'last_seen': conn_row[1]
                }
            
            conn.close()
            
        except Exception as e:
            print(f"Error getting admin stats: {e}")
        
        return stats