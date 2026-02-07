import sqlite3
import os

DB_PATH = "/home/anderss/Documents/projects/daa/backend/logs/daa_memory.db"

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("\n--- SETTINGS ---")
    try:
        c.execute("SELECT * FROM settings")
        for row in c.fetchall():
            key = row['key']
            val = row['value']
            if "KEY" in key: val = "***"
            print(f"{key}: {val}")
    except Exception as e:
        print(f"Error reading settings: {e}")

    print("\n--- PROMPTS ---")
    try:
        c.execute("SELECT * FROM prompts")
        for row in c.fetchall():
            print(f"Key: {row['key']}")
            print(f"Value (first 200 chars): {row['value'][:200]}...")
            if "calendar" in row['value'].lower():
                print("⚠️  WARNING: 'calendar' found in prompt!")
    except Exception as e:
        print(f"Error reading prompts: {e}")

    conn.close()

if __name__ == "__main__":
    check_db()
