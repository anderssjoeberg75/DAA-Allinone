import sys
import io
import os
import asyncio
import socketio
import uvicorn
import time
import requests
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import google.generativeai as genai
from openai import OpenAI

# --- UTF-8 FIX ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Ladda Config
try:
    from config.settings import get_config
    CONFIG = get_config()
    print(f"[SYS] Configuration loaded from Database ({len(CONFIG)} keys).")
except Exception as e:
    print(f"[CRITICAL] Config Load Error: {e}")
    CONFIG = {}

# Importera databasfunktioner
try:
    from app.core.database import init_db, save_message, get_history, save_db_setting
    from app.services.llm_handler import stream_response 
    init_db() 
except Exception as e:
    print(f"[CRITICAL] Database Import Error: {e}")

# --- VERKTYG ---
from app.tools.garmin_core import GarminCoach
from app.tools.strava_core import StravaTool
from app.tools.weather_core import get_weather
from app.tools.tts_core import generate_elevenlabs_audio
from app.tools.code_auditor import run_code_audit  # Analysverktyget

garmin_tool = None
strava_tool = None
last_garmin_fetch = 0
cached_garmin_data = None
last_strava_fetch = 0
cached_strava_data = None

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
            print("[SYS] Garmin Tool Loaded")
        except Exception as e: print(f"[SYS] Garmin Init Error: {e}")

    if CONFIG.get("STRAVA_CLIENT_ID"):
        try:
            strava_tool = StravaTool()
            print("[SYS] Strava Tool Loaded")
        except Exception as e: print(f"[SYS] Strava Init Error: {e}")

    yield 
    print("--- DAA HYBRID BACKEND STOPPING ---")

# --- MODEL LIST HELPER ---
def get_available_models_sync():
    models = []
    # 1. Google
    if CONFIG.get("GOOGLE_API_KEY"):
        # Lägger till dina manuella favoriter först
        models.append({'id': 'gemini-2.5-flash', 'name': 'Google: Gemini 2.5 Flash'})
        models.append({'id': 'gemini-2.0-flash-exp', 'name': 'Google: Gemini 2.0 Flash (Exp)'})
        models.append({'id': 'gemini-1.5-pro', 'name': 'Google: Gemini 1.5 Pro'})
    
    # 2. OpenAI
    if CONFIG.get("OPENAI_API_KEY"):
        try:
            client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])
            for m in client.models.list():
                if "gpt" in m.id: models.append({'id': m.id, 'name': f"OpenAI: {m.id}"})
        except: pass

    # 3. Groq
    if CONFIG.get("GROQ_API_KEY"):
        try:
            client = OpenAI(api_key=CONFIG["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
            for m in client.models.list():
                models.append({'id': m.id, 'name': f"Groq: {m.id}"})
        except: pass
        
    # 4. DeepSeek
    if CONFIG.get("DEEPSEEK_API_KEY"):
        models.append({'id': 'deepseek-chat', 'name': 'DeepSeek: V3'})

    # 5. Ollama
    ollama_url = CONFIG.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            for m in resp.json().get('models', []):
                name = m.get('name', m.get('model', 'Unknown'))
                models.append({'id': name, 'name': f"Ollama: {name}"})
    except: pass

    # 6. Anthropic
    if CONFIG.get("ANTHROPIC_API_KEY"):
        models.append({'id': 'claude-3-5-sonnet-20240620', 'name': 'Anthropic: Claude 3.5 Sonnet'})

    if not models: models.append({'id': 'error', 'name': '⚠️ Inga modeller hittades'})
    return models

# --- SERVER ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app_socketio = socketio.ASGIApp(sio, app)

# --- ENDPOINTS ---
class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    if not CONFIG.get("ELEVENLABS_API_KEY"):
        return Response(content="Ingen API-nyckel", status_code=400)
    loop = asyncio.get_event_loop()
    audio_data = await loop.run_in_executor(None, generate_elevenlabs_audio, req.text)
    return Response(content=audio_data, media_type="audio/mpeg") if audio_data else Response(status_code=500)

@app.get("/api/settings")
async def get_settings_endpoint():
    return get_config()

class SettingUpdate(BaseModel):
    settings: dict

@app.post("/api/settings")
async def update_settings_endpoint(data: SettingUpdate):
    global CONFIG
    loop = asyncio.get_event_loop()
    for key, value in data.settings.items():
        await loop.run_in_executor(None, save_db_setting, key, value)
    CONFIG = get_config()
    if CONFIG.get("GOOGLE_API_KEY"):
        try: genai.configure(api_key=CONFIG["GOOGLE_API_KEY"])
        except: pass
    return {"status": "success", "msg": "Inställningar sparade."}

# --- SOCKET EVENTS ---
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
    global last_garmin_fetch, cached_garmin_data, last_strava_fetch, cached_strava_data
    text = data.get('text', '')
    model_id = data.get('model', 'gemini-1.5-flash')
    
    print(f"[USER] {text} (Model: {model_id})")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_message, "hybrid", "user", text)
    
    injected_data = ""
    text_lower = text.lower()

    # --- KODANALYS (Specialfall) ---
    if "analysera dig själv" in text_lower or "analysera koden" in text_lower:
        print(f"[SYS] Startar Code Audit med vald modell: {model_id}")
        await sio.emit('ai_chunk', {'text': f"Jag startar analysen med **{model_id}**. Detta tar en stund...\n"})
        
        # HÄR SKICKAR VI MED MODEL_ID TILL VERKTYGET
        audit_result = await loop.run_in_executor(None, run_code_audit, model_id)
        
        await sio.emit('ai_chunk', {'text': audit_result})
        await sio.emit('ai_done', {})
        await loop.run_in_executor(None, save_message, "hybrid", "assistant", audit_result)
        return 

    # Väder
    if any(x in text_lower for x in ["väder", "prognos", "grader"]):
        try:
            w = await get_weather()
            injected_data += f"\n[VÄDER]: {w}\n"
        except: pass

    # Garmin & Strava
    if garmin_tool and any(t in text_lower for t in ["puls", "sömn", "stress", "garmin"]):
        now = time.time()
        if (now - last_garmin_fetch > 900) or not cached_garmin_data:
            try:
                report = await loop.run_in_executor(None, garmin_tool.get_health_report)
                if report: cached_garmin_data = report; last_garmin_fetch = now
            except: pass
        if cached_garmin_data: injected_data += f"\n[GARMIN]: {cached_garmin_data}\n"

    if strava_tool and any(t in text_lower for t in ["strava", "löpning", "cykling", "pass"]):
        now = time.time()
        if (now - last_strava_fetch > 300) or not cached_strava_data:
            try:
                activities = await strava_tool.get_health_report(limit=3)
                if activities: cached_strava_data = activities; last_strava_fetch = now
            except: pass
        if cached_strava_data:
            s_txt = "".join([f"- {a['datum']}: {a['typ']} {a['distans_km']}km\n" for a in cached_strava_data])
            injected_data += f"\n[STRAVA]:\n{s_txt}\n"

    full_resp = ""
    try:
        h_limit = int(CONFIG.get("HISTORY_LIMIT", 600))
        chat_history = await loop.run_in_executor(None, get_history, "hybrid", h_limit)
        
        # Vanligt anrop till LLM-tjänsten (som också borde använda model_id)
        async for chunk in stream_response(model_id, chat_history, text, None, system_injection=injected_data):
            full_resp += chunk
            await sio.emit('ai_chunk', {'text': chunk})
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        await sio.emit('ai_chunk', {'text': f"Error: {e}"})

    await loop.run_in_executor(None, save_message, "hybrid", "assistant", full_resp)
    await sio.emit('ai_done', {})

if __name__ == "__main__":
    uvicorn.run(app_socketio, host="127.0.0.1", port=8000, reload=False)