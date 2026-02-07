import httpx
import json
import asyncio
import logging
from config.settings import get_config

# Setup logging so it appears in terminal
logger = logging.getLogger(__name__)

async def trigger_n8n_webhook(webhook_slug: str, payload: dict = None, method: str = "POST"):
    """
    Low-level function to call an n8n webhook.
    """
    cfg = get_config()
    base_url = cfg.get("N8N_BASE_URL")
    api_key = cfg.get("N8N_API_KEY")

    if not base_url:
        return {"error": "N8N_BASE_URL missing"}

    if not base_url.endswith("/"): base_url += "/"
    url = f"{base_url}{webhook_slug.lstrip('/')}"
    
    headers = {"Content-Type": "application/json"}
    if api_key: headers["X-N8N-API-KEY"] = api_key

    try:
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                resp = await client.get(url, params=payload or {}, headers=headers, timeout=10.0)
            else:
                resp = await client.post(url, json=payload or {}, headers=headers, timeout=10.0)
            
            print(f"[N8N DEBUG] URL: {url} | Payload: {payload} | Status: {resp.status_code}")
            print(f"[N8N DEBUG] Response: {resp.text}")

            if resp.status_code == 200:
                try: return resp.json()
                except: return resp.text
            
            # Special handling for n8n "No item to return" error (often means empty list)
            if resp.status_code == 500 and "No item to return was found" in resp.text:
                return "[]" # Return empty JSON list string

            # Handle n8n configuration errors
            if "Invalid JSON in" in resp.text and "Response Body" in resp.text:
                return "Error: The n8n 'Respond to Webhook' node has invalid JSON configuration. Please check the node settings in n8n."

            return {"error": f"Status {resp.status_code}", "details": resp.text}
    except Exception as e:
        return {"error": "Connection failed", "details": str(e)}

async def call_daa_flow(webhook_slug: str, payload: dict = None, method: str = "POST"):
    """
    High-level runner for DAA flows. 
    Handles common n8n response patterns like 'speech_text'.
    """
    print(f"[N8N] Running flow: {webhook_slug}")
    result = await trigger_n8n_webhook(webhook_slug, payload, method)

    # 1. Handle Errors
    if isinstance(result, dict) and "error" in result:
        print(f"[N8N ERROR] {result['error']}: {result.get('details', '')}")
        return f"Could not call n8n flow '{webhook_slug}': {result['error']}"

    # 2. Handle 'Workflow was started' (meaning n8n isn't waiting for output)
    if isinstance(result, dict) and result.get("message") == "Workflow was started":
        return "OK. Request sent to n8n (flow started without waiting for response)."

    # 3. Parse DAA-style response (speech_text)
    # We look for 'speech_text' in lists or dicts
    data_source = result[0] if isinstance(result, list) and result else result
    
    if isinstance(data_source, dict) and "speech_text" in data_source:
        return data_source["speech_text"]

    # 4. Fallback: Return raw data as string
    return str(result)

# --- CONVENIENCE WRAPPERS (Add new flows here!) ---

async def get_calendar_events(start: str = None, end: str = None, query: str = None):
    """
    Fetches calendar events from n8n.
    Supports structured start/end or legacy query string.
    """
    payload = {}
    if start: payload["start"] = start
    if end: payload["end"] = end
    if query: payload["query"] = query
    
    # If no specific args, default to "next 7 days" roughly
    if not payload:
        payload["query"] = "next week"

    return await call_daa_flow("get-calendar", payload, method="GET")

async def trigger_n8n_generic(slug: str, payload_str: str = "{}"):
    """Generic tool for LLM to call any webhook."""
    try:
        data = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        return await call_daa_flow(slug, data)
    except Exception as e:
        return f"Fel vid anrop av {slug}: {e}"

def trigger_n8n_webhook_sync(webhook_slug: str, payload_str: str = "{}"):
    """Legacy sync version for thread compatibility."""
    import requests
    cfg = get_config()
    base_url = cfg.get("N8N_BASE_URL", "").rstrip("/") + "/"
    url = f"{base_url}{webhook_slug.lstrip('/')}"
    try:
        data = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        resp = requests.post(url, json=data, timeout=10.0)
        return resp.json() if resp.status_code == 200 else str(resp.status_code)
    except: return "Error"
