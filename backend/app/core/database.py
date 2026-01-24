import sqlite3
import os
from config.settings import DB_PATH

# VIKTIGT: Vi definierar standardvärdet här istället för att importera det
# Detta löser kraschen "cannot import name HISTORY_LIMIT"
DEFAULT_HISTORY_LIMIT = 600 

def init_db():
    """Skapar databasen och tabellerna om de inte finns."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Tabell för historik
        c.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                image TEXT, 
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabell för inställningar
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Databas initierad: {DB_PATH}")
    except Exception as e:
        print(f"❌ Databasfel vid initiering: {e}")

def save_message(session_id, role, content, image=None):
    """Sparar ett meddelande i historiken."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO history (session_id, role, content, image) VALUES (?, ?, ?, ?)",
                  (session_id, role, content, image))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Kunde inte spara till DB: {e}")

def get_history(session_id=None, limit=DEFAULT_HISTORY_LIMIT):
    """
    Hämtar konversationshistorik.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = f"""
            SELECT role, content, image 
            FROM (
                SELECT * FROM history 
                ORDER BY id DESC 
                LIMIT ?
            ) 
            ORDER BY id ASC
        """
        
        c.execute(query, (limit,))
        rows = c.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"]}
            if row["image"]: 
                msg["image"] = row["image"]
            history.append(msg)
            
        return history
    except Exception as e:
        print(f"⚠️ Kunde inte hämta historik: {e}")
        return []

def get_db_settings():
    """Hämtar alla sparade inställningar som en dictionary."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT key, value FROM settings")
        rows = c.fetchall()
        conn.close()
        
        settings = {}
        for row in rows:
            settings[row["key"]] = row["value"]
        return settings
    except Exception as e:
        print(f"⚠️ Kunde inte hämta inställningar: {e}")
        return {}

def save_db_setting(key, value):
    """Sparar eller uppdaterar en inställning."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Kunde inte spara inställning {key}: {e}")
        return False