
import httpx
import asyncio
from config.settings import get_config

# SMHI Wsymb2 Mapping (1-27)
SMHI_CODES = {
    1: "Klart", 2: "Lätt molnighet", 3: "Halvklart", 4: "Molnigt", 5: "Mycket molnigt", 
    6: "Mulet", 7: "Dimma", 8: "Lätt regnskur", 9: "Regnskur", 10: "Kraftig regnskur",
    11: "Åskskur", 12: "Lätt by av snöblandat regn", 13: "By av snöblandat regn", 
    14: "Kraftig by av snöblandat regn", 15: "Lätt snöby", 16: "Snöby", 17: "Kraftig snöby",
    18: "Lätt regn", 19: "Regn", 20: "Kraftigt regn", 21: "Åska", 22: "Lätt snöblandat regn",
    23: "Snöblandat regn", 24: "Kraftigt snöblandat regn", 25: "Lätt snöfall", 
    26: "Snöfall", 27: "Kraftigt snöfall"
}

async def get_weather():
    """
    Hämtar väder från SMHI Open API (PMP3g).
    """
    cfg = get_config()
    lat = cfg.get("LATITUDE")
    lon = cfg.get("LONGITUDE")

    if not lat or not lon:
        return "⚠️ Saknar GPS-koordinater. Fyll i LATITUDE och LONGITUDE i inställningarna."

    # SMHI requires 6 decimal precision
    try:
        lat_formatted = f"{float(lat):.6f}"
        lon_formatted = f"{float(lon):.6f}"
    except ValueError:
        return "⚠️ Ogiltiga GPS-koordinater."

    url = f"https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/{lon_formatted}/lat/{lat_formatted}/data.json"

    try:
        # User-Agent is good practice/required sometimes
        headers = {"User-Agent": "DAA-Assistant/1.0"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0, headers=headers)
            
            if response.status_code != 200:
                print(f"[SMHI] Error {response.status_code}: {response.text}")
                return f"Kunde inte hämta väder från SMHI (Felkod: {response.status_code})"

            data = response.json()
            time_series = data.get("timeSeries", [])
            
            if not time_series:
                return "Ingen väderdata tillgänglig från SMHI."

            # --- Current Weather (First data point) ---
            current = time_series[0]
            params = {p["name"]: p["values"][0] for p in current["parameters"]}
            
            # Wsymb2 = Weather Symbol
            wsymb = int(params.get("Wsymb2", 0))
            desc = SMHI_CODES.get(wsymb, f"Okänt väder ({wsymb})")
            
            # t = Temp C
            temp = params.get("t", "N/A")
            
            # ws = Wind Speed m/s
            wind = params.get("ws", "N/A")

            # --- Forecast (Next 3 Days) ---
            forecast_msg = ""
            days = ["Idag", "Imorgon", "Iövermorgon"]
            
            # Simple assumption: 24h per day blocks roughly (since data is hourly for first days)
            # Better: Group by date string (validTime)
            
            daily_stats = {}
            for entry in time_series:
                vt = entry.get("validTime", "")[:10] # YYYY-MM-DD
                if vt not in daily_stats: daily_stats[vt] = []
                
                p = {x["name"]: x["values"][0] for x in entry["parameters"]}
                if "t" in p: daily_stats[vt].append(p["t"])
            
            # Sort dates and take first 3
            sorted_dates = sorted(daily_stats.keys())[:3]
            
            for i, date in enumerate(sorted_dates):
                if i < len(days):
                    temps = daily_stats[date]
                    if temps:
                        d_max = max(temps)
                        d_min = min(temps)
                        forecast_msg += f"{days[i]}: Max {d_max}°C, Min {d_min}°C. "

            report = (
                f"Just nu rapporterar SMHI {desc} och {temp}°C, vind {wind} m/s. "
                f"Prognos: {forecast_msg}"
            )
                
            return report

    except Exception as e:
        print(f"[WEATHER] Error: {e}")
        return "Systemfel vid hämtning av väderdata från SMHI."

if __name__ == "__main__":
    import sys
    import os
    # Allow importing config when running directly
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    print(asyncio.run(get_weather()))