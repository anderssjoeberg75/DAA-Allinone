from datetime import datetime
from app.core.database import get_db_prompts

"""
==============================================================================
FILE: app/core/prompts.py
DESCRIPTION: Kombinerar statisk text från DB med dynamisk tid/datum.
==============================================================================
"""

def get_prompts_data():
    """Hjälpfunktion för att hämta allt från DB."""
    return get_db_prompts()

def get_system_prompt():
    """
    Bygger system-prompten:
    1. Hämtar personlighet/regler från Databasen.
    2. Lägger till realtidsinformation (Tid/Datum) via Python.
    """
    # 1. Hämta bas-texten från databasen
    data = get_prompts_data()
    # Om DB är tom, använd en enkel fallback
    base_prompt = data.get("SYSTEM_PROMPT", "Du är DAA. Fyll i din prompt i inställningarna.")

    # 2. Skapa tidsdata (Din gamla logik!)
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%Y-%m-%d")
    week_number = now.strftime("%V")
    
    # Svenska översättningar
    days_se = {
        "Monday": "måndag", "Tuesday": "tisdag", "Wednesday": "onsdag",
        "Thursday": "torsdag", "Friday": "fredag", "Saturday": "lördag", "Sunday": "söndag"
    }
    day_name = now.strftime("%A")
    swe_day = days_se.get(day_name, day_name)
    
    # 3. Skapa kontext-blocket
    time_context = (
        f"\n\n--- REALTIDSINFORMATION (GENERERAT AV SYSTEMET) ---\n"
        f"- Tid: {current_time}\n"
        f"- Datum: {current_date}\n"
        f"- Veckodag: {swe_day}\n"
        f"- Vecka: {week_number}\n"
        f"---------------------------------------------------\n"
    )
    
    # 4. Slå ihop: Databas-text + Tids-block
    return base_prompt + time_context

def get_audit_prompt():
    return get_prompts_data().get("CODE_AUDIT_PROMPT", "Ingen kodanalys-prompt hittades.")

def get_audit_tool_desc():
    # Standardbeskrivning om den saknas i DB
    default = "Analyserar projektets källkod för att hitta fel och förbättringar."
    return get_prompts_data().get("TOOL_DESC_AUDIT", default)

# Variabler för import till andra filer
CODE_AUDIT_PROMPT = get_audit_prompt()
ANALYZE_CODE_TOOL_DESC = get_audit_tool_desc()