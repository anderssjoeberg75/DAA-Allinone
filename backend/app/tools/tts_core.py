import os
import requests
from config.settings import get_config

def generate_elevenlabs_audio(text):
    """
    Genererar ljud via ElevenLabs API.
    Hämtar API-nyckel och Voice ID från databasen.
    """
    cfg = get_config()
    
    api_key = cfg.get("ELEVENLABS_API_KEY")
    voice_id = cfg.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Standard: Rachel
    
    # Vi använder den snabbaste modellen för att undvika timeouts
    model_id = "eleven_turbo_v2_5" 

    if not api_key:
        print("[TTS] Error: Ingen ElevenLabs API-nyckel i inställningarna.")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    try:
        # ÄNDRING HÄR: timeout=30 (ger ElevenLabs 30 sekunder på sig istället för 10)
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.content
        else:
            print(f"[TTS] ElevenLabs Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"[TTS] Request Error: {e}")
        return None