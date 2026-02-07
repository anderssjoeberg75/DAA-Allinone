import asyncio
import base64
from google import genai
from google.genai import types
from app.core.prompts import get_system_prompt, ANALYZE_CODE_TOOL_DESC

# --- IMPORT TOOLS ---
try:
    from app.tools.weather_core import get_weather
    from app.tools.n8n_core import get_calendar_events, call_daa_flow
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

try:
    from app.tools.garmin_core import GarminCoach
    garmin_tool = GarminCoach()
    garmin_available = True
except ImportError:
    garmin_available = False
    garmin_tool = None

MODEL = "gemini-2.5-flash-native-audio-latest"  # Only model that supports Live API currently

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
        description=ANALYZE_CODE_TOOL_DESC
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

if garmin_available:
    funcs.append(types.FunctionDeclaration(
        name="get_health_data",
        description="Fetches comprehensive health data from Garmin including sleep, heart rate, stress, body battery, HRV status, steps, and activity metrics for today."
    ))

my_tools = [types.Tool(function_declarations=funcs)] if funcs else []


class LiveChatSession:
    """
    Gemini Live Chat Session - generates both TEXT and AUDIO simultaneously.
    Unlike Voice Mode, this is for text-based chat with audio playback.
    """
    
    def __init__(self, api_key, on_text_chunk=None, on_audio_chunk=None, on_done=None, on_error=None):
        self.api_key = api_key
        self.on_text_chunk = on_text_chunk  # Callback for text (to display in UI)
        self.on_audio_chunk = on_audio_chunk  # Callback for audio (to play)
        self.on_done = on_done
        self.on_error = on_error
        
        if not self.api_key:
            raise ValueError("API Key missing")
            
        self.client = genai.Client(http_options={"api_version": "v1alpha"}, api_key=self.api_key)
        self.session = None
        self.stop_event = asyncio.Event()
        
    async def send_message(self, text):
        """Send user message to Gemini Live"""
        if not self.session:
            raise ValueError("Session not started")
        # Send using send_client_content with 'turns' parameter
        await self.session.send_client_content(
            turns=[types.Content(parts=[types.Part(text=text)])],
            turn_complete=True
        )
    
    async def handle_tool_calls(self, tool_call):
        """Handle tool/function calls from the model"""
        for fc in tool_call.function_calls:
            print(f"[LIVE CHAT] Tool called: {fc.name}")
            
            # WEATHER
            if fc.name == "get_weather":
                try: 
                    result = await get_weather()
                except Exception as e: 
                    result = f"Could not fetch weather: {e}"
                    
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="get_weather", id=fc.id, response={"result": result})]
                )

            # CALENDAR
            elif fc.name == "get_calendar":
                start = fc.args.get("start")
                end = fc.args.get("end")
                
                try:
                    result = await get_calendar_events(start=start, end=end)
                except Exception as e:
                    result = f"Could not fetch calendar: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="get_calendar", id=fc.id, response={"result": result})]
                )
            
            # CODE ANALYSIS
            elif fc.name == "analyze_code":
                try:
                    result = await asyncio.to_thread(run_code_audit)
                except Exception as e:
                    result = f"Analysis error: {e}"
                    
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="analyze_code", id=fc.id, response={"result": result})]
                )
            
            # N8N TRIGGER
            elif fc.name == "trigger_n8n":
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
                    
                    result = await call_daa_flow(webhook_slug, payload_data)
                except Exception as e:
                    result = f"n8n error: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="trigger_n8n", id=fc.id, response={"result": result})]
                )
            
            # CONTROL LIGHT
            elif fc.name == "control_light":
                entity_id = fc.args.get("entity_id", "")
                action = fc.args.get("action", "")
                
                try:
                    result = await control_light(entity_id, action)
                except Exception as e:
                    result = f"Light control error: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="control_light", id=fc.id, response={"result": result})]
                )
            
            # CONTROL VACUUM
            elif fc.name == "control_vacuum":
                entity_id = fc.args.get("entity_id", "")
                action = fc.args.get("action", "")
                
                try:
                    result = await control_vacuum(entity_id, action)
                except Exception as e:
                    result = f"Vacuum control error: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="control_vacuum", id=fc.id, response={"result": result})]
                )
            
            # GET HA STATE
            elif fc.name == "get_ha_state":
                entity_id = fc.args.get("entity_id", "")
                
                try:
                    result = await get_ha_state(entity_id)
                except Exception as e:
                    result = f"HA state error: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="get_ha_state", id=fc.id, response={"result": result})]
                )
            
            # GET SENSOR
            elif fc.name == "get_sensor":
                friendly_name = fc.args.get("friendly_name", "")
                
                try:
                    result = await get_sensor_data(friendly_name)
                except Exception as e:
                    result = f"Sensor error: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="get_sensor", id=fc.id, response={"result": result})]
                )
            
            # GET HEALTH DATA (GARMIN)
            elif fc.name == "get_health_data":
                try:
                    # Garmin is synchronous, run in executor
                    health_data = await asyncio.get_event_loop().run_in_executor(None, garmin_tool.get_health_report)
                    
                    if health_data and 'error' not in health_data:
                        # Format health data nicely for the AI
                        result = (
                            f"**HÄLSODATA FRÅN GARMIN ({health_data.get('date', 'N/A')})**:\n"
                            f"- 💤 Sömn: {health_data.get('sleep_hours', 'N/A')} (poäng: {health_data.get('sleep_score', 'N/A')})\n"
                            f"- �� REM-sömn: {health_data.get('rem_sleep', 'N/A')}, Djupsömn: {health_data.get('deep_sleep', 'N/A')}\n"
                            f"- ❤️ Vilopuls: {health_data.get('resting_heart_rate', 'N/A')} bpm\n"
                            f"- ⚡ Stress: {health_data.get('stress_avg', 'N/A')}/100 (max: {health_data.get('stress_max', 'N/A')})\n"
                            f"- 🧠 HRV Status: {health_data.get('hrv_status', 'N/A')}\n"
                            f"- 🔋 Body Battery: Nu {health_data.get('body_battery_now', 'N/A')} (högsta: {health_data.get('body_battery_high', 'N/A')}, lägsta: {health_data.get('body_battery_low', 'N/A')})\n"
                            f"- 👟 Steg: {health_data.get('steps', 'N/A')} av {health_data.get('step_goal', 'N/A')}\n"
                            f"- 🏃 Distans: {health_data.get('distance_km', 'N/A')} km\n"
                            f"- 🔥 Kalorier: {health_data.get('total_calories', 'N/A')} kcal\n"
                            f"- ⏱️ Intensiva minuter: {health_data.get('intensive_minutes', 'N/A')} min\n"
                            f"- 🫁 SpO2: {health_data.get('spo2_avg', 'N/A')}%"
                        )
                    else:
                        result = health_data.get('error', 'Could not fetch Garmin data')
                        
                except Exception as e:
                    result = f"Garmin error: {e}"
                
                await self.session.send_tool_response(
                    function_responses=[types.FunctionResponse(name="get_health_data", id=fc.id, response={"result": result})]
                )
    
    async def receive_responses(self):
        """Receive responses from Gemini Live - BOTH text and audio"""
        try:
            async for response in self.session.receive():
                # Handle tool calls
                if tool_call := response.tool_call:
                    await self.handle_tool_calls(tool_call)
                
                # Handle AI responses
                if server_content := response.server_content:
                    if model_turn := server_content.model_turn:
                        for part in model_turn.parts:
                            # TEXT for UI display
                            if part.text:
                                print(f"[LIVE CHAT] Received text: {part.text[:50]}...")
                                if self.on_text_chunk:
                                    self.on_text_chunk(part.text)


                            
                            # AUDIO for playback
                            if part.inline_data:
                                print(f"[LIVE CHAT] Received audio chunk: {len(part.inline_data.data)} bytes")
                                if self.on_audio_chunk:
                                    # Encode audio as base64 for transmission
                                    audio_b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                                    self.on_audio_chunk(audio_b64)
                    
                    # Turn complete
                    if server_content.turn_complete:
                        print("[LIVE CHAT] Turn complete")
                        if self.on_done:
                            self.on_done()
                        
        except Exception as e:
            print(f"[LIVE CHAT] Receive error: {e}")
            if self.on_error:
                self.on_error(str(e))
    
    async def start(self, initial_message=None):
        """Start a Live Chat session"""
        try:
            print(f"[LIVE CHAT] Connecting to {MODEL}...")
            
            # Fetch system prompt dynamically
            current_prompt = get_system_prompt()
            
            live_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],  # Only AUDIO (Live API doesn't support TEXT+AUDIO together)
                tools=my_tools,
                system_instruction=types.Content(parts=[types.Part(text=current_prompt)]),
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Aoede"  # Same voice as Voice Mode
                        )
                    )
                )
            )
            
            async with self.client.aio.live.connect(model=MODEL, config=live_config) as session:
                self.session = session
                print("[LIVE CHAT] Connected!")
                
                # Send initial message if provided
                if initial_message:
                    await self.send_message(initial_message)
                
                # Start receiving responses
                await self.receive_responses()
                
        except Exception as e:
            print(f"[LIVE CHAT] Error: {e}")
            if self.on_error:
                self.on_error(str(e))
    
    def stop(self):
        """Stop the session"""
        self.stop_event.set()
