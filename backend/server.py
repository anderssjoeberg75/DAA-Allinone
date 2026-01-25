import sys
import io
import os
import asyncio
import socketio
import uvicorn
import time
import datetime
import requests
import json
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import google.generativeai as genai
from openai import OpenAI
from mem0 import AsyncMemoryClient

# --- UTF-8 FIX FÖR WINDOWS ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- KONFIGURATION ---
try:
    # Vi behåller din befintliga konfigurationshantering
    from config.settings import get_config
    CONFIG = get_config()
    print(f"[SYS] Configuration loaded from Database ({len(CONFIG)} keys).")
except Exception as e:
    print(f"[CRITICAL] Config Load Error: {e}")
    CONFIG = {}

# --- DATABAS & TJÄNSTER ---
try:
    from app.core.database import init_db, save_message, get_history, save_db_setting
    from app.services.llm_handler import stream_response 
    init_db() 
except Exception as e:
    print(f"[CRITICAL] Database Import Error: {e}")

# --- VERKTYG (TOOLS) ---
from app.tools.garmin_core import GarminCoach
from app.tools.strava_core import StravaTool
from app.tools.weather_core import get_weather
from app.tools.tts_core import generate_elevenlabs_audio
from app.tools.code_auditor import run_code_audit

# Globala variabler
garmin_tool = None
strava_tool = None

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- DAA HYBRID BACKEND STARTED (LIFESPAN) ---")
    global garmin_tool, strava_tool
    
    if CONFIG.get("GOOGLE_API_KEY"):
        try: genai.configure(api_key=CONFIG["GOOGLE_API_KEY"])
        except: pass

    if CONFIG.get("GARMIN_EMAIL") and CONFIG.get("GARMIN_PASSWORD"):
        try:
            loop = asyncio.get_event_loop()
            garmin_tool = await loop.run_in_executor(None, GarminCoach)
            print("[SYS] Garmin Tool Loaded & Ready")
        except Exception as e: 
            print(f"[SYS] Garmin Init Error: {e}")

    if CONFIG.get("STRAVA_CLIENT_ID"):
        try:
            strava_tool = StravaTool()
            print("[SYS] Strava Tool Loaded & Ready")
        except Exception as e: 
            print(f"[SYS] Strava Init Error: {e}")

    yield 
    print("--- DAA HYBRID BACKEND STOPPING ---")

# --- MODELLHANTERING ---
def get_available_models_sync():
    """Hämtar tillgängliga modeller dynamiskt."""
    models = []
    
    # Google
    if CONFIG.get("GOOGLE_API_KEY"):
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    clean_id = m.name.replace("models/", "")
                    d_name = getattr(m, "display_name", clean_id)
                    models.append({'id': clean_id, 'name': f"Google: {d_name}"})
        except Exception as e:
            print(f"[SYS] Google Model Fetch Error: {e}")
    
    # OpenAI
    if CONFIG.get("OPENAI_API_KEY"):
        try:
            client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])
            for m in client.models.list():
                if "gpt" in m.id: models.append({'id': m.id, 'name': f"OpenAI: {m.id}"})
        except: pass

    # Groq
    if CONFIG.get("GROQ_API_KEY"):
        try:
            client = OpenAI(api_key=CONFIG["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
            for m in client.models.list():
                models.append({'id': m.id, 'name': f"Groq: {m.id}"})
        except: pass
        
    # DeepSeek
    if CONFIG.get("DEEPSEEK_API_KEY"):
        models.append({'id': 'deepseek-chat', 'name': 'DeepSeek: V3'})

    # Ollama
    ollama_url = CONFIG.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=3)
        if resp.status_code == 200:
            for m in resp.json().get('models', []):
                name = m.get('name', m.get('model', 'Unknown'))
                models.append({'id': name, 'name': f"Ollama: {name}"})
    except: pass

    # Anthropic
    if CONFIG.get("ANTHROPIC_API_KEY"):
        models.append({'id': 'claude-3-5-sonnet-latest', 'name': 'Anthropic: Claude 3.5 Sonnet'})
        models.append({'id': 'claude-3-opus-latest', 'name': 'Anthropic: Claude 3 Opus'})

    if not models: 
        models.append({'id': 'error', 'name': '⚠️ Inga modeller hittades (Kolla API-nycklar)'})
    
    models.sort(key=lambda x: x['name'])
    return models

# --- SERVER SETUP ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app_socketio = socketio.ASGIApp(sio, app)

# --- REST API ENDPOINTS ---

class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    if not CONFIG.get("ELEVENLABS_API_KEY"):
        return Response(content="Ingen API-nyckel", status_code=400)
    loop = asyncio.get_event_loop()
    audio_data = await loop.run_in_executor(None, generate_elevenlabs_audio, req.text)
    return Response(content=audio_data, media_type="audio/mpeg") if audio_data else Response(status_code=500)

SENSITIVE_KEYS = [
    "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", 
    "GROQ_API_KEY", "DEEPSEEK_API_KEY", "ELEVENLABS_API_KEY", 
    "GARMIN_PASSWORD", "STRAVA_CLIENT_SECRET", "WITHINGS_CLIENT_SECRET",
    "HA_TOKEN", "MEM0_API_KEY"
]

@app.get("/api/settings")
async def get_settings_endpoint():
    raw_config = get_config()
    safe_config = {}
    for key, value in raw_config.items():
        if key in SENSITIVE_KEYS and value:
            if len(value) > 8:
                safe_config[key] = f"sk-HIDDEN...{value[-4:]}"
            else:
                safe_config[key] = "********"
        else:
            safe_config[key] = value
    return safe_config

class SettingUpdate(BaseModel):
    settings: dict

@app.post("/api/settings")
async def update_settings_endpoint(data: SettingUpdate):
    global CONFIG
    loop = asyncio.get_event_loop()
    for key, value in data.settings.items():
        val_str = str(value)
        if "sk-HIDDEN" in val_str or "********" in val_str:
            continue
        await loop.run_in_executor(None, save_db_setting, key, value)
    CONFIG = get_config()
    if CONFIG.get("GOOGLE_API_KEY"):
        try: genai.configure(api_key=CONFIG["GOOGLE_API_KEY"])
        except: pass
    return {"status": "success", "msg": "Inställningar sparade säkert."}

# --- SOCKET.IO EVENTS ---

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    await sio.emit('status', {'msg': 'Brain Connected'})
    loop = asyncio.get_event_loop()
    mods = await loop.run_in_executor(None, get_available_models_sync)
    await sio.emit('models_list', {'models': mods})

@sio.event
async def get_models(sid):
    loop = asyncio.get_event_loop()
    mods = await loop.run_in_executor(None, get_available_models_sync)
    await sio.emit('models_list', {'models': mods})

@sio.event
async def user_message(sid, data):
    text = data.get('text', '')
    model_id = data.get('model', 'gemini-1.5-flash')
    print(f"[USER] {text} (Model: {model_id})")
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_message, "hybrid", "user", text)
    
    # Initiera Mem0
    mem0_client = None
    if CONFIG.get("MEM0_API_KEY"):
        try:
            mem0_client = AsyncMemoryClient(api_key=CONFIG["MEM0_API_KEY"])
        except: pass

    injected_data = ""
    text_lower = text.lower()

    # --- KODANALYS ---
    if "analysera dig själv" in text_lower or "analysera koden" in text_lower:
        print(f"[SYS] Startar Code Audit med vald modell: {model_id}")
        await sio.emit('ai_chunk', {'text': f"Jag startar analysen med **{model_id}**. Detta tar en stund...\n"})
        audit_result = await loop.run_in_executor(None, run_code_audit, model_id)
        await sio.emit('ai_chunk', {'text': audit_result})
        await sio.emit('ai_done', {})
        await loop.run_in_executor(None, save_message, "hybrid", "assistant", audit_result)
        return 

    # --- VÄDER ---
    if any(x in text_lower for x in ["väder", "prognos", "grader"]):
        try:
            w = await get_weather()
            injected_data += f"\n[VÄDER]: {w}\n"
        except: pass

    # --- GARMIN LOGIK: LIVE -> SAVE -> FALLBACK ---
    garmin_triggers = ["puls", "sömn", "stress", "garmin", "mår jag", "status", "återhämtning"]
    if garmin_tool and any(t in text_lower for t in garmin_triggers):
        
        garmin_report = None
        source_label = ""
        
        # 1. LIVE DATA FÖRST
        try:
            print("[GARMIN] Försöker hämta LIVE data...")
            report = await loop.run_in_executor(None, garmin_tool.get_health_report)
            
            if report and "fel" not in report:
                garmin_report = report
                source_label = "LIVE (Just nu)"
                
                # 2. SPARA TILL MEM0 (Om vi har en klient)
                if mem0_client:
                    today = datetime.date.today().isoformat()
                    # Vi sparar det som en "fakta"
                    await mem0_client.add(f"Garmin hälsodata {today}: {json.dumps(report)}", user_id="Anders")
                    print("[GARMIN] Data sparad till Mem0.")
            else:
                print(f"[GARMIN] Live misslyckades: {report.get('fel')}")
                raise Exception("API Error")
                
        except Exception as e:
            # 3. FALLBACK: SÖK I MEM0
            print(f"[GARMIN] Byter till FALLBACK (Mem0)... Orsak: {e}")
            if mem0_client:
                try:
                    # Sök efter senaste Garmin-datan
                    mem_results = await mem0_client.search("Garmin hälsodata", user_id="Anders", limit=1)
                    if mem_results:
                        garmin_report = mem_results[0]['memory']
                        update_time = mem_results[0]['updated_at']
                        source_label = f"MINNE (Senast sparat: {update_time})"
                except Exception as mem_e:
                    print(f"[GARMIN] Mem0 fallback misslyckades också: {mem_e}")

        if garmin_report:
            injected_data += f"\n[GARMIN KÄLLA: {source_label}]:\n{garmin_report}\n"
        else:
            injected_data += "\n[GARMIN ERROR]: Kunde inte hämta live-data och inget fanns i minnet.\n"

    # --- STRAVA LOGIK: LIVE -> SAVE -> FALLBACK ---
    strava_triggers = ["strava", "löpning", "cykling", "pass", "träning", "aktivitet"]
    if strava_tool and any(t in text_lower for t in strava_triggers):
        
        strava_data = None
        strava_source = ""
        
        # 1. LIVE
        try:
            print("[STRAVA] Försöker hämta LIVE data...")
            activities = await strava_tool.get_health_report(limit=3)
            
            if isinstance(activities, list):
                strava_data = activities
                strava_source = "LIVE"
                
                # 2. SPARA
                if mem0_client:
                    # Spara som en sammanfattning
                    summary = f"Senaste träning {datetime.date.today()}: " + ", ".join([f"{a['typ']} {a['distans']}" for a in activities])
                    await mem0_client.add(summary, user_id="Anders")
            else:
                raise Exception("Strava API Error")
        except Exception as e:
            # 3. FALLBACK
            print(f"[STRAVA] Fallback till Mem0: {e}")
            if mem0_client:
                try:
                    res = await mem0_client.search("Senaste träning", user_id="Anders", limit=1)
                    if res:
                        strava_data = res[0]['memory']
                        strava_source = f"MINNE ({res[0]['updated_at']})"
                except: pass

        if strava_data:
            injected_data += f"\n[STRAVA KÄLLA: {strava_source}]:\n{strava_data}\n"

    # --- SKICKA TILL AI ---
    full_resp = ""
    try:
        h_limit = int(CONFIG.get("HISTORY_LIMIT", 600))
        chat_history = await loop.run_in_executor(None, get_history, "hybrid", h_limit)
        
        async for chunk in stream_response(model_id, chat_history, text, None, system_injection=injected_data):
            full_resp += chunk
            await sio.emit('ai_chunk', {'text': chunk})
            
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        await sio.emit('ai_chunk', {'text': f"Error: {e}"})

    # Spara assistentens svar i DB (SQLite)
    await loop.run_in_executor(None, save_message, "hybrid", "assistant", full_resp)
    
    # --- MEM0: SPARA KONVERSATIONEN ---
    # Detta gör att assistenten "lär sig" av samtalet
    if mem0_client and full_resp:
        try:
            await mem0_client.add([
                {"role": "user", "content": text},
                {"role": "assistant", "content": full_resp}
            ], user_id="Anders")
            print("[MEM0] Konversation sparad.")
        except Exception as e:
            print(f"[MEM0] Kunde inte spara konversation: {e}")

    await sio.emit('ai_done', {})

if __name__ == "__main__":
    uvicorn.run(app_socketio, host="127.0.0.1", port=8000, reload=False)