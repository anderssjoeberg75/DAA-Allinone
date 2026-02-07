import wave
import io
import asyncio
import httpx
from config.settings import get_config

async def generate_tts_audio(text):
    """
    Generates audio via ElevenLabs TTS API.
    Returns audio bytes (MP3 format from ElevenLabs).
    """
    import re
    # Fix negative temperature pronunciation: "-5" -> "minus 5"
    # Matches hyphen followed by digits, optionally with decimal
    text = re.sub(r'(?<!\w)-(\d+(?:[.,]\d+)?)', r'minus \1', text)

    cfg = get_config()
    api_key = cfg.get("ELEVENLABS_API_KEY")
    voice_id = cfg.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Default: Rachel
    
    if not api_key:
        print("[TTS] Error: No ElevenLabs API key configured.")
        return None
    
    if not voice_id:
        print("[TTS] Error: No ElevenLabs voice ID configured.")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",  # Supports Swedish
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    print(f"[TTS] Generating audio with ElevenLabs (voice: {voice_id})...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                audio_data = response.content
                print(f"[TTS] Generated {len(audio_data)} bytes of audio")
                return audio_data
            else:
                print(f"[TTS] ElevenLabs Error {response.status_code}: {response.text}")
                return None

    except Exception as e:
        print(f"[TTS] ElevenLabs Generation Error: {e}")
        return None