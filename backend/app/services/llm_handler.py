import google.generativeai as genai
import httpx
import json
import asyncio
import traceback
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import get_config
from mem0 import AsyncMemoryClient

# Importera verktyg
from app.tools import (
    get_calendar_events, 
    get_sensor_data, 
    control_vacuum, 
    get_ha_state, 
    control_light,
    get_weather,
    run_code_audit
)
# Importera prompt-funktioner och variabel
from app.core.prompts import get_system_prompt, ANALYZE_CODE_TOOL_DESC

# --- VERKTYGS-WRAPPERS ---

def tool_analyze_code():
    # Beskrivningen sätts dynamiskt nedanför
    print("[DAA] 🛠️  Startar kodanalys...")
    try: 
        result = run_code_audit()
        print("[DAA] ✅ Kodanalys klar!")
        return result
    except Exception as e: 
        return f"Fel vid kodanalys: {e}"

# HÄR sätter vi beskrivningen från databasen (via prompts.py)
tool_analyze_code.__doc__ = ANALYZE_CODE_TOOL_DESC

def tool_get_weather():
    """Hämtar väderprognos."""
    try: return asyncio.run(get_weather())
    except: return "Kunde inte hämta väder."

def tool_control_light(entity_id: str, action: str):
    """Styr belysning (on/off)."""
    try: return asyncio.run(control_light(entity_id, action))
    except: return "Kunde inte styra lampan."

def tool_control_vacuum(entity_id: str, action: str):
    """Styr dammsugare (start/stop/dock)."""
    try: return asyncio.run(control_vacuum(entity_id, action))
    except: return "Kunde inte styra dammsugaren."

def tool_get_ha_state(entity_id: str):
    """Hämtar status för en enhet."""
    try: return asyncio.run(get_ha_state(entity_id))
    except: return "Kunde inte hämta status."

def tool_get_sensor(friendly_name: str):
    """Hämtar sensordata."""
    try: return asyncio.run(get_sensor_data(friendly_name))
    except: return "Kunde inte hämta sensordata."

def tool_analyze_health_data():
    """Hjälpfunktion för att analysera träningsdata."""
    return "Data för analys finns redan i konversationshistoriken."

# Lista med verktyg
daa_tools = [
    get_calendar_events,
    tool_get_sensor,
    tool_control_vacuum,
    tool_get_ha_state,
    tool_control_light,
    tool_get_weather,
    tool_analyze_health_data,
    tool_analyze_code
]

# --- HUVUDFUNKTION FÖR STREAMING ---
async def stream_response(model_id, history, new_message, image_data=None, system_injection=None):
    cfg = get_config()
    base_system_prompt = get_system_prompt() # Hämtas från DB + Tid
    
    # --- MEM0 ---
    mem0_key = cfg.get("MEM0_API_KEY")
    mem0_client = None
    if mem0_key and len(mem0_key) > 5:
        try:
            mem0_client = AsyncMemoryClient(api_key=mem0_key)
            try:
                relevant_memories = await mem0_client.search(new_message, user_id="Anders")
                mem_text = ""
                for mem in relevant_memories:
                    mem_text += f"- {mem['memory']}\n"
                if mem_text: base_system_prompt += f"\n\n--- LÅNGTIDSMINNE ---\n{mem_text}"
            except: pass
        except: pass

    # --- LIVE DATA ---
    if system_injection:
        base_system_prompt += f"\n\n--- REALTIDSDATA ---\n{system_injection}"

    model_lower = model_id.lower()
    full_response_text = ""

    # --- VÄLJ MODELL ---
    if "gemini" in model_lower or "google" in model_lower:
        if cfg.get("GOOGLE_API_KEY"): genai.configure(api_key=cfg["GOOGLE_API_KEY"])
        async for chunk in stream_gemini(model_id, history, new_message, image_data, base_system_prompt):
            full_response_text += chunk
            yield chunk
    elif "gpt" in model_lower:
        api_key = cfg.get("OPENAI_API_KEY")
        if not api_key: yield "⚠️ Ingen API-nyckel."; return
        async for chunk in stream_openai_compatible(api_key, None, model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk
    elif "ollama" in model_lower: # Förenklat för exempel
         async for chunk in stream_ollama(model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk
    else: # Fallback till Ollama eller annan logik
         async for chunk in stream_ollama(model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk

    # --- SPARA TILL MINNE ---
    if mem0_client and full_response_text:
        try: await mem0_client.add([{"role": "user", "content": new_message},{"role": "assistant", "content": full_response_text}], user_id="Anders")
        except: pass

async def stream_gemini(model_id, history, new_message, image_data=None, system_prompt=None):
    try:
        clean_model_id = model_id.replace("Google: ", "").strip()
        if not clean_model_id: clean_model_id = "gemini-1.5-flash"
        
        # Stäng av filter
        safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]

        model = genai.GenerativeModel(model_name=clean_model_id, tools=daa_tools, system_instruction=system_prompt, safety_settings=safety)
        
        chat_history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in history]
        chat = model.start_chat(history=chat_history, enable_automatic_function_calling=True)
        
        parts = [new_message]
        if image_data: parts.append({"mime_type": "image/jpeg", "data": image_data})

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: chat.send_message(parts))
        
        final_text = ""
        try: final_text = response.text
        except:
            if hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'text') and part.text: final_text += part.text

        chunk_size = 50 
        for i in range(0, len(final_text), chunk_size):
            yield final_text[i:i+chunk_size]
            await asyncio.sleep(0.01)

    except Exception as e: yield f"⚠️ Error: {str(e)}"

# Behåll helper-funktioner för OpenAI/Ollama här (de var korrekta i förra versionen)
async def stream_openai_compatible(api_key, base_url, model_id, history, new_message, system_prompt=None):
    clean_model_id = model_id.split(": ")[-1] if ": " in model_id else model_id
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": new_message}]
    stream = await client.chat.completions.create(model=clean_model_id, messages=messages, stream=True)
    async for chunk in stream:
        if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content

async def stream_ollama(model_id, history, new_message, system_prompt=None):
    cfg = get_config()
    url = f"{cfg['OLLAMA_URL']}/api/chat"
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": new_message}]
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json={"model": model_id.split(": ")[-1], "messages": messages}, timeout=60.0) as resp:
            async for line in resp.aiter_lines():
                if line:
                    try: 
                        data = json.loads(line)
                        if "message" in data: yield data["message"].get("content", "")
                    except: pass