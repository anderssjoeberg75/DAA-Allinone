import httpx
import time
from config.settings import get_config

class StravaTool:
    def __init__(self):
        cfg = get_config()
        self.client_id = cfg.get("STRAVA_CLIENT_ID")
        self.client_secret = cfg.get("STRAVA_CLIENT_SECRET")
        self.refresh_token = cfg.get("STRAVA_REFRESH_TOKEN")
        self.access_token = None
        self.expires_at = 0

    async def _refresh_access_token(self):
        """Hämtar ett nytt access token om det gamla gått ut."""
        if time.time() < self.expires_at and self.access_token:
            return

        url = "https://www.strava.com/api/v3/oauth/token"
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(url, data=payload)
                data = r.json()
                self.access_token = data['access_token']
                self.expires_at = data['expires_at']
        except Exception as e:
            print(f">> [Strava] Token Refresh Error: {e}")

    async def get_health_report(self, limit=3):
        """Hämtar de senaste träningspassen för analys."""
        # Kontrollera att token finns
        if not self.refresh_token or "DITT_STRAVA_REFRESH_TOKEN" in self.refresh_token:
            return None

        try:
            await self._refresh_access_token()
            url = "https://www.strava.com/api/v3/athlete/activities"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"per_page": limit}
            
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, params=params)
                
            if r.status_code == 200:
                activities = r.json()
                output = []
                for act in activities:
                    output.append({
                        "typ": act['type'],
                        "datum": act['start_date_local'][:10],
                        "distans_km": round(act['distance'] / 1000, 1),
                        "tid_min": round(act['moving_time'] / 60, 0),
                        "ansträngning": act.get('suffer_score', 'Ej angivet')
                    })
                return output
        except Exception as e:
            print(f">> [Strava] Fetch Error: {e}")
        return None