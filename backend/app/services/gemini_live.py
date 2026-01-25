import asyncio
import os
import sys
import pyaudio
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Importera väder
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from app.tools.weather_core import get_weather
    weather_available = True
except: 
    weather_available = False

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
MODEL = "models/gemini-2.0-flash-exp"

my_tools = []
if weather_available:
    my_tools.append(types.Tool(function_declarations=[
        types.FunctionDeclaration(name="get_weather", description="Hämtar väderprognos.")
    ]))

# HÄR ÄR DEN NYA INSTRUKTIONEN (SAMMA SOM I TEXT-CHATTEN)
SYSTEM_PROMPT = """
Du är DAA (Digital Advanced Assistant).
Du är användarens butler och högra hand, 'Anders'.
Du är en blandning av en professionell assistent och en superdator.
Du hjälper till med information, analys och styrning.
Svara alltid på svenska.
Svara kort, koncist och hjälpsamt.
Inga långa utläggningar om att du är en språkmodell.
"""

live_config = types.LiveConnectConfig(
    response_modalities=["TEXT"], # Vi vill ha TEXT så vi kan använda ElevenLabs
    tools=my_tools,
    system_instruction=types.Content(parts=[types.Part(text=SYSTEM_PROMPT)])
)

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
        if not self.api_key: raise ValueError("API Key missing")
        self.client = genai.Client(http_options={"api_version": "v1beta"}, api_key=self.api_key)
        self.stop_event = asyncio.Event()

    def set_paused(self, paused): self.paused = paused
    def stop(self): self.stop_event.set()

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        print(f"[DAA] Mic: {mic_info['name']}")
        try:
            self.audio_stream = await asyncio.to_thread(
                pya.open, format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True,
                input_device_index=self.input_device_index if self.input_device_index is not None else mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
        except OSError as e:
            if self.on_error: self.on_error(f"Mic Error: {e}")
            return
        while True:
            if self.paused: await asyncio.sleep(0.1); continue
            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, exception_on_overflow=False)
                if self.out_queue: await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
            except: await asyncio.sleep(0.1)

    async def receive_audio(self):
        print("[DAA] Lyssnar (Text-mode)...")
        try:
            while True:
                if not self.session: await asyncio.sleep(0.1); continue
                async for response in self.session.receive():
                    
                    # Verktyg
                    if tool_call := response.tool_call:
                        for fc in tool_call.function_calls:
                            if fc.name == "get_weather":
                                print("[DAA] Hämtar väder...")
                                try: w = await get_weather()
                                except: w = "Kunde inte hämta väder."
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="get_weather", id=fc.id, response={"result": w})]
                                )

                    # Text
                    if server_content := response.server_content:
                        if model_turn := server_content.model_turn:
                            for part in model_turn.parts:
                                if part.text:
                                    # Skicka textbiten direkt till skärmen
                                    if self.on_transcription: self.on_transcription(part.text)
                        
                        # VIKTIGT: Signalen som triggar uppläsning
                        if server_content.turn_complete:
                            if self.on_turn_complete: self.on_turn_complete()
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Receive Error: {e}")
            raise e 

    async def run(self):
        while not self.stop_event.is_set():
            try:
                print(f"[DAA] Connecting to {MODEL}...")
                if self.on_status: self.on_status("Connecting...")
                async with (
                    self.client.aio.live.connect(model=MODEL, config=live_config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session
                    self.out_queue = asyncio.Queue(maxsize=10)
                    tg.create_task(self.listen_audio())
                    tg.create_task(self.receive_audio())
                    async def send_from_queue():
                        while True:
                            msg = await self.out_queue.get()
                            try: await session.send_realtime_input(data=msg["data"], mime_type=msg["mime_type"])
                            except: await session.send(input=msg, end_of_turn=False)
                    tg.create_task(send_from_queue())
                    if self.on_status: self.on_status("DAA Live: Active")
                    print("[DAA] ANSLUTEN!")
                    await self.stop_event.wait()
            except asyncio.CancelledError: break
            except Exception as e:
                print(f"[DAA ERROR] {e}")
                if "403" in str(e) or "1008" in str(e): break
                await asyncio.sleep(2)
            finally:
                if hasattr(self, 'audio_stream'):
                    try: self.audio_stream.close()
                    except: pass