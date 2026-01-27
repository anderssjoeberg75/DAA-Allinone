import sys
import os
import asyncio
import socketio
import uvicorn
import requests
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import google.generativeai as genai
from app.services.gemini_live import AudioLoop
from app.core.database import init_db, save_message, get_history, save_db_setting, get_db_prompts, save_db_prompt
from app.services.llm_handler import stream_response
from app.tools.tts_core import generate_elevenlabs_audio
# IMPORTERA ENDAST FUNKTIONEN
from app.core.prompts import get_system_prompt 

try:
    from config.settings import get_config
except:
    def get_config(): return {}

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
init_db()

audio_loop = None
loop_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    conf = get_config()
    if conf.get("GOOGLE_API_KEY"):
        try: genai.configure(api_key=conf["GOOGLE_API_KEY"])
        except: pass
    yield 
    global audio_loop, loop_task
    if audio_loop: audio_loop.stop()
    if loop_task: loop_task.cancel()

def get_available_models_sync():
    conf = get_config() 
    models = []
    if conf.get("GOOGLE_API_KEY"):
        try:
            genai.configure(api_key=conf["GOOGLE_API_KEY"])
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    clean_id = m.name.replace("models/", "")
                    models.append({'id': clean_id, 'name': f"Google: {getattr(m, 'display_name', clean_id)}"})
        except: models.append({'id': 'gemini-2.0-flash-exp', 'name': 'Google: Gemini 2.0 Flash (Fallback)'})
    if conf.get("OPENAI_API_KEY"): models.append({'id': 'gpt-4o', 'name': 'OpenAI: GPT-4o'})
    ollama_url = conf.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=1)
        if resp.status_code == 200:
            for m in resp.json().get('models', []):
                models.append({'id': m.get('name'), 'name': f"Ollama: {m.get('name')}"})
    except: pass
    if not models: models.append({'id': 'error', 'name': '⚠️ No Models Found'})
    return models

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app_socketio = socketio.ASGIApp(sio, app)

class TTSRequest(BaseModel): text: str
class SettingsRequest(BaseModel): settings: dict
class PromptRequest(BaseModel): prompts: dict

@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    loop = asyncio.get_event_loop()
    try:
        audio = await loop.run_in_executor(None, generate_elevenlabs_audio, req.text)
        if audio: return Response(content=audio, media_type="audio/mpeg")
    except: pass
    return Response(status_code=500)

@app.get("/api/settings")
async def get_s():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_config)

@app.post("/api/settings")
async def up_s(d: SettingsRequest): 
    loop = asyncio.get_event_loop()
    for k, v in d.settings.items(): await loop.run_in_executor(None, save_db_setting, k, v)
    return {"status": "ok"}

@app.get("/api/prompts")
async def get_prompts_endpoint():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_db_prompts)

@app.post("/api/prompts")
async def save_prompts_endpoint(req: PromptRequest):
    loop = asyncio.get_event_loop()
    for k, v in req.prompts.items(): await loop.run_in_executor(None, save_db_prompt, k, v)
    return {"status": "ok"}

@sio.event
async def connect(sid, env):
    await sio.emit('status', {'msg': 'DAA Connected'})
    loop = asyncio.get_event_loop()
    mods = await loop.run_in_executor(None, get_available_models_sync)
    await sio.emit('models_list', {'models': mods})

@sio.event
async def get_models(sid):
    loop = asyncio.get_event_loop()
    mods = await loop.run_in_executor(None, get_available_models_sync)
    await sio.emit('models_list', {'models': mods})

@sio.event
async def start_audio(sid, data=None):
    global audio_loop, loop_task
    if audio_loop: return
    conf = get_config()
    api_key = conf.get("GOOGLE_API_KEY")
    if not api_key: await sio.emit('error', {'msg': 'Saknar Google API Key'}); return

    def on_status(msg): asyncio.create_task(sio.emit('status', {'msg': msg}))
    def on_error(msg): asyncio.create_task(sio.emit('error', {'msg': msg}))
    def on_transcription(text): asyncio.create_task(sio.emit('ai_chunk', {'text': text}))
    def on_turn_complete(): asyncio.create_task(sio.emit('ai_done', {}))

    try:
        audio_loop = AudioLoop(api_key=api_key, on_status=on_status, on_error=on_error, on_transcription=on_transcription, on_turn_complete=on_turn_complete)
        loop_task = asyncio.create_task(audio_loop.run())
        await sio.emit('status', {'msg': 'DAA Live Starting...'})
    except Exception as e: await sio.emit('error', {'msg': str(e)})

@sio.event
async def stop_audio(sid):
    global audio_loop, loop_task
    if audio_loop:
        audio_loop.stop()
        audio_loop = None
        await sio.emit('status', {'msg': 'DAA Live Stopped'})

@sio.event
async def user_message(sid, data):
    text = data.get('text', '')
    requested_model = data.get('model', 'gemini-2.0-flash-exp')
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_message, "hybrid", "user", text)
    full_resp = ""
    try:
        hist = await loop.run_in_executor(None, get_history, "hybrid", 10)
        
        # --- CLEAN: Inga hårdkodade instruktioner här ---
        sys_prompt = get_system_prompt()

        try:
            async for chunk in stream_response(requested_model, hist, text, None, system_injection=sys_prompt):
                full_resp += chunk
                await sio.emit('ai_chunk', {'text': chunk})
        except Exception as e:
            fallback = "gemini-2.0-flash-exp"
            if requested_model != fallback:
                await sio.emit('ai_chunk', {'text': f"\n[System: Byter till {fallback}...]\n"})
                async for chunk in stream_response(fallback, hist, text, None, system_injection=sys_prompt):
                    full_resp += chunk
                    await sio.emit('ai_chunk', {'text': chunk})
            else: raise e

    except Exception as e:
        print(f"[LLM ERROR] {e}")
        await sio.emit('ai_chunk', {'text': f"Fel: {e}"})

    await loop.run_in_executor(None, save_message, "hybrid", "assistant", full_resp)
    await sio.emit('ai_done', {})

if __name__ == "__main__":
    uvicorn.run(app_socketio, host="127.0.0.1", port=8000, reload=False, loop="asyncio")