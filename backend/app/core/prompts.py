from datetime import datetime
from app.core.database import get_db_prompts

"""
==============================================================================
FILE: app/core/prompts.py
DESCRIPTION: Combines static text from DB with dynamic time/date.
==============================================================================
"""

def get_prompts_data():
    """Helper function to fetch all data from DB."""
    return get_db_prompts()

def get_system_prompt():
    """
    Builds the system prompt:
    1. Fetches personality/rules from Database.
    2. Adds real-time info (Time/Date) via Python.
    """
    # 1. Fetch base text from database
    data = get_prompts_data()
    # If DB is empty, use a simple fallback
    base_prompt = data.get("SYSTEM_PROMPT", "You are DAA. Fill in your prompt in settings.")

    # 2. Create time data (Real-time data injection)
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%Y-%m-%d")
    week_number = now.strftime("%V")
    
    # Day names in Swedish (for Swedish-speaking AI assistant)
    days_se = {
        "Monday": "måndag", "Tuesday": "tisdag", "Wednesday": "onsdag",
        "Thursday": "torsdag", "Friday": "fredag", "Saturday": "lördag", "Sunday": "söndag"
    }
    day_name = now.strftime("%A")
    swedish_day_name = days_se.get(day_name, day_name)
    
    # 3. Create context block
    time_context = (
        f"\n\n--- REAL-TIME INFORMATION (SYSTEM GENERATED) ---\n"
        f"- Time: {current_time}\n"
        f"- Date: {current_date}\n"
        f"- Day: {swedish_day_name}\n"
        f"- Week: {week_number}\n"
        f"---------------------------------------------------\n"
    )
    
    # 4. Inject APP_NAME into prompt (replace "DAA" with configured name)
    from config.settings import get_config
    cfg = get_config()
    app_name = cfg.get("APP_NAME", "DAA")
    
    # Replace all instances of "DAA" with the configured app name
    final_prompt = base_prompt.replace("DAA", app_name)
    
    # 5. Combine: Modified text + Time block
    return final_prompt + time_context

def get_audit_prompt():
    return get_prompts_data().get("CODE_AUDIT_PROMPT", "No code analysis prompt found.")

def get_audit_tool_desc():
    # Default description if missing from DB
    default = "Analyzes project source code to find errors and improvements."
    return get_prompts_data().get("TOOL_DESC_AUDIT", default)

# Variables for import to other files
CODE_AUDIT_PROMPT = get_audit_prompt()
ANALYZE_CODE_TOOL_DESC = get_audit_tool_desc()