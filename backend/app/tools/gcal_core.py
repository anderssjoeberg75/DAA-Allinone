"""
app/tools/gcal_core.py
"""
import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config.settings import get_config

cfg = get_config()

def get_calendar_events(max_results=5):
    """Hämtar kommande händelser i kalendern."""
    key_path = cfg["SERVICE_ACCOUNT_FILE"]
    if not os.path.exists(key_path): return "Ingen kalender-nyckel hittades."

    try:
        creds = service_account.Credentials.from_service_account_file(
            key_path, scopes=['https://www.googleapis.com/auth/calendar.readonly'])
        service = build('calendar', 'v3', credentials=creds)
        
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                            maxResults=max_results, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])
        
        if not events: return "Kalendern är tom."
        
        output = "Kommande händelser: "
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            clean_time = start.replace('T', ' ').split('+')[0][:16]
            output += f"Kl {clean_time}: {event.get('summary', 'Inget namn')}. "
        return output
    except Exception as e:
        return f"Kalenderfel: {e}"

def create_calendar_event(summary, start_time, end_time):
    """Funktion för att skapa event (kräver skrivrättigheter i scope)."""
    # Implementera vid behov
    return "Funktionen är inte aktiverad i denna version."