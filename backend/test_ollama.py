import requests
import sys

# Tvinga utskrift direkt (ingen buffering)
def log(msg):
    print(msg, flush=True)

url = "http://127.0.0.1:11434/api/tags"

log(f"--- TESTAR OLLAMA PÅ: {url} ---")

try:
    log("1. Skickar förfrågan...")
    response = requests.get(url, timeout=5)
    
    log(f"2. Statuskod: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        models = data.get('models', [])
        log(f"3. Hittade {len(models)} modeller:")
        for m in models:
            name = m.get('name', m.get('model', 'Okänd'))
            log(f"   - {name}")
            
        if not models:
            log("   VARNING: Listan är tom! Du måste ladda ner en modell.")
            log("   Kör i terminalen: ollama pull gemma:2b")
    else:
        log(f"FEL: Fick konstigt svar: {response.text}")

except Exception as e:
    log(f"KRITISKT FEL: Kunde inte nå Ollama.")
    log(f"Orsak: {e}")
    log("\nTIPS:")
    log("- Är programmet 'Ollama' igång nere vid klockan?")
    log("- Blockeras port 11434 av en brandvägg?")

log("--- TEST KLART ---")