import os
import google.generativeai as genai
from openai import OpenAI
try:
    import anthropic
except ImportError:
    anthropic = None 

from config.settings import get_config
from app.core.prompts import CODE_AUDIT_PROMPT

# Konfiguration
OUTPUT_FILE = "../../DAA_CODE_REVIEW.md"
IGNORED_DIRS = {
    'venv', 'node_modules', '.git', '__pycache__', 'logs', 'dist', 'build', 
    'garmin_tokens', '.vscode', 'assets', 'site-packages', '__init__', 'frontend'
}
ALLOWED_EXTENSIONS = {'.py', '.js', '.jsx', '.html', '.css', '.bat', '.json'}
IGNORED_FILES = {'package-lock.json', 'service_account.json', 'daa_memory.db', 'DAA_CODE_REVIEW.md'}

def get_project_code(root_dir):
    """Läser in all kod rekursivt."""
    code_content = ""
    file_count = 0
    actual_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    
    print(f"[AUDIT] Läser filer från: {actual_root}")
    
    for subdir, dirs, files in os.walk(actual_root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in ALLOWED_EXTENSIONS and file not in IGNORED_FILES:
                file_path = os.path.join(subdir, file)
                rel_path = os.path.relpath(file_path, actual_root)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        code_content += f"\n--- FIL: {rel_path} ---\n{f.read()}\n"
                        file_count += 1
                except Exception as e:
                    print(f"[SKIP] Kunde inte läsa {rel_path}: {e}")
                    
    return code_content, file_count

def process_and_save_response(full_response_text, model_name):
    SEPARATOR = "---RAPPORT_START---"
    try:
        abs_output = os.path.abspath(os.path.join(os.path.dirname(__file__), OUTPUT_FILE))
        with open(abs_output, "w", encoding="utf-8") as f:
            f.write(full_response_text)
        file_saved_msg = f"\n\n📂 *Fullständig rapport sparad till: {OUTPUT_FILE}*"
    except Exception as e:
        file_saved_msg = f"\n\n⚠️ Kunde inte spara rapportfilen: {e}"

    if SEPARATOR in full_response_text:
        summary_for_chat = full_response_text.split(SEPARATOR)[0].strip()
    else:
        summary_for_chat = full_response_text[:1000] + "...\n(Se filen för resten)"

    return f"✅ **Analys klar med {model_name}!**\n\n{summary_for_chat}{file_saved_msg}"

def run_code_audit(preferred_model=None):
    cfg = get_config()
    print("[AUDIT] Startar insamling av kod...")
    full_code, count = get_project_code(".")
    
    if count == 0: 
        print("[AUDIT] Inga filer hittades!")
        return "Hittade inga filer att analysera. Kontrollera sökvägarna."
    
    print(f"[AUDIT] Hittade {count} filer. Skickar till AI...")
    
    final_prompt = f"{CODE_AUDIT_PROMPT}\n\nKÄLLKOD ({count} filer):\n{full_code}"

    # Lista modeller att testa
    test_models = ['gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gpt-4o']

    for model_name in test_models:
        try:
            # --- GOOGLE ---
            if "gemini" in model_name.lower() and cfg.get("GOOGLE_API_KEY"):
                print(f"   - Testar Google: {model_name}")
                genai.configure(api_key=cfg["GOOGLE_API_KEY"])
                # VIKTIGT: Stäng av filter här också
                safety = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                model = genai.GenerativeModel(model_name, safety_settings=safety)
                response = model.generate_content(final_prompt)
                return process_and_save_response(response.text, f"Google {model_name}")

            # --- OPENAI ---
            elif "gpt" in model_name.lower() and cfg.get("OPENAI_API_KEY"):
                print(f"   - Testar OpenAI: {model_name}")
                client = OpenAI(api_key=cfg["OPENAI_API_KEY"])
                res = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": CODE_AUDIT_PROMPT},
                              {"role": "user", "content": f"KOD:\n{full_code}"}]
                )
                return process_and_save_response(res.choices[0].message.content, model_name)

        except Exception as e:
            print(f"   x {model_name} misslyckades: {e}")
            continue

    return "⚠️ Kunde inte analysera koden. Kontrollera API-nycklar och internetanslutning."