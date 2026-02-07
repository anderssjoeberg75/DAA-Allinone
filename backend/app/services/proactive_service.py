
import asyncio
import time
import logging
from datetime import datetime
from app.core.database import save_message
from app.services.llm_handler import stream_response
from app.tools.garmin_core import GarminCoach

logger = logging.getLogger(__name__)

class ProactiveService:
    def __init__(self, sio):
        self.sio = sio
        self.running = False
        self.garmin = GarminCoach()
        self.last_check = {}
        self.max_cache_entries = 100  # Prevent memory leak
        
    async def start(self):
        """Start the background loop."""
        self.running = True
        logger.info("[PROACTIVE] Service started.")
        while self.running:
            try:
                await self.check_triggers()
            except Exception as e:
                logger.error(f"[PROACTIVE] Loop Error: {e}")
            
            # Sleep for 60 seconds
            await asyncio.sleep(60)

    def stop(self):
        self.running = False
        logger.info("[PROACTIVE] Service stopping...")

    async def check_triggers(self):
        """Check all proactive triggers."""
        # Cleanup old cache entries to prevent memory leak
        if len(self.last_check) > self.max_cache_entries:
            logger.info(f"[PROACTIVE] Cleaning cache ({len(self.last_check)} entries)")
            oldest_keys = sorted(self.last_check.items(), key=lambda x: x[1])[:50]
            for key, _ in oldest_keys:
                del self.last_check[key]
        
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # KEY: "trigger_name": timestamp
        
        # 1. MORNING BRIEFING (07:00 - 08:00)
        # Check if we haven't run this today yet
        trigger_id = f"morning_{now.strftime('%Y-%m-%d')}"
        if 7 <= current_hour < 9 and trigger_id not in self.last_check:
            logger.info("[PROACTIVE] Checking Morning Trigger...")
            await self.run_morning_briefing(trigger_id)
            
        # 2. STRESS CHECK (Every hour approx, but we check every loop which is 60s)
        # We should only trigger this if we haven't triggered it recently (e.g. last 4 hours)
        
        stress_trigger_key = f"stress_{now.strftime('%Y-%m-%d')}_{current_hour}" # Unique per hour
        # Rate limit: Don't check too often to avoid API spam? 
        # Actually, let's just check once per hour block if active.
        
        # Only check between 08:00 - 22:00
        if 8 <= current_hour < 22 and stress_trigger_key not in self.last_check:
             # Only check if we haven't done so this hour
             await self.run_stress_check(stress_trigger_key)

    async def run_morning_briefing(self, trigger_id):
        """Analyze sleep data and send a message if interesting."""
        logger.info(f"[PROACTIVE] Starting morning briefing for {trigger_id}")
        try:
            # Mark as run immediately to avoid loop
            self.last_check[trigger_id] = time.time()
            
            # Fetch Garmin Data (sync function run in executor)
            logger.info("[PROACTIVE] Fetching Garmin data...")
            loop = asyncio.get_event_loop()
            health_data = await loop.run_in_executor(None, self.garmin.get_health_report)
            
            logger.info(f"[PROACTIVE] Garmin data received: {health_data}")
            
            if not health_data or 'error' in health_data:
                logger.warning(f"[PROACTIVE] No health data for morning briefing. Error: {health_data.get('error') if health_data else 'None'}")
                return

            sleep_score = health_data.get('sleep_score')
            logger.info(f"[PROACTIVE] Sleep score: {sleep_score}")
            # If sleep score is low/interesting, trigger message
            # logic: trigger if sleep is bad (<60) OR really good (>90)
            should_trigger = False
            context = ""
            
            try:
                score_val = int(sleep_score)
                if score_val < 60:
                    should_trigger = True
                    context = f"Användaren har sovit dåligt. Sömnpoäng: {score_val}."
                elif score_val > 90:
                    should_trigger = True
                    context = f"Användaren har sovit fantastiskt! Sömnpoäng: {score_val}."
            except: pass

            if should_trigger:
                await self.send_proactive_message("morning_brief", context)
            else:
                 logger.info(f"[PROACTIVE] Sleep score {sleep_score} not triggering threshold.")

        except Exception as e:
            logger.error(f"[PROACTIVE] Morning check failed: {e}")

    async def send_proactive_message(self, trigger_type, context):
        """Generate and send the message."""
        logger.info(f"[PROACTIVE] Generating message for {trigger_type}...")
        
        from config.settings import get_config
        cfg = get_config()
        user_name = cfg.get("USER_NAME", "Användare")

        system_prompt = (
            f"Du är DAA, en proaktiv AI-assistent. "
            f"Du ska initiera ett samtal med {user_name} baserat på data. "
            "Var kort, omtänksam och naturlig. Inte robotaktig. "
            "Avsluta med en relevant fråga."
            f"\n\nKONTEXT: {context}"
        )
        
        # Generate message using Gemini (via stream_response helper but simplified)
        # We cheat and use a "system" role prompt to generate the opening line
        full_msg = ""
        try:
            # We use a dummy history to prompt the generation
            dummy_history = [{"role": "user", "content": "Generera ett proaktivt meddelande till mig baserat på kontexten."}]
            
            # Call LLM
            # We consume the generator
            async for chunk in stream_response("gemini-2.0-flash", dummy_history, "Generera startreplik", system_injection=system_prompt):
                if chunk and "⚠️" not in chunk:
                    full_msg += chunk
            
            if full_msg:
                # 1. Save to DB directly as assistant message
                # Note: We verify save_message signature: session_id, role, text
                save_message("hybrid", "assistant", full_msg)
                
                # 2. Emit to socket
                # We emit a special event 'proactive_message' or just standard 'ai_chunk' sequence?
                # Let's simulate a standard incoming message stream
                await self.sio.emit('ai_chunk', {'text': f"\n\n[DAA PROACTIVE]: {full_msg}\n"})
                await self.sio.emit('ai_done', {})
                
                logger.info(f"[PROACTIVE] Sent: {full_msg}")

        except Exception as e:
            logger.error(f"[PROACTIVE] Generation failed: {e}")

    async def run_stress_check(self, trigger_id):
        """Checks current stress level and triggers if high."""
        try:
             # Fetch Garmin Data
             loop = asyncio.get_event_loop()
             logger.info("[PROACTIVE] Fetching Garmin stress data...")
             health_data = await loop.run_in_executor(None, self.garmin.get_health_report)
             
             if not health_data or 'error' in health_data:
                 return

             stress_avg = health_data.get('stress_avg')
             # Note: stress_avg is daily average.
             
             should_trigger = False
             context = ""
             
             try:
                 stress_val = int(stress_avg)
                 logger.info(f"[PROACTIVE] Daily Stress Avg: {stress_val}")
                 if stress_val > 75: # High stress threshold
                     should_trigger = True
                     context = f"Användaren har en hög genomsnittlig stressnivå idag ({stress_val}). Fråga om de behöver en paus."
             except: pass
             
             if should_trigger:
                 await self.send_proactive_message("stress_alert", context)
                 
        except Exception as e:
            logger.error(f"[PROACTIVE] Stress check failed: {e}")
