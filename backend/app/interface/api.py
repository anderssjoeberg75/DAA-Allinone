from fastapi import APIRouter
from pydantic import BaseModel
import google.generativeai as genai
import requests
import json
import time
import asyncio
from typing import List, Optional

# Importera databasfunktioner
from app.core.database import save_message, get_history
# Importera System Prompt
from app.core.prompts import get_system_prompt

# Importera inställningar - Use dynamic config
from config.settings import get_config

# Tools
from app.tools.garmin_core import GarminCoach
from app.tools.strava_core import StravaTool

router = APIRouter()

# --- GET DYNAMIC CONFIG ---
cfg = get_config()
GOOGLE_API_KEY = cfg.get("GOOGLE_API_KEY")
OPENAI_API_KEY = cfg.get("OPENAI_API_KEY")
OLLAMA_URL = cfg.get("OLLAMA_URL", "http://127.0.0.1:11434")

# --- AI CONFIGURATION ---
has_google = False
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        has_google = True
    except: pass

# --- GARMIN INIT ---
garmin_tool = None
GARMIN_EMAIL = cfg.get("GARMIN_EMAIL")
GARMIN_PASSWORD = cfg.get("GARMIN_PASSWORD")
if GARMIN_EMAIL and GARMIN_PASSWORD:
    try:
        garmin_tool = GarminCoach()
        print(f"[API] Garmin tool initialized successfully")
    except Exception as e:
        print(f"[API] Garmin init failed: {e}")

last_garmin_fetch = 0
cached_garmin_data = None

# --- STRAVA INIT ---
strava_tool = None
STRAVA_CLIENT_ID = cfg.get("STRAVA_CLIENT_ID")
STRAVA_REFRESH_TOKEN = cfg.get("STRAVA_REFRESH_TOKEN")
if STRAVA_CLIENT_ID and STRAVA_REFRESH_TOKEN:
    try:
        strava_tool = StravaTool()
        print(f"[API] Strava tool initialized successfully")
    except Exception as e:
        print(f"[API] Strava init failed: {e}")

last_strava_fetch = 0
cached_strava_data = None



# --- MODELLER ---
class Message(BaseModel):
    role: str
    content: str
    image: Optional[str] = None

class ChatRequest(BaseModel):
    model: str = "gemini-1.5-flash"
    messages: List[Message]
    session_id: str = "default"

# --- ENDPOINTS ---

@router.get("/api/models")
async def get_models():
    """Fetches available models dynamically."""
    models = []
    
    # 1. Google
    if has_google:
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    clean_id = m.name.replace("models/", "")
                    d_name = getattr(m, "display_name", clean_id)
                    models.append({"id": clean_id, "name": f"Google: {d_name}"})
        except: pass
    
    # 2. OpenAI
    if OPENAI_API_KEY:
        try:
            # Use requests here since this is not as time-critical, 
            # eller byt till httpx för konsekvens.
            h = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            r = requests.get("https://api.openai.com/v1/models", headers=h, timeout=5)
            if r.status_code == 200:
                data = r.json().get('data', [])
                data.sort(key=lambda x: x.get('created', 0), reverse=True)
                for m in data:
                    if m['id'].startswith(("gpt", "o1")):
                        models.append({"id": m['id'], "name": f"OpenAI: {m['id']}"})
        except: pass

    # 3. Ollama
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if r.status_code == 200:
            for m in r.json().get('models', []):
                models.append({"id": m['name'], "name": f"Ollama: {m['name']}"})
    except: pass

    return {"data": models}

@router.post("/chat")
@router.post("/api/chat")
async def chat(request: ChatRequest):
    global last_garmin_fetch, cached_garmin_data
    global last_strava_fetch, cached_strava_data
    
    user_msg = request.messages[-1].content
    session_id = request.session_id
    model_id = request.model.lower()

    # 2. SAVE USER'S MESSAGE
    save_message(session_id, "user", user_msg)

    # 3. Fetch history
    db_history = get_history(session_id)

    # 4. Fetch System Prompt
    system_prompt = get_system_prompt()

    # --- FETCH GARMIN DATA (Runs in thread to avoid blocking) ---
    garmin_triggers = ["puls", "sömn", "stress", "garmin", "mår jag", "status", "kropp"]
    print(f"[API DEBUG] Message: '{user_msg}' | garmin_tool: {garmin_tool is not None}")
    if garmin_tool and any(t in user_msg.lower() for t in garmin_triggers):
        now = time.time()
        if (now - last_garmin_fetch > 900) or not cached_garmin_data:
            try:
                # Garmin library is synchronous, so we run it in an executor
                loop = asyncio.get_event_loop()
                report = await loop.run_in_executor(None, garmin_tool.get_health_report)
                if report:
                    cached_garmin_data = report
                    last_garmin_fetch = now
            except: pass
        
        if cached_garmin_data:
            d = cached_garmin_data
            data_block = (
                f"   - 💤 Sömn: {d.get('sleep_hours')} timmar\n"
                f"   - ❤️ Vilopuls: {d.get('resting_heart_rate')} bpm\n"
                f"   - ⚡ Stressnivå: {d.get('stress_avg')}/100\n"
                f"   - 🔋 Body Battery: {d.get('body_battery_now', 'N/A')}\n"
                f"   - 🧠 HRV Status: {d.get('hrv_status', 'N/A')}\n"
                f"   - 😴 Sömn poäng: {d.get('sleep_score', 'N/A')}\n"
            )
            system_prompt += f"\n\n[HÄLSODATA FRÅN GARMIN IDAG]:\n{data_block}\n\nINSTRUKTION: Analysera ovanstående data. Ge konkreta råd baserat på värdena."

    # --- FETCH STRAVA DATA (Now with await) ---
    strava_triggers = ["strava", "löpning", "cykling", "pass", "träning", "aktivitet"]
    if strava_tool and any(t in user_msg.lower() for t in strava_triggers):
        now = time.time()
        if (now - last_strava_fetch > 300) or not cached_strava_data:
            try:
                # Strava tool is now async
                activities = await strava_tool.get_health_report(limit=3)
                if activities:
                    cached_strava_data = activities
                    last_strava_fetch = now
            except: pass

        if cached_strava_data:
            strava_text = ""
            for act in cached_strava_data:
                strava_text += (
                    f"   - 📅 {act['datum']}: {act['typ']}\n"
                    f"     Distans: {act['distans_km']} km | Tid: {act['tid_min']} min | Ansträngning: {act['ansträngning']}\n"
                )
            system_prompt += f"\n\n[SENASTE TRÄNINGSPASS]:\n{strava_text}\nINSTRUKTION: Kommentera träningen kortfattat och uppmuntrande."

    response_text = ""

    # 5. CALL AI
    
    # --- GOOGLE GEMINI ---
    if "gemini" in model_id:
        try:
            gemini_history = []
            gemini_history.append({"role": "user", "parts": [system_prompt]})
            gemini_history.append({"role": "model", "parts": ["Uppfattat. Jag svarar strukturerat."]})

            for msg in db_history:
                role = "model" if msg['role'] == "assistant" else "user"
                gemini_history.append({"role": role, "parts": [msg['content']]})
            
            if not db_history or db_history[-1]['content'] != user_msg:
                 gemini_history.append({"role": "user", "parts": [user_msg]})

            # Run async if possible, otherwise executor
            loop = asyncio.get_event_loop()
            gmodel = genai.GenerativeModel(model_id)
            final_response = await loop.run_in_executor(None, lambda: gmodel.generate_content(gemini_history))
            response_text = final_response.text

        except Exception as e:
            response_text = f"Gemini Error: {e}"

    # --- OPENAI / OTHERS ---
    elif "gpt" in model_id or "o1" in model_id:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            for msg in db_history:
                messages.append({"role": msg['role'], "content": msg['content']})
            
            if not db_history or db_history[-1]['content'] != user_msg:
                 messages.append({"role": "user", "content": user_msg})

            payload = {"model": model_id, "messages": messages}
            h = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            # Use requests in executor to avoid blocking
            loop = asyncio.get_event_loop()
            r = await loop.run_in_executor(None, lambda: requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=h))
            
            if r.status_code == 200:
                response_text = r.json()["choices"][0]["message"]["content"]
            else:
                response_text = f"OpenAI Error: {r.text}"
        except Exception as e:
            response_text = f"Error: {e}"

    # --- OLLAMA ---
    else:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            for msg in db_history:
                messages.append({"role": msg['role'], "content": msg['content']})
            
            if not db_history or db_history[-1]['content'] != user_msg:
                 messages.append({"role": "user", "content": user_msg})

            payload = {"model": model_id, "messages": messages, "stream": False}
            # Ollama can be slow, run in executor
            loop = asyncio.get_event_loop()
            r = await loop.run_in_executor(None, lambda: requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60))
            
            if r.status_code == 200:
                response_text = r.json().get("message", {}).get("content", "")
            else:
                response_text = f"Ollama Error: {r.text}"
        except Exception as e:
            response_text = f"Error: {e}"

    # 6. SAVE RESPONSE
    if response_text:
        save_message(session_id, "assistant", response_text)

    return response_text