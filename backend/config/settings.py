import os
import sqlite3

# --- INFRASTRUKTUR ---
# Endast absolut nödvändiga sökvägar för att applikationen ska kunna starta
# och hitta sin databasfil. Dessa sparas inte i DB då de är beroende av filsystemet.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "logs", "daa_memory.db")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')

def get_config():
    """
    Hämtar konfiguration enbart från databasen.
    Innehåller inga hårdkodade användarinställningar.
    """
    # Skapa mappen logs om den inte finns (för första körningen)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Bootstrapping: Skapa tabellen om den inte finns
    # Detta gör att appen startar även om databasen är helt ny/tom.
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    
    # 2. Hämta inställningar från DB
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    
    # Konvertera till dictionary
    config = {row["key"]: row["value"] for row in rows}
    
    conn.close()
    
    # 3. Lägg till system-sökvägar (dessa ska inte editeras i GUI)
    config["DB_PATH"] = DB_PATH
    config["SERVICE_ACCOUNT_FILE"] = SERVICE_ACCOUNT_FILE
    
    # 4. Typkonvertering
    # Om värdena finns i DB, se till att de har rätt typ för Python-koden
    try:
        if config.get("HISTORY_LIMIT"):
            config["HISTORY_LIMIT"] = int(config["HISTORY_LIMIT"])
        if config.get("MQTT_PORT"):
            config["MQTT_PORT"] = int(config["MQTT_PORT"])
    except: 
        pass

    return config