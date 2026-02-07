import time
import json
import asyncio
from app.core.logging_config import logger
from config.settings import get_config

# Import tool classes
from app.tools.garmin_core import GarminCoach
from app.tools.strava_core import StravaTool
from app.tools.web_core import WebAgent

class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.cache = {}
        self.conf = get_config()
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize known tools based on configuration."""
        # 1. Garmin
        if self.conf.get("GARMIN_EMAIL") and self.conf.get("GARMIN_PASSWORD"):
            try:
                self.tools["garmin"] = GarminCoach()
                logger.info("Garmin tool initialized")
            except Exception as e:
                logger.error(f"Garmin init failed: {e}")

        # 2. Strava
        if self.conf.get("STRAVA_CLIENT_ID") and self.conf.get("STRAVA_REFRESH_TOKEN"):
            try:
                self.tools["strava"] = StravaTool()
                logger.info("Strava tool initialized")
            except Exception as e:
                logger.error(f"Strava init failed: {e}")

        # 3. Web Agent (Computer Use)
        # Vi initierar denna om GEMINI_API_KEY finns, vilket web_core.py kollar internt
        try:
            self.tools["web_agent"] = WebAgent()
            logger.info("WebAgent tool initialized")
        except Exception as e:
            logger.error(f"WebAgent init failed: {e}")

    async def get_tool_data(self, tool_name, force_refresh=False, **kwargs):
        """
        Generic method to fetch data from a tool with internal caching.
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return None

        # Special handling for Web Agent which is a task runner, not a data fetcher
        if tool_name == "web_agent":
            # Web agent doesn't use standard caching logic
            return tool

        current_time = time.time()
        cache_key = f"{tool_name}_data"
        
        # Cache durations (in seconds)
        durations = {
            "garmin": 900,  # 15 mins
            "strava": 300   # 5 mins
        }
        duration = durations.get(tool_name, 300)

        last_fetch = self.cache.get(f"{tool_name}_last_fetch", 0)
        cached_data = self.cache.get(cache_key)

        if not force_refresh and cached_data and (current_time - last_fetch < duration):
            return cached_data

        # Fetch new data
        try:
            logger.info(f"Fetching data for {tool_name}...")
            if tool_name == "garmin":
                data = await asyncio.to_thread(tool.get_health_report)
            elif tool_name == "strava":
                data = await tool.get_health_report(limit=1)
            else:
                data = None

            if data:
                # Validate Strava error dict
                if isinstance(data, dict) and "error" in data:
                    logger.error(f"{tool_name} returned error: {data['error']}")
                    return None
                
                self.cache[cache_key] = data
                self.cache[f"{tool_name}_last_fetch"] = current_time
                logger.info(f"{tool_name} data fetched successfully")
                return data
                
        except Exception as e:
            logger.error(f"{tool_name} fetch error: {e}")
            return None

    def check_and_inject_context(self, text, system_prompt):
        """
        Checks user text for triggers and injects data into system prompt if needed.
        Returns potentially modified system_prompt.
        """
        return text, system_prompt # This functionality will be handled in main server loop but logic helper here 

    async def get_context_injection(self, text):
        """
        Returns a string to be appended to the system prompt based on triggers.
        """
        injection = ""
        text_lower = text.lower()

        # Garmin Logic
        garmin_triggers = ["puls", "sömn", "stress", "garmin", "mår jag", "status", "kropp"]
        if any(t in text_lower for t in garmin_triggers):
            logger.info("Garmin trigger matched")
            data = await self.get_tool_data("garmin")
            if data:
                data_block = (
                    f"   - 💤 Sömn: {data.get('sleep_hours')} timmar\n"
                    f"   - ❤️ Vilopuls: {data.get('resting_heart_rate')} bpm\n"
                    f"   - ⚡ Stressnivå: {data.get('stress_avg')}/100\n"
                    f"   - 🔋 Body Battery: {data.get('body_battery_now', 'N/A')}\n"
                    f"   - 🧠 HRV Status: {data.get('hrv_status', 'N/A')}\n"
                    f"   - 😴 Sömn poäng: {data.get('sleep_score', 'N/A')}\n"
                )
                injection += f"\n\n[HÄLSODATA FRÅN GARMIN IDAG]:\n{data_block}\n\nINSTRUKTION: Analysera ovanstående data. Ge konkreta råd baserat på värdena."

        # Strava Logic
        strava_triggers = ["strava", "löpning", "cykling", "pass", "träning", "aktivitet", "tränade"]
        if any(t in text_lower for t in strava_triggers):
            logger.info("Strava trigger matched")
            data = await self.get_tool_data("strava")
            if data:
                data_str = json.dumps(data, indent=2, ensure_ascii=False)
                injection += f"\n\n[SENASTE TRÄNINGSPASS FRÅN STRAVA]:\n{data_str}\n\nINSTRUKTION: Använd denna data för att svara detaljerat om träningen."

        return injection
    
    async def run_web_agent(self, prompt):
        """
        Executes the WebAgent task if available.
        """
        agent = self.tools.get("web_agent")
        if not agent:
            return "WebAgent not active (missing API key or dependency)."
        
        return await agent.run_task(prompt)

# Global instance
tool_registry = ToolRegistry()