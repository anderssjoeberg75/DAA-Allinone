import asyncio
import os
import sys
import pyaudio
import traceback
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Suppress ALSA warnings (cosmetic audio errors that don't affect functionality)
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Add backend to path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# --- IMPORT DYNAMIC TEXTS ---
# We fetch prompt function and tool description (which in turn gets from DB)
from app.core.prompts import get_system_prompt, ANALYZE_CODE_TOOL_DESC

# --- IMPORT TOOLS ---
try:
    from app.tools.weather_core import get_weather
    from app.tools.n8n_core import get_calendar_events, call_daa_flow, trigger_n8n_webhook
    weather_available = True
except ImportError: 
    weather_available = False

try:
    from app.tools.code_auditor import run_code_audit
    audit_available = True
except ImportError:
    audit_available = False

try:
    from app.tools.ha_core import control_light, control_vacuum, get_ha_state
    from app.tools.z2m_core import get_sensor_data
    ha_available = True
except ImportError:
    ha_available = False

# Fix for older python versions (if necessary)
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

load_dotenv()

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
MODEL = "gemini-2.5-flash-native-audio-latest"

# --- DEFINE TOOLS ---
funcs = []

if weather_available:
    funcs.append(types.FunctionDeclaration(
        name="get_weather", 
        description="Fetches weather forecast for current location."
    ))

    funcs.append(types.FunctionDeclaration(
        name="get_calendar",
        description="Fetches calendar events between two ISO timestamps. You MUST calculate start/end based on current date.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "start": types.Schema(type=types.Type.STRING, description="ISO timestamp (e.g. 2026-02-02T00:00:00Z)"),
                "end": types.Schema(type=types.Type.STRING, description="ISO timestamp (e.g. 2026-02-08T23:59:59Z)")
            },
            required=["start", "end"]
        )
    ))
    
    funcs.append(types.FunctionDeclaration(
        name="trigger_n8n",
        description="Triggers n8n automation workflows (e.g. 'spotify-control', 'bookMeeting')",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "webhook_slug": types.Schema(type=types.Type.STRING, description="Webhook slug (e.g. 'spotify-control')"),
                "payload": types.Schema(type=types.Type.STRING, description="JSON string with data (e.g. '{\\\"action\\\": \\\"play\\\"}')")
            },
            required=["webhook_slug"]
        )
    ))

if audit_available:
    funcs.append(types.FunctionDeclaration(
        name="analyze_code", 
        description=ANALYZE_CODE_TOOL_DESC  # <-- Fetched dynamically from DB/Prompts
    ))

if ha_available:
    funcs.append(types.FunctionDeclaration(
        name="control_light",
        description="Controls smart lights (turn on/off)",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "entity_id": types.Schema(type=types.Type.STRING, description="Home Assistant entity ID (e.g. 'light.living_room')"),
                "action": types.Schema(type=types.Type.STRING, description="Action: 'turn_on' or 'turn_off'")
            },
            required=["entity_id", "action"]
        )
    ))
    
    funcs.append(types.FunctionDeclaration(
        name="control_vacuum",
        description="Controls vacuum cleaner (start/stop/dock)",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "entity_id": types.Schema(type=types.Type.STRING, description="Vacuum entity ID (e.g. 'vacuum.roborock')"),
                "action": types.Schema(type=types.Type.STRING, description="Action: 'start', 'stop', or 'dock'")
            },
            required=["entity_id", "action"]
        )
    ))
    
    funcs.append(types.FunctionDeclaration(
        name="get_ha_state",
        description="Gets current state of a Home Assistant device",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "entity_id": types.Schema(type=types.Type.STRING, description="Entity ID (e.g. 'light.kitchen', 'sensor.temperature')")
            },
            required=["entity_id"]
        )
    ))
    
    funcs.append(types.FunctionDeclaration(
        name="get_sensor",
        description="Gets sensor data from Zigbee2MQTT",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "friendly_name": types.Schema(type=types.Type.STRING, description="Sensor friendly name from Zigbee2MQTT")
            },
            required=["friendly_name"]
        )
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
            
        self.client = genai.Client(http_options={"api_version": "v1alpha"}, api_key=self.api_key)
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
            
            # --- SETUP OUTPUT STREAM ---
            # --- SETUP OUTPUT STREAM ---
            self.output_stream = await asyncio.to_thread(
                pya.open, format=FORMAT, channels=CHANNELS, rate=24000, output=True,  # Gemini Native is 24kHz
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
                traceback.print_exc()
                await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, exception_on_overflow=False) # Try allow buffer drain?
                await asyncio.sleep(0.1)

    async def receive_audio(self):
        print("[DAA] Listening (Text-mode)...")
        try:
            while not self.stop_event.is_set():
                if not self.session: 
                    await asyncio.sleep(0.1)
                    continue
                    
                async for response in self.session.receive():
                    
                    # --- HANDLE TOOLS ---
                    if tool_call := response.tool_call:
                        # If the model is calling a tool, previous text was likely internal reasoning/CoT.
                        # We discard it so we don't speak "I will now check the calendar..."
                        self.accumulated_text = ""
                        
                        for fc in tool_call.function_calls:
                            
                            # 1. WEATHER
                            if fc.name == "get_weather":
                                print("[DAA] Tool: Fetching weather...")
                                try: 
                                    w = await get_weather()
                                except Exception as e: 
                                    w = f"Could not fetch weather: {e}"
                                    
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="get_weather", id=fc.id, response={"result": w})]
                                )

                            # 1.5 KALENDER
                            elif fc.name == "get_calendar":
                                print("[DAA] Tool: Fetching calendar...")
                                start = fc.args.get("start")
                                end = fc.args.get("end")
                                
                                try:
                                    cal_res = await get_calendar_events(start=start, end=end)
                                except Exception as e:
                                    cal_res = f"Could not fetch calendar: {e}"
                                
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="get_calendar", id=fc.id, response={"result": cal_res})]
                                )

                            
                            # 2. KODANALYS
                            elif fc.name == "analyze_code":
                                print("[DAA] Tool: Analyzing code...")
                                if self.on_status: self.on_status("Analyzing code...")
                                
                                # Run in thread to not block audio stream
                                try:
                                    res = await asyncio.to_thread(run_code_audit)
                                except Exception as e:
                                    res = f"Analysis error: {e}"
                                    
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="analyze_code", id=fc.id, response={"result": res})]
                                )
                                if self.on_status: self.on_status("DAA Live: Active")
                            
                            # 3. N8N TRIGGER
                            elif fc.name == "trigger_n8n":
                                print(f"[DAA] Tool: Triggering n8n webhook...")
                                webhook_slug = fc.args.get("webhook_slug", "")
                                payload = fc.args.get("payload", "{}")
                                
                                try:
                                    import json
                                    if isinstance(payload, str):
                                        try:
                                            payload_data = json.loads(payload)
                                        except:
                                            payload_data = {}
                                    else:
                                        payload_data = payload
                                    
                                    res = await call_daa_flow(webhook_slug, payload_data)
                                except Exception as e:
                                    res = f"n8n error: {e}"
                                
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="trigger_n8n", id=fc.id, response={"result": res})]
                                )
                            
                            # 4. CONTROL LIGHT
                            elif fc.name == "control_light":
                                print(f"[DAA] Tool: Controlling light...")
                                entity_id = fc.args.get("entity_id", "")
                                action = fc.args.get("action", "")
                                
                                try:
                                    res = await control_light(entity_id, action)
                                except Exception as e:
                                    res = f"Light control error: {e}"
                                
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="control_light", id=fc.id, response={"result": res})]
                                )
                            
                            # 5. CONTROL VACUUM
                            elif fc.name == "control_vacuum":
                                print(f"[DAA] Tool: Controlling vacuum...")
                                entity_id = fc.args.get("entity_id", "")
                                action = fc.args.get("action", "")
                                
                                try:
                                    res = await control_vacuum(entity_id, action)
                                except Exception as e:
                                    res = f"Vacuum control error: {e}"
                                
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="control_vacuum", id=fc.id, response={"result": res})]
                                )
                            
                            # 6. GET HA STATE
                            elif fc.name == "get_ha_state":
                                print(f"[DAA] Tool: Getting device state...")
                                entity_id = fc.args.get("entity_id", "")
                                
                                try:
                                    res = await get_ha_state(entity_id)
                                except Exception as e:
                                    res = f"HA state error: {e}"
                                
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="get_ha_state", id=fc.id, response={"result": res})]
                                )
                            
                            # 7. GET SENSOR
                            elif fc.name == "get_sensor":
                                print(f"[DAA] Tool: Getting sensor data...")
                                friendly_name = fc.args.get("friendly_name", "")
                                
                                try:
                                    res = await get_sensor_data(friendly_name)
                                except Exception as e:
                                    res = f"Sensor error: {e}"
                                
                                await self.session.send_tool_response(
                                    function_responses=[types.FunctionResponse(name="get_sensor", id=fc.id, response={"result": res})]
                                )

                    # --- HANDLE AI RESPONSE ---
                    if server_content := response.server_content:
                        if model_turn := server_content.model_turn:
                            for part in model_turn.parts:
                                if part.text:
                                    if self.on_transcription: self.on_transcription(part.text)
                                if part.inline_data:
                                    if self.output_stream:
                                        await asyncio.to_thread(self.output_stream.write, part.inline_data.data)

                        if server_content.turn_complete:
                            if self.on_turn_complete: self.on_turn_complete()
                            
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Receive Error: {e}")
        except Exception as e:
            print(f"Receive Error: {e}")
            traceback.print_exc()

    async def run(self):
        while not self.stop_event.is_set():
            try:
                print(f"[DAA] Connecting to {MODEL}...")
                if self.on_status: self.on_status("Connecting...")
                
                # IMPORTANT: Fetch prompt dynamically EVERY time we connect.
                # This makes DB changes take effect immediately next session.
                current_prompt = get_system_prompt()

                
                live_config = types.LiveConnectConfig(
                    response_modalities=["AUDIO"], 
                    tools=my_tools,
                    system_instruction=types.Content(parts=[types.Part(text=current_prompt)]),
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Aoede"
                            )
                        )
                    )
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
                            try: await session.send(input={"data": msg["data"], "mime_type": msg["mime_type"]}, end_of_turn=False)
                            except: traceback.print_exc()
                            
                    tg.create_task(send_from_queue())
                    
                    if self.on_status: self.on_status("DAA Live: Active")
                    print("[DAA] CONNECTED!")
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