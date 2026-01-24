import requests
import time
import datetime
from config.settings import get_config

"""
==============================================================================
FILE: app/tools/withings_core.py
PROJECT: DAA Digital Advanced Assistant
DESCRIPTION: Hämtar hälsodata (Vikt, Sömn, Aktivitet) från Withings API.
==============================================================================
"""

class WithingsTool:
    def __init__(self):
        cfg = get_config()
        self.client_id = cfg.get("WITHINGS_CLIENT_ID")
        self.client_secret = cfg.get("WITHINGS_CLIENT_SECRET")
        self.refresh_token = cfg.get("WITHINGS_REFRESH_TOKEN")
        self.access_token = None
        self.expires_at = 0

    def _refresh_access_token(self):
        """Hämtar ett nytt access token om det gamla gått ut."""
        if time.time() < self.expires_at and self.access_token:
            return

        url = "https://wbsapi.withings.net/v2/oauth2"
        payload = {
            'action': 'requesttoken',
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }
        
        try:
            response = requests.post(url, data=payload)
            data = response.json()
            
            if data.get('status') == 0:
                body = data['body']
                self.access_token = body['access_token']
                # Token gäller oftast i 3 timmar (10800 sekunder)
                self.expires_at = time.time() + body['expires_in'] - 60 
                # Uppdatera refresh token för nästa gång (Withings roterar ofta refresh tokens)
                self.refresh_token = body['refresh_token']
                # OBS: I en produktionsmiljö bör du spara det nya refresh_tokenet till fil/db här.
            else:
                print(f">> [Withings] Token Refresh Error: {data}")
        except Exception as e:
            print(f">> [Withings] Connection Error: {e}")

    def get_health_report(self):
        """Hämtar dagens aktivitet och senaste viktmätning."""
        if not self.refresh_token:
            return None

        self._refresh_access_token()
        if not self.access_token:
            return "Kunde inte autentisera mot Withings."

        headers = {'Authorization': f'Bearer {self.access_token}'}
        report = {}

        try:
            # 1. Hämta Aktivitet (Steg, Kcal etc) för idag
            # Datumformat: YYYY-MM-DD
            today = datetime.date.today().strftime("%Y-%m-%d")
            # Vi hämtar från igår till idag för säkerhets skull
            start_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            
            act_url = "https://wbsapi.withings.net/v2/measure"
            act_params = {
                'action': 'getactivity',
                'startdateymd': start_date,
                'enddateymd': today,
                'data_fields': 'steps,soft,moderate,intense,calories'
            }
            
            r_act = requests.post(act_url, headers=headers, data=act_params)
            act_data = r_act.json()
            
            if act_data.get('status') == 0 and 'activities' in act_data['body']:
                # Ta sista posten (oftast idag)
                latest = act_data['body']['activities'][-1]
                report['steg'] = latest.get('steps', 0)
                report['kalorier'] = latest.get('calories', 0)
                report['datum_aktivitet'] = latest.get('date', today)

            # 2. Hämta Mätningar (Vikt, Fettprocent)
            meas_url = "https://wbsapi.withings.net/measure"
            meas_params = {
                'action': 'getmeas',
                'meastype': 1, # 1 = Vikt
                'category': 1, # 1 = Riktiga mätningar
                'limit': 1
            }
            
            r_meas = requests.post(meas_url, headers=headers, data=meas_params)
            meas_data = r_meas.json()
            
            if meas_data.get('status') == 0 and 'measuregrps' in meas_data['body']:
                grp = meas_data['body']['measuregrps'][0]
                # Vikt är ofta lagrad som value * 10^unit (t.ex. 75500 * 10^-3 = 75.5 kg)
                for m in grp['measures']:
                    if m['type'] == 1: # Vikt
                        weight = m['value'] * (10 ** m['unit'])
                        report['vikt'] = round(weight, 1)
                        report['vikt_datum'] = datetime.datetime.fromtimestamp(grp['date']).strftime("%Y-%m-%d")

            return report

        except Exception as e:
            return f"Fel vid hämtning av Withings-data: {e}"