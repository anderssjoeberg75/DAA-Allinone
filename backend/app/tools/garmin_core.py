
import os
import datetime
import logging
from garminconnect import Garmin
from config.settings import get_config, BASE_DIR

# Configure logger
logger = logging.getLogger(__name__)

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
                    logger.info("[GARMIN] Logged in using cached tokens.")
                    return
                except:
                    logger.warning("[GARMIN] Cached tokens invalid, re-logging in.")

            self.client.login()
            if not os.path.exists(self.token_dir):
                os.makedirs(self.token_dir)
            self.client.garth.dump(self.token_dir)
            logger.info("[GARMIN] Logged in and tokens saved.")
        except Exception as e:
            logger.error(f"[GARMIN] Login Error: {e}")
            self.client = None

    def get_health_report(self):
        if not self.client:
            if self.email and self.password: self._login()
            if not self.client: return {"error": "Not logged in to Garmin."}

        try:
            today_str = datetime.date.today().isoformat()
            logger.info(f"[GARMIN] Fetching ALL data for: {today_str}")
            
            # --- 1. DAILY SUMMARY (Steps, Heart Rate, Calories) ---
            stats = self.client.get_user_summary(today_str)
            
            # --- 2. DETAILED SLEEP & SLEEP SCORE ---
            sleep_str = "0h"
            rem_str = "0h"
            deep_str = "0h"
            sleep_score = "N/A"
            try:
                sleep_data = self.client.get_sleep_data(today_str)
                if sleep_data and 'dailySleepDTO' in sleep_data:
                    dto = sleep_data['dailySleepDTO']
                    total_sleep_sec = dto.get('sleepTimeSeconds', 0)
                    # Fallback if detailed time is missing
                    if total_sleep_sec == 0: total_sleep_sec = stats.get("sleepingSeconds", 0)

                    sleep_str = f"{int(total_sleep_sec // 3600)}h {int((total_sleep_sec % 3600) // 60)}m"
                    rem_str = f"{round(dto.get('remSleepSeconds', 0) / 3600, 1)}h"
                    deep_str = f"{round(dto.get('deepSleepSeconds', 0) / 3600, 1)}h"
                    
                    # Fetch Sleep Score (Quality)
                    if 'sleepScores' in dto and dto['sleepScores']:
                        sleep_score = dto['sleepScores'].get('overall', {}).get('value', 'N/A')
            except Exception as e:
                logger.error(f"[GARMIN] Sleep error: {e}")

            # --- 3. BODY BATTERY (Energi) ---
            bb_now = "N/A"
            bb_high = "N/A"
            bb_low = "N/A"
            try:
                bb_data = self.client.get_body_battery(today_str)
                # Check if we got a list directly or a list inside a dict
                if bb_data:
                    values = []
                    # Case A: List inside dict
                    if isinstance(bb_data, list) and len(bb_data) > 0 and 'bodyBatteryValuesArray' in bb_data[0]:
                         values = [pair[1] for pair in bb_data[0]['bodyBatteryValuesArray'] if pair and len(pair) > 1]
                    # Case B: Plain list
                    elif isinstance(bb_data, list):
                         values = [x['value'] for x in bb_data if isinstance(x, dict) and x.get('value') is not None]

                    if values:
                        bb_now = values[-1]  # Last value = Now
                        bb_high = max(values)
                        bb_low = min(values)
                        # logger.info(f"[GARMIN] Body Battery: {bb_now}") 
            except Exception as e:
                logger.error(f"[GARMIN] Body Battery error: {e}")

            # --- 4. HRV STATUS ---
            hrv_status = "N/A"
            try:
                hrv = self.client.get_hrv_data(today_str)
                if hrv and 'hrvSummary' in hrv:
                    summary = hrv['hrvSummary']
                    status = summary.get('status') # E.g. "BALANCED"
                    avg = summary.get('weeklyAvg')
                    last = summary.get('lastNightAvg')
                    
                    if status:
                        hrv_text = status
                        if last: hrv_text += f" (Tonight: {last} ms"
                        if avg: hrv_text += f", Avg: {avg} ms)"
                        else: hrv_text += ")"
                        hrv_status = hrv_text
                        # logger.info(f"[GARMIN] HRV: {hrv_status}") 
            except Exception as e:
                logger.error(f"[GARMIN] HRV Error: {e}")

            if not stats:
                return {"error": "No data from Garmin today (sync your watch)."}

            # --- COMPILATION ---
            data = {
                "date": today_str,
                "steps": stats.get("totalSteps", 0),
                "step_goal": stats.get("dailyStepGoal", 0),
                "distance_km": round(stats.get("totalDistanceMeters", 0) / 1000, 2),
                
                # Heart & Stress
                "resting_heart_rate": stats.get("restingHeartRate", "N/A"),
                "stress_avg": stats.get("averageStressLevel", "N/A"),
                "stress_max": stats.get("maxStressLevel", "N/A"),
                "hrv_status": hrv_status,
                
                # Energy (Body Battery)
                "body_battery_now": bb_now,
                "body_battery_high": bb_high,
                "body_battery_low": bb_low,
                
                # Sleep
                "sleep_hours": sleep_str,
                "sleep_score": sleep_score, 
                "rem_sleep": rem_str,
                "deep_sleep": deep_str,
                
                # Calories & Activity
                "total_calories": stats.get("totalKilocalories", 0),
                "intensive_minutes": stats.get("activeSeconds", 0) / 60,
                "spo2_avg": stats.get("averageSpO2Value", "N/A"),
            }
            
            # Correct intensive minutes if detailed info is available
            if "moderateIntensityMinutes" in stats and "vigorousIntensityMinutes" in stats:
                data["intensive_minutes"] = stats["moderateIntensityMinutes"] + (stats["vigorousIntensityMinutes"] * 2)

            return data

        except Exception as e:
            logger.error(f"[GARMIN] Fetch Error: {e}")
            return {"error": f" System error: {e}"}