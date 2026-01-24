import google.generativeai as genai
import httpx
import json
import asyncio
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import get_config

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

# Sync wrappers för verktyg (behövs för Gemini)
def get_weather_sync(): return asyncio.run(get_weather())
def control_light_sync(entity_id: str, action: str): return asyncio.run(control_light(entity_id, action))
def control_vacuum_sync(entity_id: str, action: str): return asyncio.run(control_vacuum(entity_id, action))
def get_ha_state_sync(entity_id: str): return asyncio.run(get_ha_state(entity_id))
def get_sensor_data_sync(friendly_name: str): return asyncio.run(get_sensor_data(friendly_name))

daa_tools = [
    get_calendar_events,
    get_sensor_data_sync,
    control_vacuum_sync,
    get_ha_state_sync,
    control_light_sync,
    get_weather_sync
]

async def stream_response(model_id, history, new_message, image_data=None, system_injection=None):
    cfg = get_config()
    base_system_prompt = get_system_prompt()
    if system_injection:
        base_system_prompt += f"\n\n--- REALTIDSDATA ---\n{system_injection}"

    model_lower = model_id.lower()

    # --- 1. GOOGLE GEMINI ---
    if "gemini" in model_lower or "google" in model_lower:
        if cfg.get("GOOGLE_API_KEY"):
            genai.configure(api_key=cfg["GOOGLE_API_KEY"])
        async for chunk in stream_gemini(model_id, history, new_message, image_data, base_system_prompt):
            yield chunk
            
    # --- 2. GROQ ---
    elif "groq" in model_lower:
        api_key = cfg.get("GROQ_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen Groq API-nyckel."
            return
        async for chunk in stream_openai_compatible(api_key, "https://api.groq.com/openai/v1", model_id, history, new_message, base_system_prompt):
            yield chunk

    # --- 3. DEEPSEEK ---
    elif "deepseek" in model_lower:
        api_key = cfg.get("DEEPSEEK_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen DeepSeek API-nyckel."
            return
        async for chunk in stream_openai_compatible(api_key, "https://api.deepseek.com", model_id, history, new_message, base_system_prompt):
            yield chunk

    # --- 4. OPENAI (Standard) ---
    elif "gpt" in model_lower or "o1" in model_lower or "openai" in model_lower:
        api_key = cfg.get("OPENAI_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen OpenAI API-nyckel."
            return
        async for chunk in stream_openai_compatible(api_key, None, model_id, history, new_message, base_system_prompt):
            yield chunk

    # --- 5. ANTHROPIC ---
    elif "claude" in model_lower or "anthropic" in model_lower:
        api_key = cfg.get("ANTHROPIC_API_KEY")
        if not api_key:
            yield "⚠️ Fel: Ingen Anthropic API-nyckel."
            return
        async for chunk in stream_anthropic(api_key, model_id, history, new_message, base_system_prompt):
            yield chunk
            
    # --- 6. OLLAMA ---
    else:
        async for chunk in stream_ollama(model_id, history, new_message, base_system_prompt):
            yield chunk

# --- IMPLEMENTATIONER ---

async def stream_gemini(model_id, history, new_message, image_data=None, system_prompt=None):
    try:
        clean_model_id = model_id.replace("Google: ", "").strip()
        if not clean_model_id: clean_model_id = "gemini-1.5-flash"

        model = genai.GenerativeModel(
            model_name=clean_model_id, 
            tools=daa_tools, 
            system_instruction=system_prompt
        )
        chat_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=chat_history, enable_automatic_function_calling=True)
        parts = [new_message]
        if image_data:
            parts.append({"mime_type": "image/jpeg", "data": image_data})

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: chat.send_message(parts))
        
        if response.text:
            text_content = response.text
            chunk_size = 10
            for i in range(0, len(text_content), chunk_size):
                yield text_content[i:i+chunk_size]
                await asyncio.sleep(0.01)
    except Exception as e:
        yield f"⚠️ Gemini Error: {str(e)}"

async def stream_openai_compatible(api_key, base_url, model_id, history, new_message, system_prompt=None):
    try:
        # Rensa bort prefix (t.ex. "Groq: " eller "OpenAI: ")
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