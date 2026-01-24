import requests
import time
import datetime
from config.settings import get_config
from app.core.database import save_db_setting

class WithingsTool:
    def __init__(self):
        cfg = get_config()
        self.client_id = cfg.get("WITHINGS_CLIENT_ID")
        self.client_secret = cfg.get("WITHINGS_CLIENT_SECRET")
        self.refresh_token = cfg.get("WITHINGS_REFRESH_TOKEN")
        self.access_token = None
        self.expires_at = 0

    def _refresh_access_token(self):
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
                self.expires_at = time.time() + body['expires_in'] - 60 
                self.refresh_token = body['refresh_token']
                save_db_setting("WITHINGS_REFRESH_TOKEN", self.refresh_token)
            else:
                print(f">> [Withings] Token Refresh Error: {data}")
        except Exception as e:
            print(f">> [Withings] Connection Error: {e}")

    def get_health_report(self):
        if not self.refresh_token: return None
        self._refresh_access_token()
        if not self.access_token: return "Ingen åtkomst till Withings."

        headers = {'Authorization': f'Bearer {self.access_token}'}
        report = {}

        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            # Hämta data för senaste veckan för att vara säker på att hitta mätvärden
            start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            
            # --- 1. AKTIVITET (Steg, Kalorier m.m.) ---
            act_url = "https://wbsapi.withings.net/v2/measure"
            act_params = {
                'action': 'getactivity',
                'startdateymd': today, # Försök bara med idag först för aktivitet
                'enddateymd': today,
                'data_fields': 'steps,distance,elevation,soft,moderate,intense,active,calories,totalcalories,hr_average,hr_min,hr_max'
            }
            r_act = requests.post(act_url, headers=headers, data=act_params)
            act_data = r_act.json()
            
            if act_data.get('status') == 0 and 'activities' in act_data['body']:
                latest = act_data['body']['activities'][-1]
                report['steg_withings'] = latest.get('steps', 0)
                report['kalorier_total'] = latest.get('totalcalories', 0)
                report['aktiv_tid'] = round(latest.get('active', 0) / 60, 0) # Minuter
                if 'hr_average' in latest:
                    report['snittpuls'] = latest['hr_average']

            # --- 2. KROPPSMÄTNINGAR (Vikt, Fett, Muskler, Vatten, Ben) ---
            # Type: 1=Vikt, 4=Längd, 6=Fett%, 76=Muskelmassa, 77=Vatten, 88=Benmassa, 9=Diastoliskt, 10=Systoliskt
            meas_url = "https://wbsapi.withings.net/measure"
            meas_params = { 
                'action': 'getmeas', 
                'category': 1, 
                'limit': 1  # Hämta bara det allra senaste mättillfället
            }
            r_meas = requests.post(meas_url, headers=headers, data=meas_params)
            meas_data = r_meas.json()
            
            if meas_data.get('status') == 0 and 'measuregrps' in meas_data['body']:
                grp = meas_data['body']['measuregrps'][0]
                report['mätning_datum'] = datetime.datetime.fromtimestamp(grp['date']).strftime("%Y-%m-%d %H:%M")
                
                for m in grp['measures']:
                    val = m['value'] * (10 ** m['unit'])
                    t = m['type']
                    
                    if t == 1: report['vikt'] = round(val, 1)
                    elif t == 6: report['fett_procent'] = round(val, 1)
                    elif t == 76: report['muskelmassa_kg'] = round(val, 1)
                    elif t == 77: report['vatten_kg'] = round(val, 1)
                    elif t == 88: report['benmassa_kg'] = round(val, 1)
                    elif t == 9: report['blodtryck_dia'] = int(val)
                    elif t == 10: report['blodtryck_sys'] = int(val)
                    elif t == 11: report['puls_vid_vägning'] = int(val)

            return report
        except Exception as e:
            return f"Fel vid Withings-hämtning: {e}"