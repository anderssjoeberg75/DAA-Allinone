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
        """Fetches new access token and saves the new refresh token."""
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
            print(f">> [STRAVA] Attempting to refresh token...")
            async with httpx.AsyncClient() as client:
                r = await client.post(url, data=payload)
                data = r.json()
                
                if r.status_code == 200:
                    self.access_token = data['access_token']
                    self.expires_at = data['expires_at']
                    self.refresh_token = data['refresh_token']
                    
                    # IMPORTANT: Save new refresh token to DB so we don't get logged out
                    save_db_setting("STRAVA_REFRESH_TOKEN", self.refresh_token)
                    print(f">> [STRAVA] Token refreshed and saved.")
                    return True
                else:
                    print(f">> [STRAVA] Token Error: {data}")
                    return False
        except Exception as e:
            print(f">> [STRAVA] Connection Error: {e}")
            return False

    async def get_health_report(self, limit=5):
        """Fetches detailed data for recent workout sessions."""
        if not self.refresh_token: 
            return {"error": "No Strava key configured."}

        if not await self._refresh_access_token():
            return {"error": "Could not login to Strava. Check Client ID/Secret."}

        try:
            url = "https://www.strava.com/api/v3/athlete/activities"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"per_page": limit}
            
            print(f">> [STRAVA] Fetching activities...")
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, params=params)
                
            if r.status_code == 200:
                activities = r.json()
                if not activities:
                    return {"error": "No activities found on Strava."}
                    
                output = []
                for act in activities:
                    # Calculate pace/speed
                    speed_ms = act.get('average_speed', 0)
                    speed_str = "0 km/h"
                    if speed_ms > 0:
                        if act.get('type') == 'Run':
                            # Min/km for running
                            pace_decimal = 16.666666666667 / speed_ms
                            p_min = int(pace_decimal)
                            p_sec = int((pace_decimal - p_min) * 60)
                            speed_str = f"{p_min}:{p_sec:02d} min/km"
                        else:
                            # Km/h for cycling/other
                            speed_str = f"{round(speed_ms * 3.6, 1)} km/h"

                    item = {
                        "id": act.get('id'),
                        "name": act.get('name', 'Unnamed workout'),
                        "type": act.get('type', 'Unknown'),
                        "date": act.get('start_date_local', '')[:16].replace('T', ' '),
                        "distance": f"{round(act.get('distance', 0) / 1000, 2)} km",
                        "time": f"{round(act.get('moving_time', 0) / 60, 0)} min",
                        "avg_hr": act.get('average_heartrate', 'N/A'),
                        "max_hr": act.get('max_heartrate', 'N/A'),
                        "elevation": f"{act.get('total_elevation_gain', 0)} m",
                        "pace": speed_str,
                        "effort": act.get('suffer_score', 'N/A')
                    }
                    output.append(item)
                
                print(f">> [STRAVA] Fetched {len(output)} workouts.")
                return output
            else:
                return {"error": f"Strava API responded with {r.status_code}"}
                
        except Exception as e:
            print(f">> [STRAVA] Fetch Error: {e}")
            return {"error": f"System error: {e}"}