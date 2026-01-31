import os
import datetime
from garminconnect import Garmin
from config.settings import get_config, BASE_DIR

class GarminCoach:
    def __init__(self):
        self.client = None
        cfg = get_config()
        self.email = cfg.get("GARMIN_EMAIL")
        self.password = cfg.get("GARMIN_PASSWORD")
        self.token_dir = os.path.join(BASE_DIR, "config", "garmin_tokens")
        
        if self.email and self.password:
            self._login()

    def _login(self):
        try:
            self.client = Garmin(self.email, self.password)
            self.client.garth.configure(domain="garmin.com")
            
            if os.path.exists(self.token_dir):
                try:
                    self.client.garth.load(self.token_dir)
                    self.client.login()
                    return
                except: pass

            self.client.login()
            if not os.path.exists(self.token_dir):
                os.makedirs(self.token_dir)
            self.client.garth.dump(self.token_dir)
        except Exception as e:
            print(f">> [Garmin] Login Error: {e}")
            self.client = None

    def get_health_report(self):
        if not self.client:
            if self.email and self.password: self._login()
            if not self.client: return {"fel": "Ej inloggad på Garmin."}

        try:
            today_str = datetime.date.today().isoformat()
            print(f">> [GARMIN] Hämtar ALL data för: {today_str}")
            
            # --- 1. DAGLIG SAMMANFATTNING (Steg, Puls, Kalorier) ---
            stats = self.client.get_user_summary(today_str)
            
            # --- 2. DETALJERAD SÖMN & SÖMNPOÄNG ---
            sleep_str = "0h"
            rem_str = "0h"
            deep_str = "0h"
            sleep_score = "N/A"
            try:
                sleep_data = self.client.get_sleep_data(today_str)
                if sleep_data and 'dailySleepDTO' in sleep_data:
                    dto = sleep_data['dailySleepDTO']
                    total_sleep_sec = dto.get('sleepTimeSeconds', 0)
                    # Fallback om detaljerad tid saknas
                    if total_sleep_sec == 0: total_sleep_sec = stats.get("sleepingSeconds", 0)

                    sleep_str = f"{int(total_sleep_sec // 3600)}h {int((total_sleep_sec % 3600) // 60)}m"
                    rem_str = f"{round(dto.get('remSleepSeconds', 0) / 3600, 1)}h"
                    deep_str = f"{round(dto.get('deepSleepSeconds', 0) / 3600, 1)}h"
                    
                    # Hämta Sleep Score (Kvalitet)
                    if 'sleepScores' in dto and dto['sleepScores']:
                        sleep_score = dto['sleepScores'].get('overall', {}).get('value', 'N/A')
            except Exception as e:
                print(f">> [GARMIN] Sömnfel: {e}")

            # --- 3. BODY BATTERY (Energi) ---
            bb_now = "N/A"
            bb_high = "N/A"
            bb_low = "N/A"
            try:
                bb_data = self.client.get_body_battery(today_str)
                # Kollar om vi fick en lista direkt eller en lista inuti en dict (som din logg visade)
                if bb_data:
                    values = []
                    # Fall A: Din loggstruktur (lista inuti dict)
                    if isinstance(bb_data, list) and len(bb_data) > 0 and 'bodyBatteryValuesArray' in bb_data[0]:
                         values = [pair[1] for pair in bb_data[0]['bodyBatteryValuesArray'] if pair and len(pair) > 1]
                    # Fall B: Vanlig lista (om formatet varierar)
                    elif isinstance(bb_data, list):
                         values = [x['value'] for x in bb_data if isinstance(x, dict) and x.get('value') is not None]

                    if values:
                        bb_now = values[-1]  # Sista värdet = Nu
                        bb_high = max(values)
                        bb_low = min(values)
                        print(f">> [GARMIN] Body Battery: {bb_now}")
            except Exception as e:
                print(f">> [GARMIN] Body Battery fel: {e}")

            # --- 4. HRV STATUS (FIXAD) ---
            hrv_status = "N/A"
            try:
                hrv = self.client.get_hrv_data(today_str)
                if hrv and 'hrvSummary' in hrv:
                    summary = hrv['hrvSummary']
                    status = summary.get('status') # T.ex "BALANCED"
                    avg = summary.get('weeklyAvg') # <-- RÄTT NYCKEL HÄR (Var weeklyAverage)
                    last = summary.get('lastNightAvg') # Vi lägger till nattens värde också!
                    
                    if status:
                        hrv_text = status
                        if last: hrv_text += f" (I natt: {last} ms"
                        if avg: hrv_text += f", Snitt: {avg} ms)"
                        else: hrv_text += ")"
                        hrv_status = hrv_text
                        print(f">> [GARMIN] HRV: {hrv_status}")
            except Exception as e:
                print(f">> [GARMIN] HRV Fel: {e}")

            if not stats:
                return {"fel": "Ingen data från Garmin idag (synka klockan)."}

            # --- SAMMANSTÄLLNING ---
            data = {
                "datum": today_str,
                "steg": stats.get("totalSteps", 0),
                "mål_steg": stats.get("dailyStepGoal", 0),
                "distans_km": round(stats.get("totalDistanceMeters", 0) / 1000, 2),
                
                # Hjärta & Stress
                "vilopuls": stats.get("restingHeartRate", "N/A"),
                "stress_snitt": stats.get("averageStressLevel", "N/A"),
                "stress_max": stats.get("maxStressLevel", "N/A"),
                "hrv_status": hrv_status,
                
                # Energi (Body Battery)
                "body_battery_nu": bb_now,
                "body_battery_högst": bb_high,
                "body_battery_lägst": bb_low,
                
                # Sömn
                "sömn_timmar": sleep_str,
                "sömn_poäng": sleep_score, 
                "rem_sömn": rem_str,
                "djup_sömn": deep_str,
                
                # Kalorier & Aktivitet
                "kalorier_totalt": stats.get("totalKilocalories", 0),
                "intensiva_minuter": stats.get("activeSeconds", 0) / 60,
                "spo2_snitt": stats.get("averageSpO2Value", "N/A"),
            }
            
            # Korrigera intensiva minuter om detaljerad info finns
            if "moderateIntensityMinutes" in stats and "vigorousIntensityMinutes" in stats:
                data["intensiva_minuter"] = stats["moderateIntensityMinutes"] + (stats["vigorousIntensityMinutes"] * 2)

            return data

        except Exception as e:
            print(f">> [Garmin] Fetch Error: {e}")
            return {"fel": f"Systemfel: {e}"}