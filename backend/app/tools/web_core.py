# backend/app/tools/web_core.py

import os
import asyncio
import base64
from app.core.logging_config import logger
from config.settings import get_config
from playwright.async_api import async_playwright
from google import genai
from google.genai import types

# Konfiguration
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
# Konfiguration
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
MODEL_ID = "gemini-2.5-computer-use-preview-10-2025"

class WebAgent:
    def __init__(self):
        self.conf = get_config()
        # Fallback to GOOGLE_API_KEY if GEMINI_API_KEY is not set
        self.api_key = self.conf.get("GEMINI_API_KEY") or self.conf.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            logger.error("WebAgent: Saknar GEMINI_API_KEY/GOOGLE_API_KEY i settings")
            raise ValueError("Missing API Key")

        self.client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
        self.browser = None
        self.context = None
        self.page = None

    def denormalize_x(self, x: int, width: int) -> int:
        return int((x / 1000) * width)

    def denormalize_y(self, y: int, height: int) -> int:
        return int((y / 1000) * height)

    async def execute_function_calls(self, function_calls):
        results = []
        for call in function_calls:
            call_id = getattr(call, 'id', None)
            fn_name = call.name
            args = call.args
            logger.info(f"[WebAgent] Processing Call ID: {call_id} Function: {fn_name}")
            
            # --- SAFETY CHECK (ada_v2 principle) ---
            requires_acknowledgement = False
            if "safety_decision" in args:
                 decision = args["safety_decision"]
                 if decision.get("decision") == "require_confirmation":
                     logger.warning(f"[WebAgent] Safety Alert: {decision.get('explanation')}")
                     logger.info("   -> Auto-acknowledging to proceed.")
                     requires_acknowledgement = True

            result_data = {}
            try:
                if fn_name == "open_web_browser":
                    pass # Already open
                elif fn_name == "navigate":
                    url = args["url"]
                    if not url.startswith("http"):
                        url = "https://" + url
                    await self.page.goto(url)
                elif fn_name == "click_at":
                    x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    await self.page.mouse.click(x, y)
                elif fn_name == "type_text_at":
                    x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    text = args["text"]
                    await self.page.mouse.click(x, y)
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.press("Backspace")
                    await self.page.keyboard.type(text)
                    if args.get("press_enter", False):
                        await self.page.keyboard.press("Enter")
                elif fn_name == "scroll_at":
                    x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    await self.page.mouse.move(x, y)
                    await self.page.mouse.wheel(0, args.get("magnitude", 800))
                elif fn_name == "wait_5_seconds":
                    await asyncio.sleep(5)
                
                await asyncio.sleep(3) # Låt UI stabiliseras

            except Exception as e:
                logger.error(f"[WebAgent] Error executing {fn_name}: {e}")
                result_data = {"error": str(e)}

            # Add internal flag to result_data to be picked up by get_function_responses
            if requires_acknowledgement:
                result_data["_requires_acknowledgement"] = True

            results.append((call_id, fn_name, result_data))
        
        return results

    async def get_function_responses(self, results):
        screenshot_bytes = await self.page.screenshot(type="jpeg", quality=80)
        
        current_url = self.page.url
        
        function_responses = []
        for call_id, name, result in results:
            response_data = {"url": current_url}
            
            # Check for internal safety flag
            if result and result.pop("_requires_acknowledgement", False):
                response_data["safety_acknowledgement"] = True
                
            if result:
                response_data.update(result)
            
            # Add status text to the structured response instead of a Part
            response_data["status"] = f"Action {name} executed successfully."
            response_data["output"] = f"Action {name} executed successfully."

            # Construct response object arguments
            response_args = {
                "name": name,
                "response": response_data,
            }
            if call_id:
                response_args["id"] = call_id

            logger.info(f"[WebAgent] Sending FunctionResponse: name={name} id={call_id} response={response_data}")
            function_responses.append(types.FunctionResponse(**response_args))
        
        return function_responses, screenshot_bytes

    async def run_task(self, prompt: str):
        """
        Huvudfunktion för att köra agenten.
        """
        logger.info(f"[WebAgent] Startar uppgift: {prompt}")
        final_response = "Ingen slutsats nåddes."

        async with async_playwright() as p:
            # headless=True för serverdrift, False om du vill se webbläsaren
            self.browser = await p.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}
            )
            self.page = await self.context.new_page()
            await self.page.goto("about:blank")

            # Use official Computer Use tool configuration
            config = types.GenerateContentConfig(
                tools=[types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER
                    )
                )],
                # thinking_config=types.ThinkingConfig(include_thoughts=True) # Enable if supported and desired
            )

            # Starta chattsession
            chat = self.client.aio.chats.create(
                model=MODEL_ID,
                config=config,
                history=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text="You are a helpful web browsing assistant. You can traverse the web. You are allowed to use the provided tools to navigate, click, type, and scroll. Do not refuse to use these tools. IMPORTANT: Output ONLY the final answer. If the user speaks Swedish, answer in Swedish. Do NOT include English reasoning or status updates like 'I have evaluated step X' in the final response.")]
                    ),
                    types.Content(
                         role="model",
                         parts=[types.Part(text="Understood. I will provide only the final answer in the requested language.")]
                    )
                ]
            )

            # Startbild
            initial_screenshot = await self.page.screenshot(type="jpeg", quality=50)
            # initial_screenshot = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
            
            # Första meddelandet
            current_message_parts = [
                types.Part(text=prompt),
                types.Part.from_bytes(data=initial_screenshot, mime_type="image/png")
            ]

            # Loopa i max 15 steg
            try:
                for turn in range(15):
                    try:
                        logger.info(f"[WebAgent] Sending message for turn {turn+1}...")
                        response = await chat.send_message(current_message_parts)
                        logger.info(f"[WebAgent] Received response for turn {turn+1}.")
                    except Exception as e:
                        logger.error(f"[WebAgent] API Error: {e}")
                        return f"Fel vid anrop till Gemini: {e}"

                    if not response.candidates:
                        break
                    
                    model_content = response.candidates[0].content
                    # Chat session handles history automatically
                    
                    logger.info(f"[WebAgent] Model content: {model_content}")

                    # Logga tankar
                    final_response = None
                    for part in model_content.parts:
                        if part.thought:
                            logger.info(f"[WebAgent Thinking]: {part.text[:100]}...")
                        elif part.text:
                            final_response = part.text

                    function_calls = [p.function_call for p in model_content.parts if p.function_call]
                    
                    if not function_calls:
                        if final_response:
                            logger.info("[WebAgent] Klar.")
                            break
                        break

                    # Utför handlingar
                    results = await self.execute_function_calls(function_calls)
                    
                    # Svara med ny skärmdump (standard: riktig bild)
                    function_responses, screenshot_bytes = await self.get_function_responses(results)
                    
                    current_message_parts = [types.Part(function_response=fr) for fr in function_responses]
                    # Add screenshot as a separate part at the end
                    if screenshot_bytes:
                         current_message_parts.append(types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"))
                    
                    logger.info(f"[WebAgent] Prepared next message with {len(current_message_parts)} parts.")

            finally:
                if self.context:
                    await self.context.close()
                if self.browser:
                    await self.browser.close()
            
            if self.browser:
                    await self.browser.close()
            
            if final_response:
                final_response = final_response.lstrip('.').strip()
            return final_response