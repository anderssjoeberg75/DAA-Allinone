import requests
import webbrowser
import time
import json
from config.settings import get_config
from app.core.database import save_db_setting

def get_new_strava_token():
    print("--- STRAVA TOKEN GENERATOR ---")
    
    # 1. Fetch Client ID and Secret from database
    cfg = get_config()
    client_id = cfg.get("STRAVA_CLIENT_ID")
    client_secret = cfg.get("STRAVA_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: You must fill in STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in settings first!")
        client_id = input("Enter Client ID: ").strip()
        client_secret = input("Enter Client Secret: ").strip()

    # 2. Open browser for authorization
    print(f"\n1. Opening browser to authorize app (ID: {client_id})...")
    auth_url = f"http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=activity:read_all"
    webbrowser.open(auth_url)

    # 3. User pastes the code
    print("\n2. After clicking 'Authorize', look at the URL in the browser.")
    print("   It looks like this: http://localhost/exchange_token?state=&code=YOUR_CODE_HERE&scope=...")
    auth_code = input("\n3. Paste the code (everything after code= and before &scope): ").strip()

    # 4. Exchange code for Refresh Token
    print("\n4. Exchanging code for Refresh Token...")
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': auth_code,
        'grant_type': 'authorization_code'
    }

    try:
        res = requests.post(token_url, data=payload)
        data = res.json()

        if res.status_code == 200:
            refresh_token = data['refresh_token']
            print(f"\n✅ SUCCESS! New Refresh Token: {refresh_token}")
            
            # 5. Save automatically to database
            print("   Saving to database...")
            save_db_setting("STRAVA_REFRESH_TOKEN", refresh_token)
            
            # Save Client ID/Secret if they were missing
            save_db_setting("STRAVA_CLIENT_ID", client_id)
            save_db_setting("STRAVA_CLIENT_SECRET", client_secret)
            
            print("✅ Done! Restart 'start_windows.bat' now.")
        else:
            print(f"\n❌ ERROR: {data}")
            
    except Exception as e:
        print(f"\n❌ CRASH: {e}")

if __name__ == "__main__":
    get_new_strava_token()
    input("\nPress Enter to exit...")