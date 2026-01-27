import asyncio
import os
import sys
import pyaudio
import traceback
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Lägg till backend i sökvägen för att hitta moduler
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# --- IMPORTERA DYNAMISKA TEXTER ---
# Vi hämtar prompt-funktionen och verktygsbeskrivningen (som i sin tur hämtar från DB)
from app.core.prompts import get_system_prompt, ANALYZE_CODE_TOOL_DESC

# --- IMPORTERA VERKTYG ---
try:
    from app.tools.weather_core import get_weather
    weather_available = True
except ImportError: 
    weather_available = False

try:
    from app.tools.code_auditor import run_code_audit
    audit_available = True
except ImportError:
    audit_available = False

# Fix för äldre python-versioner (om nödvändigt)
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

load_dotenv()

# Ljudinställningar
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
MODEL = "models/gemini-2.0-flash-exp"

# --- DEFINIERA VERKTYG ---
funcs = []

if weather_available:
    funcs.append(types.FunctionDeclaration(
        name="get_weather", 
        description="Hämtar väderprognos för aktuell plats."
    ))

if audit_available:
    funcs.append(types.FunctionDeclaration(
        name="analyze_code", 
        description=ANALYZE_CODE_TOOL_DESC  # <-- Hämtas dynamiskt från DB/Prompts
    ))

my_tools = [types.Tool(function_declarations=funcs)] if funcs else []

pya = pyaudio.PyAudio()

class AudioLoop:
    def __init__(self, api_key, on_audio_data=None, on_transcription=None, on_status=None, on_error=None, on_turn_complete=None, input_device_index=None):
        self.api_key = api_key
        self.on_transcription = on_transcription
        self.on_status = on_status 
        self.on_error = on_error
        self.on_turn_complete = on_turn_complete
        self.input_device_index = input_device_index
        self.out_queue = asyncio.Queue(maxsize=10)
        self.paused = False
        self.session = None
        
        if not self.api_key: 
            raise ValueError("API Key missing")
            
        self.client = genai.Client(http_options={"api_version": "v1beta"}, api_key=self.api_key)
        self.stop_event = asyncio.Event()

    def set_paused(self, paused): 
        self.paused = paused
        
    def stop(self): 
        self.stop_event.set()

    async def listen_audio(self):
        try:
            mic_info = pya.get_default_input_device_info()
            print(f"[DAA] Mic: {mic_info['name']}")
            
            self.audio_stream = await asyncio.to_thread(
                pya.open, format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True,
                input_device_index=self.input_device_index if self.input_device_index is not None else mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
        except OSError as e:
            if self.on_error: self.on_error(f"Mic Error: {e}")
            return
            
        while not self.stop_event.is_set():
            if self.paused: 
                await asyncio.sleep(0.1)
                continue
            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, exception_on_overflow=False)
                if self.out_queue: 
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
            except: 
                await asyncio.sleep(0.1)

    async def receive_audio(self):
        print("[DAA] Lyssnar (Text-mode)...")
        try:
            while not self.stop_event.is_set():
                if not self.session: 
                    await asyncio.sleep(0.1)
                    continue
                    
                async for response in self.session.receive():
                    
                    # --- HANTERA VERKTYG ---
                    if tool_call := response.tool_call:
                        for fc in tool_call.function_calls:
                            
                            # 1. VÄDER
                            if fc.name == "get_weather":
                                print("[DAA] Verktyg: Hämtar väder...")
                                try: 
                                    w = await get_weather()
                                except Exception as e: 
                                    w = f"Kunde inte hämta väder: {e}"
                                    
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="get_weather", id=fc.id, response={"result": w})]
                                )
                            
                            # 2. KODANALYS
                            elif fc.name == "analyze_code":
                                print("[DAA] Verktyg: Analyserar kod...")
                                if self.on_status: self.on_status("Analyserar kod...")
                                
                                # Kör i tråd för att inte blockera ljudströmmen
                                try:
                                    res = await asyncio.to_thread(run_code_audit)
                                except Exception as e:
                                    res = f"Analysfel: {e}"
                                    
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="analyze_code", id=fc.id, response={"result": res})]
                                )
                                if self.on_status: self.on_status("DAA Live: Active")

                    # --- HANTERA SVAR FRÅN AI ---
                    if server_content := response.server_content:
                        if model_turn := server_content.model_turn:
                            for part in model_turn.parts:
                                if part.text:
                                    if self.on_transcription: self.on_transcription(part.text)
                        
                        if server_content.turn_complete:
                            if self.on_turn_complete: self.on_turn_complete()
                            
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Receive Error: {e}")
            pass

    async def run(self):
        while not self.stop_event.is_set():
            try:
                print(f"[DAA] Connecting to {MODEL}...")
                if self.on_status: self.on_status("Connecting...")
                
                # VIKTIGT: Hämta prompten dynamiskt VARJE gång vi ansluter.
                # Detta gör att ändringar i databasen slår igenom direkt vid nästa session.
                current_prompt = get_system_prompt()
                
                live_config = types.LiveConnectConfig(
                    response_modalities=["TEXT"], 
                    tools=my_tools,
                    system_instruction=types.Content(parts=[types.Part(text=current_prompt)])
                )

                async with (
                    self.client.aio.live.connect(model=MODEL, config=live_config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session
                    self.out_queue = asyncio.Queue(maxsize=10)
                    
                    tg.create_task(self.listen_audio())
                    tg.create_task(self.receive_audio())
                    
                    async def send_from_queue():
                        while not self.stop_event.is_set():
                            msg = await self.out_queue.get()
                            try: await session.send_realtime_input(data=msg["data"], mime_type=msg["mime_type"])
                            except: pass
                            
                    tg.create_task(send_from_queue())
                    
                    if self.on_status: self.on_status("DAA Live: Active")
                    print("[DAA] ANSLUTEN!")
                    await self.stop_event.wait()
                    
            except asyncio.CancelledError: 
                break
            except Exception as e:
                print(f"[DAA ERROR] {e}")
                if "403" in str(e) or "1008" in str(e): 
                    if self.on_error: self.on_error("API Error: Check Key/Quota")
                    break
                await asyncio.sleep(2)
            finally:
                if hasattr(self, 'audio_stream'):
                    try: self.audio_stream.close()
                    except: pass