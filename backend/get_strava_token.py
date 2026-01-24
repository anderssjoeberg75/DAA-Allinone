import requests
import webbrowser
import time
import json
from config.settings import get_config
from app.core.database import save_db_setting

def get_new_strava_token():
    print("--- STRAVA TOKEN GENERATOR ---")
    
    # 1. Hämta Client ID och Secret från din databas
    cfg = get_config()
    client_id = cfg.get("STRAVA_CLIENT_ID")
    client_secret = cfg.get("STRAVA_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("FEL: Du måste fylla i STRAVA_CLIENT_ID och STRAVA_CLIENT_SECRET i inställningarna först!")
        client_id = input("Ange Client ID: ").strip()
        client_secret = input("Ange Client Secret: ").strip()

    # 2. Öppna webbläsaren för att godkänna
    print(f"\n1. Öppnar webbläsare för att godkänna appen (ID: {client_id})...")
    auth_url = f"http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=activity:read_all"
    webbrowser.open(auth_url)

    # 3. Användaren klistrar in koden
    print("\n2. Efter att du klickat 'Authorize', titta på URL:en i webbläsaren.")
    print("   Den ser ut så här: http://localhost/exchange_token?state=&code=DIN_KOD_HÄR&scope=...")
    auth_code = input("\n3. Klistra in koden (allt efter code= och före &scope): ").strip()

    # 4. Byt koden mot en Refresh Token
    print("\n4. Växlar kod mot Refresh Token...")
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
            print(f"\n✅ SUCCÉ! Ny Refresh Token: {refresh_token}")
            
            # 5. Spara automatiskt till databasen
            print("   Sparar till databasen...")
            save_db_setting("STRAVA_REFRESH_TOKEN", refresh_token)
            
            # Spara även Client ID/Secret om de saknades
            save_db_setting("STRAVA_CLIENT_ID", client_id)
            save_db_setting("STRAVA_CLIENT_SECRET", client_secret)
            
            print("✅ Klart! Starta om 'start_windows.bat' nu.")
        else:
            print(f"\n❌ FEL: {data}")
            
    except Exception as e:
        print(f"\n❌ KRASCH: {e}")

if __name__ == "__main__":
    get_new_strava_token()
    input("\nTryck Enter för att avsluta...")