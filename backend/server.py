import sys
import os
import asyncio
import socketio
import uvicorn
import requests
import httpx
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from google import genai

from app.core.database import init_db, save_message, get_history, save_db_setting, get_db_prompts, save_db_prompt
from app.services.llm_handler import stream_response
from app.tools.tts_core import generate_tts_audio
# IMPORT ONLY THE FUNCTION
from app.core.prompts import get_system_prompt 
from app.services.gemini_live import AudioLoop  # Voice mode support 
from app.services.gemini_live_chat import LiveChatSession  # Live Chat mode support 

# NEW IMPORTS
from app.core.logging_config import logger
from app.core.tool_registry import tool_registry
from app.services.proactive_service import ProactiveService

try:
    from config.settings import get_config
except:
    def get_config(): return {}

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    conf = get_config()
    # Note: google.genai uses Client(api_key=...) pattern, not configure()
    # API key validation happens when client is created
    if not conf.get("GOOGLE_API_KEY"):
        logger.warning("No GOOGLE_API_KEY found in settings! You will not be able to use Gemini models or Live audio.")

    if not conf.get("OPENAI_API_KEY"):
        logger.info("No OPENAI_API_KEY provided. GPT-4o disabled.")
    
    # START PROACTIVE SERVICE
    global proactive_service
    proactive_service = ProactiveService(sio)
    asyncio.create_task(proactive_service.start())

    yield 
    
    # SHUTDOWN
    if proactive_service:
        proactive_service.stop() 

import time

# Cache variables
CACHED_MODELS = None
LAST_CACHE_TIME = 0
CACHE_DURATION = 300  # 5 minutes

async def get_available_models(force_refresh=False):
    global CACHED_MODELS, LAST_CACHE_TIME
    
    current_time = time.time()
    if not force_refresh and CACHED_MODELS and (current_time - LAST_CACHE_TIME < CACHE_DURATION):
        return CACHED_MODELS

    conf = get_config() 
    models = []
    
    # 1. Google Gemini
    if conf.get("GOOGLE_API_KEY"):
        try:
            client = genai.Client(api_key=conf["GOOGLE_API_KEY"])
            for m in client.models.list():
                methods = getattr(m, 'supported_methods', [])
                if 'generateContent' in methods or not methods:
                    clean_id = m.name.replace("models/", "")
                    models.append({'id': clean_id, 'name': f"Google: {m.display_name or clean_id}"})
        except Exception as e:
            logger.error(f"[GOOGLE MODELS ERROR] {e}")
            models.append({'id': 'gemini-1.5-flash', 'name': 'Google: Gemini 1.5 Flash (Fallback)'})
    
    # 2. OpenAI
    if conf.get("OPENAI_API_KEY"): 
        models.append({'id': 'gpt-4o', 'name': 'OpenAI: GPT-4o'})
    
    # 3. Ollama (Async)
    ollama_url = conf.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{ollama_url}/api/tags", timeout=1.0)
            if resp.status_code == 200:
                for m in resp.json().get('models', []):
                    models.append({'id': m.get('name'), 'name': f"Ollama: {m.get('name')}"})
    except: 
        pass
    
    if not models: 
        models.append({'id': 'error', 'name': '⚠️ No Models Found'})
    
    CACHED_MODELS = models
    LAST_CACHE_TIME = current_time
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
    try:
        audio = await generate_tts_audio(req.text)
        if audio: return Response(content=audio, media_type="audio/wav")
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
    mods = await get_available_models()
    await sio.emit('models_list', {'models': mods})



@sio.event
async def user_message(sid, data):
    text = data.get('text', '')
    image_data = data.get('image', None) # Extract image data
    requested_model = data.get('model', 'gemini-2.5-flash-native-audio-latest')
    loop = asyncio.get_event_loop()
    
    # Auto-fill text if image is present but text is empty
    if not text.strip() and image_data:
        text = "Beskriv vad du ser på bilden."

    # Save message with image
    await loop.run_in_executor(None, save_message, "hybrid", "user", text, image_data)
    
    # --- WEB AGENT ROUTING ---
    # Simple keyword detection for "Computer Use" capabilities
    web_triggers = ["gå till", "sök på", "navigera till", "kolla på", "vad kostar", "leta upp", "amazon", "google"]
    if any(t in text.lower() for t in web_triggers) and "bild" not in text.lower():
        logger.info(f"WebAgent trigger detected for: {text}")
        await sio.emit('ai_chunk', {'text': "\n🤖 *Startar webbläsare...*\n"})
        
        try:
            # Run the agent (this might take time)
            agent_response = await tool_registry.run_web_agent(text)
            
            # Send the result
            await sio.emit('ai_chunk', {'text': f"\n{agent_response}\n"})
            
            # Save to history
            await loop.run_in_executor(None, save_message, "hybrid", "assistant", agent_response)
            await sio.emit('ai_done', {})
            return # Exit early, don't use standard LLM
            
        except Exception as e:
            logger.error(f"WebAgent failed: {e}")
            await sio.emit('ai_chunk', {'text': f"\n⚠️ *Webelläsarfel:* {str(e)}\n"})
            # Fall through to normal LLM if web agent fails
    
    full_resp = ""
    try:
        hist = await loop.run_in_executor(None, get_history, "hybrid", 10)
        
        sys_prompt = get_system_prompt()

        # --- CONTEXT INJECTION FROM TOOL REGISTRY ---
        # Replaces the old hardcoded Garmin/Strava blocks
        injection = await tool_registry.get_context_injection(text)
        if injection:
            sys_prompt += injection
            logger.info("Context injected from ToolRegistry")

        try:
            # Pass image_data to stream_response
            async for chunk in stream_response(requested_model, hist, text, image_data=image_data, system_injection=sys_prompt):
                full_resp += chunk
                await sio.emit('ai_chunk', {'text': chunk})
        except Exception as e:
            fallback = "gemini-2.0-flash"
            if requested_model != fallback:
                await sio.emit('ai_chunk', {'text': f"\n[System: Switching to {fallback}...]\n"})
                async for chunk in stream_response(fallback, hist, text, image_data=image_data, system_injection=sys_prompt):
                    full_resp += chunk
                    await sio.emit('ai_chunk', {'text': chunk})
            else: raise e

    except Exception as e:
        logger.error(f"[LLM ERROR] {e}")
        await sio.emit('ai_chunk', {'text': f"Error: {e}"})

    await loop.run_in_executor(None, save_message, "hybrid", "assistant", full_resp)
    await sio.emit('ai_done', {})

# --- VOICE MODE ---
voice_sessions = {}

# --- LIVE CHAT MODE ---
live_chat_sessions = {}

@sio.event
async def start_voice_mode(sid):
    logger.info(f"[VOICE] Start {sid}")
    try:
        cfg = get_config()
        api_key = cfg.get("GOOGLE_API_KEY")
        if not api_key:
            await sio.emit('voice_error', {'error': 'No API key'}, room=sid)
            return
        
        def on_trans(txt):
            asyncio.create_task(sio.emit('ai_transcription', {'text': txt}, room=sid))
        def on_stat(s):
            asyncio.create_task(sio.emit('voice_status', {'status': s}, room=sid))
        def on_err(e):
            asyncio.create_task(sio.emit('voice_error', {'error': e}, room=sid))
        def on_turn():
            asyncio.create_task(sio.emit('voice_turn_complete', {}, room=sid))
        
        audio_loop = AudioLoop(api_key, on_transcription=on_trans, on_status=on_stat, on_error=on_err, on_turn_complete=on_turn)
        voice_sessions[sid] = audio_loop
        asyncio.create_task(audio_loop.run())
        await sio.emit('voice_started', {}, room=sid)
    except Exception as e:
        await sio.emit('voice_error', {'error': str(e)}, room=sid)

@sio.event
async def stop_voice_mode(sid):
    if sid in voice_sessions:
        voice_sessions[sid].stop()
        del voice_sessions[sid]
        await sio.emit('voice_stopped', {}, room=sid)

@sio.event
async def start_live_chat(sid, data):
    """Start Gemini Live Chat session - generates TEXT + AUDIO simultaneously"""
    logger.info(f"[LIVE CHAT] Start {sid}")
    try:
        cfg = get_config()
        api_key = cfg.get("GOOGLE_API_KEY")
        if not api_key:
            await sio.emit('chat_error', {'error': 'No API key'}, room=sid)
            return
        
        initial_message = data.get('message', '')
        
        # Callbacks to send data to frontend
        def on_text_chunk(text):
            asyncio.create_task(sio.emit('ai_chunk', {'text': text}, room=sid))
        
        def on_audio_chunk(audio_b64):
            asyncio.create_task(sio.emit('audio_chunk', {'audio': audio_b64}, room=sid))
        
        def on_done():
            asyncio.create_task(sio.emit('ai_done', {}, room=sid))
        
        def on_error(error):
            asyncio.create_task(sio.emit('chat_error', {'error': error}, room=sid))
        
        # Create and start session
        session = LiveChatSession(
            api_key=api_key,
            on_text_chunk=on_text_chunk,
            on_audio_chunk=on_audio_chunk,
            on_done=on_done,
            on_error=on_error
        )
        
        live_chat_sessions[sid] = session
        
        # Start session in background
        asyncio.create_task(session.start(initial_message=initial_message))
        
        await sio.emit('live_chat_started', {}, room=sid)
        logger.info(f"[LIVE CHAT] Session started for {sid}")
        
    except Exception as e:
        logger.error(f"[LIVE CHAT] Error: {e}")
        await sio.emit('chat_error', {'error': str(e)}, room=sid)

@sio.event
async def live_chat_message(sid, data):
    """Send a message in an active Live Chat session"""
    if sid not in live_chat_sessions:
        await sio.emit('chat_error', {'error': 'No active session'}, room=sid)
        return
    
    message = data.get('message', '')
    try:
        await live_chat_sessions[sid].send_message(message)
    except Exception as e:
        logger.error(f"[LIVE CHAT] Send error: {e}")
        await sio.emit('chat_error', {'error': str(e)}, room=sid)

@sio.event
async def stop_live_chat(sid):
    """Stop Live Chat session"""
    if sid in live_chat_sessions:
        live_chat_sessions[sid].stop()
        del live_chat_sessions[sid]
        await sio.emit('live_chat_stopped', {}, room=sid)
        logger.info(f"[LIVE CHAT] Session stopped for {sid}")

@sio.event
async def disconnect(sid):
    # Clean up voice sessions
    if sid in voice_sessions:
        voice_sessions[sid].stop()
        del voice_sessions[sid]
    
    # Clean up live chat sessions
    if sid in live_chat_sessions:
        live_chat_sessions[sid].stop()
        del live_chat_sessions[sid]


# --- MEMORY EXPLORER ENDPOINTS ---
from mem0 import AsyncMemoryClient

class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 20

class MemoryAddRequest(BaseModel):
    text: str

@app.post("/api/memories/search")
async def search_memories(req: MemorySearchRequest):
    """Search vector memories via Mem0"""
    conf = get_config()
    api_key = conf.get("MEM0_API_KEY")
    user_id = conf.get("USER_ID", "Anders")
    
    if not api_key:
        return Response(content='{"error": "No MEM0_API_KEY configured"}', status_code=400, media_type="application/json")

    try:
        client = AsyncMemoryClient(api_key=api_key)
        # Search returns a list of dicts: [{'memory': '...', 'id': '...'}]
        # v2 requires filters dict
        results = await client.search(req.query, filters={"user_id": user_id}, limit=req.limit)
        return results
    except Exception as e:
        logger.error(f"Mem0 Search Error: {e}")
        return Response(content=f'{{"error": "{str(e)}"}}', status_code=500, media_type="application/json")

@app.get("/api/memories")
async def get_all_memories():
    """Get 'all' memories by searching for a generic term or list (if supported)"""
    # Mem0 doesn't have a clean 'list all' yet in some versions, so we search for common terms or use client.get_all depending on SDK version.
    # We'll assume search with "history" or empty string might return recent.
    # Better approach: Mem0 v1 has .get_all(user_id=...)
    conf = get_config()
    api_key = conf.get("MEM0_API_KEY")
    user_id = conf.get("USER_ID", "Anders")
    
    if not api_key: return {"results": []}

    try:
        client = AsyncMemoryClient(api_key=api_key)
        # v2 requires filters dict
        results = await client.get_all(filters={"user_id": user_id}, limit=100)
        return results
    except Exception as e:
         logger.error(f"Mem0 List Error: {e}")
         return {"results": [], "error": str(e)}

@app.post("/api/memories/add")
async def add_memory(req: MemoryAddRequest):
    conf = get_config()
    api_key = conf.get("MEM0_API_KEY")
    user_id = conf.get("USER_ID", "Anders")
    
    if not api_key: return Response(status_code=400)

    try:
        client = AsyncMemoryClient(api_key=api_key)
        await client.add(req.text, user_id=user_id)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Mem0 Add Error: {e}")
        return Response(status_code=500, content=str(e))

@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    conf = get_config()
    api_key = conf.get("MEM0_API_KEY")
    user_id = conf.get("USER_ID", "Anders") # Provide user_id for safety if needed by SDK
    
    if not api_key: return Response(status_code=400)
    
    try:
        client = AsyncMemoryClient(api_key=api_key)
        # Verify SDK signature for delete. Usually delete(memory_id)
        await client.delete(memory_id)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Mem0 Delete Error: {e}")
        return Response(status_code=500, content=str(e))




if __name__ == "__main__":
    uvicorn.run("server:app_socketio", host="127.0.0.1", port=8000, reload=True, loop="asyncio")