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
    get_weather
)
from app.core.prompts import get_system_prompt

# --- VERKTYGS-WRAPPERS ---
# Dessa wrap-funktioner gör att synkrona verktyg kan köras i AI:ns flöde
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
    """
    Hjälpfunktion för att analysera träningsdata.
    Returnerar instruktion om att använda kontexten.
    """
    return "Data för analys finns redan i konversationshistoriken eller system-prompten. Använd den."

# Lista med verktyg som AI:n får se och använda
daa_tools = [
    get_calendar_events,
    tool_get_sensor,
    tool_control_vacuum,
    tool_get_ha_state,
    tool_control_light,
    tool_get_weather,
    tool_analyze_health_data
]

# --- HUVUDFUNKTION FÖR STREAMING ---
async def stream_response(model_id, history, new_message, image_data=None, system_injection=None):
    cfg = get_config()
    base_system_prompt = get_system_prompt()
    
    # --- MEM0: HÄMTA RELEVANT KONTEXT ---
    # Vi kollar om API-nyckeln finns i inställningarna
    mem0_key = cfg.get("MEM0_API_KEY")
    mem0_client = None
    
    if mem0_key:
        try:
            mem0_client = AsyncMemoryClient(api_key=mem0_key)
            # Sök efter minnen som är relevanta för det användaren just sa
            relevant_memories = await mem0_client.search(new_message, user_id="Anders")
            
            mem_text = ""
            for mem in relevant_memories:
                # Plocka ut text och datum om det finns
                date_str = mem.get('updated_at', '')[:10]
                mem_text += f"- {mem['memory']} (Info från: {date_str})\n"
            
            if mem_text:
                base_system_prompt += f"\n\n--- LÅNGTIDSMINNE (Fakta om Anders) ---\n{mem_text}\nAnvänd detta för att personifiera svaret, men prioritera ny data om sådan finns."
        except Exception as e:
            print(f"[MEM0] Kunde inte hämta minnen: {e}")

    # --- LIVE DATA INJEKTION ---
    # Här läggs Garmin/Strava-data till om server.py skickade med det
    if system_injection:
        base_system_prompt += f"\n\n--- REALTIDSDATA & STATUS ---\n{system_injection}"

    model_lower = model_id.lower()
    full_response_text = ""

    # --- VÄLJ MODELL OCH STREAM ---
    
    # 1. GOOGLE GEMINI
    if "gemini" in model_lower or "google" in model_lower:
        if cfg.get("GOOGLE_API_KEY"):
            genai.configure(api_key=cfg["GOOGLE_API_KEY"])
        async for chunk in stream_gemini(model_id, history, new_message, image_data, base_system_prompt):
            full_response_text += chunk
            yield chunk
            
    # 2. GROQ
    elif "groq" in model_lower:
        api_key = cfg.get("GROQ_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen Groq API-nyckel."
            return
        async for chunk in stream_openai_compatible(api_key, "https://api.groq.com/openai/v1", model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk

    # 3. DEEPSEEK
    elif "deepseek" in model_lower:
        api_key = cfg.get("DEEPSEEK_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen DeepSeek API-nyckel."
            return
        async for chunk in stream_openai_compatible(api_key, "https://api.deepseek.com", model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk

    # 4. OPENAI (GPT)
    elif "gpt" in model_lower or "o1" in model_lower or "openai" in model_lower:
        api_key = cfg.get("OPENAI_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen OpenAI API-nyckel."
            return
        async for chunk in stream_openai_compatible(api_key, None, model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk

    # 5. ANTHROPIC (CLAUDE)
    elif "claude" in model_lower or "anthropic" in model_lower:
        api_key = cfg.get("ANTHROPIC_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen Anthropic API-nyckel."
            return
        async for chunk in stream_anthropic(api_key, model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk
            
    # 6. OLLAMA (LOKALT)
    else:
        async for chunk in stream_ollama(model_id, history, new_message, base_system_prompt):
            full_response_text += chunk
            yield chunk

    # --- MEM0: SPARA KONVERSATIONEN ---
    # Spara interaktionen så att assistenten minns vad vi pratat om
    if mem0_client and full_response_text:
        try:
            # Vi kör detta "fire and forget" så vi inte blockerar, 
            # men i en enkel implementation väntar vi snabbt.
            await mem0_client.add([
                {"role": "user", "content": new_message},
                {"role": "assistant", "content": full_response_text}
            ], user_id="Anders")
            print("[MEM0] Konversation sparad till långtidsminnet.")
        except Exception as e:
            print(f"[MEM0] Kunde inte spara konversation: {e}")


# --- IMPLEMENTATIONER AV MODELLER ---

async def stream_gemini(model_id, history, new_message, image_data=None, system_prompt=None):
    """
    Hanterar kommunikation med Google Gemini.
    Inkluderar fix för verktygsanrop och tomma svar.
    """
    try:
        clean_model_id = model_id.replace("Google: ", "").strip()
        if not clean_model_id: clean_model_id = "gemini-1.5-flash"

        # Konfigurera modellen
        model = genai.GenerativeModel(
            model_name=clean_model_id, 
            tools=daa_tools, 
            system_instruction=system_prompt
        )
        
        # Bygg chatthistorik för Gemini-format
        chat_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})

        # Starta chattsession med automatisk verktygshantering
        chat = model.start_chat(history=chat_history, enable_automatic_function_calling=True)
        
        parts = [new_message]
        if image_data:
            parts.append({"mime_type": "image/jpeg", "data": image_data})

        loop = asyncio.get_event_loop()
        
        # 1. SKICKA MEDDELANDET (Körs i tråd för att inte blockera)
        # Google-biblioteket sköter verktygsanropet (t.ex. tool_get_weather) automatiskt här
        response = await loop.run_in_executor(None, lambda: chat.send_message(parts))
        
        # 2. HANTERA SVARET SÄKERT
        final_text = ""
        
        try:
            # Försök hämta texten direkt. Detta fungerar om allt gick rätt.
            final_text = response.text
        except Exception:
            # Om .text kraschar betyder det oftast att modellen gjorde ett verktygsanrop
            # men att något i returen inte tolkades som text av biblioteket.
            # Vi letar manuellt i 'parts'.
            if hasattr(response, 'parts'):
                for part in response.parts:
                    # Om det finns text, ta den
                    if hasattr(part, 'text') and part.text:
                        final_text += part.text
                    
                    # Om vi ser ett funktionsanrop som ligger kvar i svaret
                    if hasattr(part, 'function_call') and part.function_call:
                        print(f"[GEMINI WARN] Verktygsanrop syns i slutsvaret: {part.function_call.name}")
                        final_text += f"\n(Jag körde verktyget '{part.function_call.name}'...)"

        if not final_text:
            final_text = "⚠️ Jag försökte tänka (eller hämta data) men svaret blev tomt. Prova igen."

        # 3. SKICKA SVARET
        # Vi delar upp texten i småbitar för att simulera "streaming"-effekten i UI:t
        chunk_size = 50 
        for i in range(0, len(final_text), chunk_size):
            yield final_text[i:i+chunk_size]
            await asyncio.sleep(0.01)

    except Exception as e:
        traceback.print_exc()
        yield f"⚠️ Gemini System Error: {str(e)}"

async def stream_openai_compatible(api_key, base_url, model_id, history, new_message, system_prompt=None):
    try:
        if ": " in model_id:
            clean_model_id = model_id.split(": ")[-1]
        else:
            clean_model_id = model_id
            
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": new_message})

        stream = await client.chat.completions.create(
            model=clean_model_id,
            messages=messages,
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        yield f"⚠️ API Error ({clean_model_id}): {str(e)}"

async def stream_anthropic(api_key, model_id, history, new_message, system_prompt=None):
    try:
        clean_model_id = model_id.split(": ")[-1]
        client = AsyncAnthropic(api_key=api_key)
        messages = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": new_message})

        async with client.messages.stream(
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            model=clean_model_id,
        ) as stream:
            async for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f"⚠️ Claude Error: {str(e)}"

async def stream_ollama(model_id, history, new_message, system_prompt=None):
    cfg = get_config()
    clean_model_id = model_id.split(": ")[-1]
    url = f"{cfg['OLLAMA_URL']}/api/chat"
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": new_message})
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json={"model": clean_model_id, "messages": messages}, timeout=60.0) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                yield data["message"].get("content", "")
                        except: pass
        except Exception as e:
            yield f"⚠️ Ollama Error: {e}"