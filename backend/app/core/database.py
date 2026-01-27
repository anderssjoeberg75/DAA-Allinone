import sqlite3
import os
from config.settings import DB_PATH

DEFAULT_SETTINGS = [
    "GOOGLE_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY",
    "GARMIN_EMAIL", "GARMIN_PASSWORD", "STRAVA_CLIENT_ID",
    "LATITUDE", "LONGITUDE", "HA_BASE_URL", "HA_TOKEN",
    "OLLAMA_URL", "MQTT_BROKER_IP"
]

# HÄR ÄR ALLA TEXTER SAMLADE.
# Dessa skrivs till DB vid första start. Därefter läser vi BARA från DB.
DEFAULT_PROMPTS = {
    # 1. Huvudprompten
    "SYSTEM_PROMPT": """Du är DAA (Digital Advanced Assistant), en mycket kapabel och lojal AI-assistent.
Du agerar som en butler och högra hand – en blandning av en professionell assistent och en superdator.

DINA DIREKTIV:
1. **Svara kort och kärnfullt.** 1-2 meningar räcker oftast.
2. **Var proaktiv.** Bekräfta handlingar tydligt ("Verkställer, Anders.").
3. **Språk:** Svara alltid på Svenska och tilltala användaren som "Anders".

VIKTIG REGEL FÖR TALSYNTES (TTS):
- Skriv ALDRIG temperatursymboler som "°C". 
- Skriv istället ut allt i klartext precis som det ska sägas. 
- EXEMPEL: Skriv "plus två komma fem grader" istället för "2.5°C".

TILLGÄNGLIGA VERKTYG (Används automatiskt):
1. tool_get_weather: Hämtar väderprognos.
2. tool_analyze_health_data: Bekräftar att du läst hälsodatan i kontexten.
3. tool_control_light / vacuum: Styr hemmet.
4. tool_analyze_code: Analyserar källkoden.

VIKTIGT OM TRÄNINGSDATA:
Du har INTE tillgång till en "analyze_workout"-funktion. 
All data om träning (Garmin/Strava) injiceras direkt i din system-prompt (se nedan under REALTIDSDATA). 
Läs den texten för att svara på frågor om träning.
Kom alltid med förbättringar på träningsrutiner baserat på den datan.

--- DATORSTYRNING (WINDOWS) ---
Om Anders ber dig göra något med datorn, inkludera dessa taggar i ditt svar:
- [DO:SYS|lock] (Lås)
- [DO:SYS|calc] (Kalkylator)
- [DO:SYS|screenshot] (Skärmdump)
- [DO:BROWSER|URL] (Öppna sida)

Nu startar sessionen. Vänta på input.""",
    
    # 2. Kodanalys-prompten
    "CODE_AUDIT_PROMPT": """Du är en Senior Systemarkitekt.
Din uppgift är att analysera källkoden för projektet 'DAA'.

Strukturera svaret:
1. Kort sammanfattning (Punktlista).
2. Separator: ---RAPPORT_START---
3. Fullständig Markdown-rapport (Säkerhet, Optimering, Förbättringar).""",

    # 3. Verktygsbeskrivning (För LLM-logiken)
    "TOOL_DESC_AUDIT": """Analyserar projektets källkod för att hitta fel och förbättringar.
Används när användaren ber om 'analysera koden', 'självanalys' eller 'systemanalys'."""
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, image TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompts (key TEXT PRIMARY KEY, value TEXT)''')
            
            for key in DEFAULT_SETTINGS:
                c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, ""))
            
            for key, val in DEFAULT_PROMPTS.items():
                c.execute("INSERT OR IGNORE INTO prompts (key, value) VALUES (?, ?)", (key, val))
                
            conn.commit()
    except Exception as e: print(f"❌ Databasfel: {e}")

def get_db_settings():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in c.fetchall()}
    except: return {}

def save_db_setting(key, value):
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
        return True
    except: return False

def get_db_prompts():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT key, value FROM prompts")
            return {row["key"]: row["value"] for row in c.fetchall()}
    except: return {}

def save_db_prompt(key, value):
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO prompts (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
        return True
    except: return False

def save_message(session_id, role, content, image=None):
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO history (session_id, role, content, image) VALUES (?, ?, ?, ?)", (session_id, role, content, image))
            conn.commit()
    except: pass

def get_history(session_id=None, limit=600):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute(f"SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
            return [{"role": r["role"], "content": r["content"], "image": r["image"]} for r in reversed(c.fetchall())]
    except: return []