import speech_recognition as sr
import os
import traceback

# Initiera recognizer
r = sr.Recognizer()

# Inställningar för känslighet
r.energy_threshold = 100        
r.dynamic_energy_threshold = True 
r.dynamic_energy_adjustment_damping = 0.15
r.pause_threshold = 0.8         

def listen_and_transcribe_local():
    """
    Lyssnar via datorns mikrofon och transkriberar med lokal Whisper.
    Returnerar texten eller en specifik felkod.
    """
    print("[VOICE] Justerar för bakgrundsljud... (var tyst i 1 sek)")
    
    try:
        # Om du har flera mikrofoner kan du behöva ändra till device_index=1 här
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=1)
            print(f"[VOICE] Redo! (Threshold: {r.energy_threshold})")
            
            try:
                print("[VOICE] Lyssnar nu! Prata...")
                audio = r.listen(source, timeout=5, phrase_time_limit=15)
                print("[VOICE] Ljud fångat! Bearbetar med Whisper (Small)...")
                
                # Transkribera lokalt med Whisper (Svenska)
                text = r.recognize_whisper(audio, model="small", language="sv")
                text = text.strip()
                
                print(f"[VOICE] Hörde: {text}")
                return text
                
            except sr.WaitTimeoutError:
                print("[VOICE] Timeout: Inget tal uppfattades.")
                return "TIMEOUT_ERROR"
            except Exception as e:
                print(f"[VOICE] Fel vid bearbetning: {e}")
                return f"ERROR: {str(e)}"
                
    except Exception as e:
        # Detta loggas i backend-konsolen
        print(f"[VOICE] KRITISKT FEL: Kunde inte starta mikrofonen. Är den upptagen?")
        traceback.print_exc() 
        return "MIC_ERROR"