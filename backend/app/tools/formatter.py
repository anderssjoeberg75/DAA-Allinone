"""
==============================================================================
FILE: app/tools/formatter.py
DESCRIPTION: Centrala funktioner för att formatera data till naturligt talspråk.
==============================================================================
"""

def format_temp_for_speech(temp):
    """
    Formaterar temperaturvärden till naturligt talspråk för TTS.
    Ex: 2.5 -> "plus två komma fem grader"
    """
    try:
        if temp is None or str(temp).lower() in ['unknown', 'unavailable', 'none']:
            return "okänd temperatur"
        
        temp_val = float(temp)
        prefix = "plus " if temp_val >= 0 else "minus "
        abs_temp = abs(temp_val)
        
        # Ersätt punkt med komma
        temp_str = str(abs_temp).replace('.', ' komma ')
        
        # Snygga till heltal (ta bort " komma 0")
        if temp_str.endswith(' komma 0'):
            temp_str = temp_str.replace(' komma 0', '')
            
        return f"{prefix}{temp_str} grader"
    except Exception:
        return f"{temp} grader"