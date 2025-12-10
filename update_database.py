import sqlite3
import os

def update_database():
    """Add TP column to existing database"""
    
    db_file = 'signals.db'
    
    if not os.path.exists(db_file):
        print(f"❌ Database file '{db_file}' not found!")
        print("✅ No need to update, new database will be created automatically")
        return
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # Check if TP column exists
        cursor.execute("PRAGMA table_info(signals)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'tp' not in columns:
            print("Adding TP column to signals table...")
            cursor.execute("ALTER TABLE signals ADD COLUMN tp REAL DEFAULT 0")
            conn.commit()
            print("✅ TP column added successfully!")
            
            # Update existing records with default TP value
            cursor.execute("""
                UPDATE signals 
                SET tp = 
                    CASE 
                        WHEN type = 'buy' THEN price * 1.02
                        WHEN type = 'sell' THEN price * 0.98
                        ELSE price
                    END
                WHERE tp = 0 OR tp IS NULL
            """)
            updated = cursor.rowcount
            if updated > 0:
                print(f"✅ Updated {updated} records with default TP values")
        else:
            print("✅ TP column already exists in the database")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
    finally:
        conn.close()
    
    print("\n✅ Database update completed successfully!")

if __name__ == "__main__":
    print("=" * 60)
    print("       DATABASE UPDATE TOOL (for TP support)")
    print("=" * 60)
    print("This script will update your existing database to support TP")
    print("=" * 60)
    
    update_database()
    
    print("\n📝 Next steps:")
    print("1. Replace your existing Python files with the new versions")
    print("2. Restart the server and all clients")
    print("3. Enjoy TP support in your trading signals!")