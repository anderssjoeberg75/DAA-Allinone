from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>DAA Interface</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&family=Roboto:wght@300;400&display=swap" rel="stylesheet">
    <style>
        :root { --color-idle: #00d4ff; --color-listen: #ff0055; --bg-color: #050505; }
        body { background: var(--bg-color); color: white; font-family: 'Roboto', sans-serif; margin: 0; height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; user-select: none; }
        .header { position: absolute; top: 30px; text-align: center; width: 100%; pointer-events: none; }
        .daa-title { font-family: 'Orbitron', sans-serif; font-size: 3rem; letter-spacing: 5px; color: var(--color-idle); text-shadow: 0 0 20px rgba(0, 212, 255, 0.4); margin: 0; }
        .orb-container { position: relative; width: 260px; height: 260px; display: flex; align-items: center; justify-content: center; margin-top: -20px; z-index: 100; }
        
        /* KNAPPEN */
        button.orb {
            appearance: none; outline: none; border: 4px solid rgba(255,255,255,0.1);
            width: 180px; height: 180px; border-radius: 50%;
            background: radial-gradient(circle, var(--color-idle) 0%, #004080 100%);
            box-shadow: 0 0 50px rgba(0, 212, 255, 0.2);
            transition: all 0.2s ease; display: flex; align-items: center; justify-content: center;
            z-index: 200; cursor: pointer; color: white; margin: 0; padding: 0;
        }
        button.orb:active { transform: scale(0.95); }
        .orb-icon { font-size: 4rem; pointer-events: none; }
        
        /* RINGAR */
        .ring { position: absolute; border-radius: 50%; border: 2px solid transparent; border-top-color: var(--color-idle); border-bottom-color: var(--color-idle); opacity: 0.3; pointer-events: none; z-index: 50; }
        .ring-1 { width: 220px; height: 220px; animation: spin 10s linear infinite; }
        .ring-2 { width: 250px; height: 250px; animation: spin-rev 15s linear infinite; border-left-color: var(--color-idle); border-top-color: transparent; }
        
        body.state-listening .orb { background: radial-gradient(circle, var(--color-listen) 0%, #5e001f 100%); box-shadow: 0 0 80px rgba(255, 0, 85, 0.5); transform: scale(1.05); }
        body.state-listening .ring { border-color: var(--color-listen); opacity: 0.6; }
        
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes spin-rev { 0% { transform: rotate(360deg); } 100% { transform: rotate(0deg); } }

        #output-area { width: 85%; text-align: center; margin-top: 40px; min-height: 80px; z-index: 10; pointer-events: none; }
        #main-text { font-size: 1.5rem; line-height: 1.4; color: #e0e0e0; font-weight: 300; }
        #debug-console { position: absolute; bottom: 10px; width: 90%; font-family: monospace; font-size: 0.8rem; color: #ffff00; text-align: center; border-top: 1px solid #333; padding-top: 5px; z-index: 300; }
    </style>
</head>
<body>
    <div class="header"><div class="daa-title">DAA</div></div>
    
    <div class="orb-container">
        <div class="ring ring-1"></div>
        <div class="ring ring-2"></div>
        <button class="orb" id="mic-btn" onclick="runSequence()">
            <div class="orb-icon">🎙️</div>
        </button>
    </div>

    <div id="output-area"><div id="main-text">Tryck på orben</div></div>
    <div id="debug-console">System Redo (HTTPS).</div>

    <script>
        const body = document.body;
        const mainText = document.getElementById('main-text');
        const debugConsole = document.getElementById('debug-console');
        const synth = window.speechSynthesis;
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

        function log(msg) { debugConsole.innerText = "> " + msg; console.log(msg); }
        function setState(state) { body.className = ''; if(state) body.classList.add('state-' + state); }

        if (!SpeechRec) mainText.innerText = "FEL: Ingen röstmotor.";

        // DETTA ÄR DIAGNOS-LOGIKEN (KOPIERAD)
        async function runSequence() {
            log("1. Knapp tryckt.");
            
            if (synth.speaking) { synth.cancel(); setState(''); mainText.innerText = "Avbruten."; return; }

            // STEG A: Hårdvaru-check (Måste göras på HTTPS för Android)
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach(t => t.stop());
                log("2. Hårdvara OK.");
            } catch (err) {
                log("Hårdvaru-fel: " + err.message);
                mainText.innerText = "Ingen mic-åtkomst!";
                return;
            }

            // STEG B: Starta Google Speech
            log("3. Startar motor...");
            const rec = new SpeechRec();
            rec.lang = 'sv-SE';
            rec.continuous = false;

            rec.onstart = () => {
                setState('listening');
                mainText.innerText = "Jag lyssnar...";
                log("4. LYSSNAR NU!");
            };

            rec.onresult = async (event) => {
                const text = event.results[0][0].transcript;
                mainText.innerText = '"' + text + '"';
                log("Hörde: " + text);
                await processQuery(text);
            };

            rec.onerror = (e) => { setState(''); log("FEL: " + e.error); };
            rec.onend = () => { if (!body.classList.contains('state-thinking')) setState(''); log("Klar."); };

            try { rec.start(); } catch(e) { log("Startfel: " + e.message); }
        }

        async function processQuery(text) {
            body.classList.add('state-thinking'); // Manuell override för färg
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ model: "gemini-1.5-flash", messages: [{role: "user", content: text}], session_id: "daa-web-final" })
                });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullText = "";
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    fullText += decoder.decode(value);
                    mainText.innerText = fullText; 
                }
                speakResponse(fullText);
            } catch (err) { setState(''); mainText.innerText = "Serverfel."; log("API Fel: " + err.message); }
        }

        function speakResponse(text) {
            setState(''); // Rensa lyssnar-färg
            // Lägg till 'speaking' klass om du vill ha grön färg här
            const utter = new SpeechSynthesisUtterance(text);
            utter.lang = 'sv-SE';
            synth.speak(utter);
            utter.onend = () => { mainText.innerText = "Redo."; };
        }
    </script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse)
async def get_ui():
    return HTML_CONTENT