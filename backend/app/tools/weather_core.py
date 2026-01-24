import httpx
import asyncio
from config.settings import get_config

# Enklare mappning av WMO-koder till text
WEATHER_CODES = {
    0: "Klart solsken", 1: "Mest klart", 2: "Halvklart", 3: "Molnigt",
    45: "Dimma", 48: "Rimfrost", 51: "Lätt duggregn", 53: "Duggregn",
    55: "Kraftigt duggregn", 61: "Lätt regn", 63: "Regn", 65: "Kraftigt regn",
    71: "Lätt snöfall", 73: "Snöfall", 75: "Kraftigt snöfall", 77: "Snökorn",
    80: "Lätt regnskur", 81: "Regnskur", 82: "Kraftig regnskur",
    85: "Lätt snöby", 86: "Kraftig snöby", 95: "Åska", 96: "Åska med hagel"
}

async def get_weather():
    """
    Hämtar väder från OpenMeteo API (Kräver ingen API-nyckel).
    """
    cfg = get_config()
    lat = cfg.get("LATITUDE")
    lon = cfg.get("LONGITUDE")

    if not lat or not lon:
        return "⚠️ Saknar GPS-koordinater. Fyll i LATITUDE och LONGITUDE i inställningarna (Kugghjulet)."

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            
            if response.status_code != 200:
                return f"Kunde inte hämta väder (Felkod: {response.status_code})"

            data = response.json()
            
            # Nuvarande väder
            curr = data.get("current", {})
            temp = curr.get("temperature_2m", "N/A")
            wind = curr.get("wind_speed_10m", 0)
            code = curr.get("weather_code", 0)
            desc = WEATHER_CODES.get(code, "Okänt väder")

            # Prognos för idag (Max/Min)
            daily = data.get("daily", {})
            max_temp = daily.get("temperature_2m_max", ["N/A"])[0]
            min_temp = daily.get("temperature_2m_min", ["N/A"])[0]

            report = (
                f"Just nu är det {desc} och {temp}°C. "
                f"Vinden ligger på {wind} m/s. "
                f"Idag förväntas en högsta temperatur på {max_temp}°C och lägsta på {min_temp}°C."
            )
                
            return report

    except Exception as e:
        print(f"[WEATHER] Error: {e}")
        return "Systemfel vid hämtning av väderdata."

if __name__ == "__main__":
    print(asyncio.run(get_weather()))