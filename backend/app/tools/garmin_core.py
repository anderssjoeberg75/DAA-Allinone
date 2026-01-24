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
            print(f">> [GARMIN DEBUG] Hämtar UTÖKAD data för: {today_str}")
            
            stats = self.client.get_user_summary(today_str)
            
            if not stats:
                return {"fel": "Ingen data från Garmin idag (synka klockan)."}

            # --- SÖMN ---
            sleep_sec = stats.get("sleepingSeconds", 0)
            sleep_str = f"{round(sleep_sec / 3600, 1)}h" if sleep_sec > 0 else "0h"

            # --- BASDATA ---
            data = {
                "datum": today_str,
                "steg": stats.get("totalSteps", 0),
                "mål_steg": stats.get("dailyStepGoal", 0),
                "distans_km": round(stats.get("totalDistanceMeters", 0) / 1000, 2),
                "våningar_upp": stats.get("floorsAscended", 0),
                
                # --- HJÄRTA & STRESS ---
                "vilopuls": stats.get("restingHeartRate", "N/A"),
                "max_puls_idag": stats.get("maxHeartRate", "N/A"),
                "stress_snitt": stats.get("averageStressLevel", "N/A"),
                "stress_max": stats.get("maxStressLevel", "N/A"),
                "body_battery_nu": stats.get("bodyBattery", "N/A"),
                "body_battery_högst": stats.get("maxBodyBattery", "N/A"),
                "body_battery_lägst": stats.get("minBodyBattery", "N/A"),
                
                # --- SÖMN & ÅTERHÄMTNING ---
                "sömn_timmar": sleep_str,
                "rem_sömn": f"{round(stats.get('remSleepSeconds', 0)/3600, 1)}h",
                "djup_sömn": f"{round(stats.get('deepSleepSeconds', 0)/3600, 1)}h",
                
                # --- AKTIVITET & KALORIER ---
                "kalorier_totalt": stats.get("totalKilocalories", 0),
                "kalorier_aktiva": stats.get("activeKilocalories", 0),
                "kalorier_bmr": stats.get("bmrKilocalories", 0),
                "intensiva_minuter_totalt": stats.get("intensityMinutesGoal", 0), # Ofta returneras målet här, faktiska värdet kan heta annorlunda beroende på enhet
                "intensiva_minuter_faktiska": stats.get("activeSeconds", 0) / 60, # Grov uppskattning om intensityMinutes saknas
                
                # --- ÖVRIGT (OM TILLGÄNGLIGT) ---
                "andningsfrekvens_snitt": stats.get("averageRespirationValue", "N/A"),
                "spo2_snitt": stats.get("averageSpO2Value", "N/A"),
            }
            
            # Försök hitta faktiska intensiva minuter om de ligger under annan nyckel
            if "moderateIntensityMinutes" in stats and "vigorousIntensityMinutes" in stats:
                data["intensiva_minuter_faktiska"] = stats["moderateIntensityMinutes"] + (stats["vigorousIntensityMinutes"] * 2)

            return data

        except Exception as e:
            print(f">> [Garmin] Fetch Error: {e}")
            return {"fel": f"Systemfel: {e}"}