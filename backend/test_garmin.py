import sys
import os
import datetime

# Lägg till nuvarande mapp i sökvägen
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.tools.garmin_core import GarminCoach
    from config.settings import get_config
except ImportError as e:
    print(f"Kunde inte importera moduler: {e}")
    sys.exit(1)

def print_section(title):
    print(f"\n{'='*50}")
    print(f"   {title}")
    print(f"{'='*50}")

def test_garmin_full():
    print_section("INITIERAR GARMIN EXTENDED TEST")
    
    # 1. INITIERA
    try:
        coach = GarminCoach()
    except Exception as e:
        print(f"Kritiskt fel vid initiering: {e}")
        return

    if not coach.client:
        print("X Kunde inte logga in. Kontrollera GARMIN_EMAIL och GARMIN_PASSWORD i inställningarna.")
        return

    client = coach.client
    print(f"V Inloggad som: {client.display_name}")
    print(f"V Fullständigt namn: {client.full_name}")

    # Datum för hämtning (Idag)
    today = datetime.date.today().isoformat()
    print(f"Kalender: Hämtar data för {today}")

    # ---------------------------------------------------------
    # 2. DAGLIG SAMMANFATTNING
    # ---------------------------------------------------------
    try:
        print_section("1. DAGLIG STATUS (SUMMARY)")
        summary = client.get_user_summary(today)
        
        keys_to_show = [
            'totalSteps', 'restingHeartRate', 'maxHeartRate', 
            'averageStressLevel', 'bodyBattery', 'sleepingSeconds', 
            'totalKilocalories', 'floorsAscended'
        ]
        
        for k in keys_to_show:
            val = summary.get(k, 'N/A')
            if k == 'sleepingSeconds' and isinstance(val, (int, float)):
                val = f"{round(val/3600, 1)} timmar"
            print(f"   - {k.ljust(20)}: {val}")
            
    except Exception as e:
        print(f"varning: Kunde inte hämta summary: {e}")

    # ---------------------------------------------------------
    # 3. SENASTE AKTIVITETER
    # ---------------------------------------------------------
    try:
        print_section("2. SENASTE AKTIVITETER (Top 3)")
        activities = client.get_activities(0, 3) 
        
        if activities:
            for act in activities:
                name = act.get('activityName', 'Okänt pass')
                type_name = act.get('activityType', {}).get('typeKey', 'N/A')
                date = act.get('startTimeLocal', 'N/A')
                dist = round(act.get('distance', 0) / 1000, 2)
                duration = round(act.get('duration', 0) / 60, 1)
                
                print(f"   > {date}: {name} ({type_name})")
                print(f"     Distans: {dist} km | Tid: {duration} min")
                print(f"     Snittpuls: {act.get('averageHR', 'N/A')} | Kalorier: {act.get('calories', 'N/A')}")
                print("     ---")
        else:
            print("   Inga aktiviteter hittades nyligen.")

    except Exception as e:
        print(f"varning: Kunde inte hämta aktiviteter: {e}")

    # ---------------------------------------------------------
    # 4. SÖMNDATA
    # ---------------------------------------------------------
    try:
        print_section("3. SÖMNDATA")
        sleep = client.get_sleep_data(today)
        
        daily_sleep = sleep.get('dailySleepDTO', {})
        if daily_sleep.get('id'):
            total_sec = daily_sleep.get('sleepTimeSeconds', 0)
            deep_sec = daily_sleep.get('deepSleepSeconds', 0)
            rem_sec = daily_sleep.get('remSleepSeconds', 0)
            
            print(f"   Total sömn: {round(total_sec/3600, 1)} timmar")
            print(f"   Djupsömn: {round(deep_sec/60, 0)} min")
            print(f"   REM-sömn: {round(rem_sec/60, 0)} min")
            print(f"   Sleep Score: {daily_sleep.get('sleepScores', {}).get('overall', {}).get('value', 'N/A')}")
        else:
            print("   Ingen sömndata registrerad för natten.")

    except Exception as e:
        print(f"varning: Kunde inte hämta sömn: {e}")

    # ---------------------------------------------------------
    # 5. ENHETER (Här var felet sist)
    # ---------------------------------------------------------
    try:
        print_section("4. KOPPLADE ENHETER")
        devices = client.get_devices()
        for dev in devices:
            name = dev.get('productDisplayName')
            last_sync = dev.get('lastSyncTimestampLocal')
            battery = dev.get('batteryLevel', 'N/A')
            # Korrigerad rad utan emoji och utan radbrytning
            print(f"   [ENHET] {name} (Batteri: {battery}%)")
            print(f"           Senast synkad: {last_sync}")
    except Exception as e:
        print(f"varning: Kunde inte hämta enheter: {e}")

    print_section("TEST KLART")

if __name__ == "__main__":
    test_garmin_full()