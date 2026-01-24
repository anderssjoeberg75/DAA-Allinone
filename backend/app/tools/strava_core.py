import httpx
import time
from config.settings import get_config
from app.core.database import save_db_setting

class StravaTool:
    def __init__(self):
        cfg = get_config()
        self.client_id = cfg.get("STRAVA_CLIENT_ID")
        self.client_secret = cfg.get("STRAVA_CLIENT_SECRET")
        self.refresh_token = cfg.get("STRAVA_REFRESH_TOKEN")
        self.access_token = None
        self.expires_at = 0

    async def _refresh_access_token(self):
        """Hämtar nytt access token och sparar det nya refresh tokenet."""
        if time.time() < self.expires_at and self.access_token:
            return True

        url = "https://www.strava.com/api/v3/oauth/token"
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }
        
        try:
            print(f">> [STRAVA] Försöker förnya token...")
            async with httpx.AsyncClient() as client:
                r = await client.post(url, data=payload)
                data = r.json()
                
                if r.status_code == 200:
                    self.access_token = data['access_token']
                    self.expires_at = data['expires_at']
                    self.refresh_token = data['refresh_token']
                    
                    # VIKTIGT: Spara nya refresh token till DB så vi inte blir utloggade
                    save_db_setting("STRAVA_REFRESH_TOKEN", self.refresh_token)
                    print(f">> [STRAVA] Token förnyad och sparad.")
                    return True
                else:
                    print(f">> [STRAVA] Token Error: {data}")
                    return False
        except Exception as e:
            print(f">> [STRAVA] Connection Error: {e}")
            return False

    async def get_health_report(self, limit=5):
        """Hämtar detaljerad data om de senaste träningspassen."""
        if not self.refresh_token: 
            return {"error": "Ingen Strava-nyckel konfigurerad."}

        if not await self._refresh_access_token():
            return {"error": "Kunde inte logga in på Strava. Kontrollera Client ID/Secret."}

        try:
            url = "https://www.strava.com/api/v3/athlete/activities"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"per_page": limit}
            
            print(f">> [STRAVA] Hämtar aktiviteter...")
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, params=params)
                
            if r.status_code == 200:
                activities = r.json()
                if not activities:
                    return {"error": "Inga aktiviteter hittades på Strava."}
                    
                output = []
                for act in activities:
                    # Beräkna tempo/hastighet
                    speed_ms = act.get('average_speed', 0)
                    speed_str = "0 km/h"
                    if speed_ms > 0:
                        if act.get('type') == 'Run':
                            # Min/km för löpning
                            pace_decimal = 16.666666666667 / speed_ms
                            p_min = int(pace_decimal)
                            p_sec = int((pace_decimal - p_min) * 60)
                            speed_str = f"{p_min}:{p_sec:02d} min/km"
                        else:
                            # Km/h för cykling/annat
                            speed_str = f"{round(speed_ms * 3.6, 1)} km/h"

                    item = {
                        "id": act.get('id'),
                        "namn": act.get('name', 'Namnlöst pass'),
                        "typ": act.get('type', 'Okänd'),
                        "datum": act.get('start_date_local', '')[:16].replace('T', ' '),
                        "distans": f"{round(act.get('distance', 0) / 1000, 2)} km",
                        "tid": f"{round(act.get('moving_time', 0) / 60, 0)} min",
                        "puls_snitt": act.get('average_heartrate', 'N/A'),
                        "puls_max": act.get('max_heartrate', 'N/A'),
                        "höjdmeter": f"{act.get('total_elevation_gain', 0)} m",
                        "tempo": speed_str,
                        "ansträngning": act.get('suffer_score', 'N/A')
                    }
                    output.append(item)
                
                print(f">> [STRAVA] Hämtade {len(output)} pass.")
                return output
            else:
                return {"error": f"Strava API svarade {r.status_code}"}
                
        except Exception as e:
            print(f">> [STRAVA] Fetch Error: {e}")
            return {"error": f"Systemfel: {e}"}