import httpx
import json
import asyncio
import logging
from config.settings import get_config

# Vi sätter upp loggning så det syns i terminalen
logger = logging.getLogger(__name__)

async def trigger_n8n_webhook(webhook_slug: str, payload_str: str = "{}"):
    """
    Anropar en n8n webhook (POST).
    """
    print(f"\n--- DAA försöker anropa n8n: {webhook_slug} ---") # Tydlig startmarkör
    
    cfg = get_config()
    base_url = cfg.get("N8N_BASE_URL")
    api_key = cfg.get("N8N_API_KEY")

    if not base_url:
        msg = "FEL: N8N_BASE_URL saknas i inställningarna."
        print(f"[N8N ERROR] {msg}")
        return msg

    # Se till att bas-URL slutar med slash
    if not base_url.endswith("/"):
        base_url += "/"

    # Bygg URL (ta bort inledande slash från slug om den finns)
    if webhook_slug.startswith("/"):
        webhook_slug = webhook_slug[1:]
        
    url = f"{base_url}{webhook_slug}"
    print(f"[N8N DEBUG] URL: {url}")
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["X-N8N-API-KEY"] = api_key

    try:
        # Försök tolka data
        try:
            data = json.loads(payload_str)
        except:
            data = {"text": payload_str}

        print(f"[N8N DEBUG] Data: {str(data)[:100]}...") # Visa bara början av datan

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=headers, timeout=10.0)
            
            if resp.status_code == 200:
                print(f"[N8N SUCCESS] Status 200 OK")
                return f"✅ n8n-flödet '{webhook_slug}' startades."
            else:
                print(f"[N8N ERROR] Status {resp.status_code}: {resp.text}")
                return f"⚠️ n8n svarade med felkod: {resp.status_code}"
                
    except Exception as e:
        print(f"[N8N CRITICAL] {e}")
        return f"Kunde inte nå n8n: {e}"