import os
import sqlite3

# --- INFRASTRUCTURE ---
# Only absolutely necessary paths for the application to start
# and find its database file. These are not saved in DB as they depend on the file system.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "logs", "daa_memory.db")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')

def get_config():
    """
    Fetches configuration only from the database.
    Contains no hardcoded user settings.
    """
    # Create logs folder if it doesn't exist (for first run)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Bootstrapping: Create table if it doesn't exist
    # This ensures the app starts even if the database is completely new/empty.
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    # 2. Fetch settings from DB
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    
    # Convert to dictionary
    config = {row["key"]: row["value"] for row in rows}
    
    conn.close()
    
    # 3. Add system paths (these should not be edited in GUI)
    config["DB_PATH"] = DB_PATH
    config["SERVICE_ACCOUNT_FILE"] = SERVICE_ACCOUNT_FILE
    
    # 4. Type conversion
    # If values exist in DB, ensure they have the correct type for Python code
    try:
        if config.get("HISTORY_LIMIT"):
            config["HISTORY_LIMIT"] = int(config["HISTORY_LIMIT"])
        if config.get("MQTT_PORT"):
            config["MQTT_PORT"] = int(config["MQTT_PORT"])
    except: 
        pass
    
    # 5. Set default user ID if not configured
    if not config.get("USER_ID"):
        config["USER_ID"] = "Anders"

    return config