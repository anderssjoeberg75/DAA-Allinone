import React, { useEffect, useState, useRef } from 'react';
import io from 'socket.io-client';
import { Activity, Eye, Mic, Volume2, VolumeX, Zap, Cpu, Settings } from 'lucide-react';

// Konfigurera socket
const socket = io('http://localhost:8000', {
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 2000,
  transports: ['websocket', 'polling'] 
});

const Orb = ({ status }) => {
  const getColor = () => {
    if (status === 'speaking') return 'rgba(255, 215, 0, 0.6)';
    if (status === 'listening') return 'rgba(0, 191, 255, 0.6)';
    return 'rgba(0, 120, 255, 0.3)';
  };
  return (
    <div style={{
      width: '180px', height: '180px', borderRadius: '50%',
      background: `radial-gradient(circle, ${getColor()} 0%, rgba(0,0,0,0) 70%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: `0 0 40px ${getColor()}`,
      transition: 'all 0.5s ease',
      animation: status !== 'idle' ? 'pulse 2s infinite ease-in-out' : 'none'
    }}>
      <style>{`@keyframes pulse { 0% { transform: scale(0.95); opacity: 0.8; } 50% { transform: scale(1.05); opacity: 1; } 100% { transform: scale(0.95); opacity: 0.8; } }`}</style>
      <div style={{ width: '60%', height: '60%', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '50%' }}></div>
    </div>
  );
};

function App() {
  const [messages, setMessages] = useState([]);
  const [logs, setLogs] = useState([]);
  const [input, setInput] = useState("");
  const [orbStatus, setOrbStatus] = useState("idle"); 
  const [isMuted, setIsMuted] = useState(false);
  
  // STATE FÖR SETTINGS
  const [viewMode, setViewMode] = useState('chat'); // 'chat' eller 'settings'
  const [configData, setConfigData] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  
  // Refs för att hantera state inuti socket-lyssnare
  const isMutedRef = useRef(false);
  const currentResponseRef = useRef(""); 
  
  const [models, setModels] = useState([{id: 'loading', name: 'Connecting to Brain...'}]);
  const [selectedModel, setSelectedModel] = useState("loading");

  const messagesEndRef = useRef(null);
  const logEndRef = useRef(null);
  
  // Ref för videoströmmen
  const videoRef = useRef(null);

  // Håll ref uppdaterad när state ändras
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  useEffect(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);
  useEffect(() => logEndRef.current?.scrollIntoView({ behavior: "smooth" }), [logs]);

  const addLog = (text) => setLogs(prev => [...prev, text]);

  // --- KAMERA-INITIERING ---
  useEffect(() => {
    const startCamera = async () => {
        try {
            // Begär tillgång till kameran
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                addLog("[VIS] Camera connected.");
            }
        } catch (err) {
            addLog(`[VIS] Camera Error: ${err.message}`);
        }
    };
    startCamera();
  }, []);

  // --- TTS FUNKTION ---
  const speak = async (text) => {
    if (isMutedRef.current) return;
    if (!text) return;

    setOrbStatus("speaking");

    // 1. Försök med ElevenLabs via backend
    try {
        const response = await fetch('http://localhost:8000/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        if (response.ok) {
            const blob = await response.blob();
            const audioUrl = URL.createObjectURL(blob);
            const audio = new Audio(audioUrl);
            
            audio.onended = () => {
                setOrbStatus("idle");
                URL.revokeObjectURL(audioUrl); // Städa minne
            };
            
            audio.play();
            return; 
        }
    } catch (e) {
        console.warn("TTS Error (using fallback):", e);
    }

    // 2. FALLBACK: Webbläsarens inbyggda röst
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'sv-SE'; // Svenska
    utterance.rate = 1.0;     // Hastighet
    
    // När den pratar klart, sätt orb till idle
    utterance.onend = () => {
       setOrbStatus("idle");
    };

    window.speechSynthesis.speak(utterance);
  };

  // NY: Hämta inställningar från DB
  const loadSettings = async () => {
    try {
        const res = await fetch('http://localhost:8000/api/settings');
        const data = await res.json();
        setConfigData(data);
    } catch (e) {
        addLog(`[ERR] Could not load settings: ${e.message}`);
    }
  };

  // NY: Spara inställningar till DB
  const saveSettings = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
        await fetch('http://localhost:8000/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ settings: configData })
        });
        addLog("[SYS] Settings saved & reloaded.");
        setViewMode('chat'); // Gå tillbaka till chatten
    } catch (e) {
        addLog(`[ERR] Save failed: ${e.message}`);
    }
    setIsSaving(false);
  };

  const handleSettingChange = (key, val) => {
    setConfigData(prev => ({...prev, [key]: val}));
  };

  useEffect(() => {
    socket.on('connect', () => {
        addLog("[NET] Connected to Backend (Port 8000)");
        setOrbStatus("idle");
        socket.emit('get_models');
    });

    socket.on('connect_error', (err) => {
        addLog(`[NET] Connection Error: ${err.message}`);
        setModels([{id: 'error', name: 'OFFLINE (Retrying...)'}]);
    });

    socket.on('disconnect', () => {
        addLog("[NET] Disconnected from Brain");
        setModels([{id: 'error', name: 'Disconnected'}]);
    });

    socket.on('status', (d) => addLog(`[SYS] ${d.msg}`));
    
    // LOGIK FÖR MODELLVAL (Inkluderar fixen för Gemini 2.5)
    socket.on('models_list', (data) => {
        addLog(`[SYS] Models received: ${data.models.length}`);
        if (data.models && data.models.length > 0) {
            setModels(data.models);
            
            setSelectedModel(prev => {
                // 1. Behåll befintligt val om det fortfarande finns
                const exists = data.models.find(m => m.id === prev);
                if (exists) return prev;

                // 2. Leta efter "Gemini 2.5 Flash"
                const preferred = data.models.find(m => 
                    m.id.toLowerCase().includes("gemini-2.5-flash") || 
                    m.name.toLowerCase().includes("gemini 2.5 flash")
                );
                if (preferred) return preferred.id;

                // 3. Fallback: Försök med "Gemini 1.5 Flash"
                const fallback = data.models.find(m => m.id.includes("gemini-1.5-flash"));
                if (fallback) return fallback.id;

                // 4. Sista utväg: Ta den första modellen i listan
                return data.models[0].id;
            });
        } else {
             setModels([{id: 'error', name: 'No Models Available'}]);
        }
    });

    socket.on('ai_chunk', (data) => {
      // Samla texten i en ref för att läsa upp senare
      currentResponseRef.current += data.text;
      
      setOrbStatus("thinking"); // Visar att den jobbar
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'ai' && last.isStreaming) {
          return [...prev.slice(0, -1), { ...last, text: last.text + data.text }];
        }
        return [...prev, { role: 'ai', text: data.text, isStreaming: true }];
      });
    });

    socket.on('ai_done', () => {
        // Läs upp hela svaret när det är klart
        speak(currentResponseRef.current);
        currentResponseRef.current = ""; // Rensa för nästa gång

        setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last) return [...prev.slice(0, -1), { ...last, isStreaming: false }];
            return prev;
        });
    });

    return () => {
        socket.off('connect');
        socket.off('connect_error');
        socket.off('disconnect');
        socket.off('status');
        socket.off('models_list');
        socket.off('ai_chunk');
        socket.off('ai_done');
    };
  }, []);

  const sendMessage = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    if (!socket.connected) {
        addLog("[ERR] Cannot send message: Brain is offline.");
        return;
    }

    // Avbryt eventuellt gammalt tal
    window.speechSynthesis.cancel();
    currentResponseRef.current = "";

    setMessages(prev => [...prev, { role: 'user', text: input }]);
    setOrbStatus("listening");
    
    socket.emit('user_message', { 
        text: input,
        model: selectedModel 
    });
    setInput("");
  };

  const panelStyle = { width: '300px', background: '#0b0e14', border: '1px solid #30363d', borderRadius: '6px', display: 'flex', flexDirection: 'column', overflow: 'hidden' };
  const titleStyle = { padding: '10px', borderBottom: '1px solid #30363d', color: '#58a6ff', fontWeight: 'bold', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', padding: '10px', boxSizing: 'border-box', gap: '10px' }}>
      
      {/* VÄNSTER: SYSTEM */}
      <div style={{ ...panelStyle, width: '300px' }}>
        <div style={titleStyle}><Activity size={16}/> SYSTEM ACTIVITY</div>
        <div style={{ flex: 1, padding: '10px', overflowY: 'auto', fontFamily: 'Consolas, monospace', fontSize: '11px', color: '#e0e6ed' }}>
            {logs.map((l, i) => <div key={i} style={{marginBottom:'4px'}}>{l}</div>)}
            <div ref={logEndRef}/>
        </div>
      </div>

      {/* MITTEN: CHATT ELLER SETTINGS */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Orb status={orbStatus} /></div>
        
        <div style={{ flex: 1, background: '#0a0a1a', border: '1px solid #1f293a', borderRadius: '6px', padding: '15px', overflowY: 'auto', display:'flex', flexDirection:'column', gap:'10px' }}>
            
            {viewMode === 'chat' ? (
                /* --- CHAT VIEW --- */
                <>
                    {messages.map((m, i) => (
                        <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth:'85%' }}>
                            <div style={{ fontSize:'10px', color: m.role==='user'?'#00ffcc':'#58a6ff', marginBottom:'2px', textAlign: m.role==='user'?'right':'left' }}>{m.role === 'user' ? 'YOU' : 'DAA'}</div>
                            <div style={{ color: '#e0e6ed', whiteSpace: 'pre-wrap', fontSize: '14px', background: m.role === 'user' ? '#0d1117' : 'transparent', border: m.role === 'user' ? '1px solid #30363d' : 'none', padding: m.role === 'user' ? '8px 12px' : '0', borderRadius: '6px' }}>{m.text}</div>
                        </div>
                    ))}
                    <div ref={messagesEndRef}/>
                </>
            ) : (
                /* --- SETTINGS FORM --- */
                <div style={{ color: '#c9d1d9', padding: '10px', height: '100%', overflowY: 'auto' }}>
                    <h3 style={{ marginTop: 0, color: '#58a6ff', borderBottom: '1px solid #30363d', paddingBottom: '10px' }}>System Configuration</h3>
                    <form onSubmit={saveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                        
                        {/* LISTA MED ALLA INSTÄLLNINGAR */}
                        {[
                            'APP_NAME', 'VERSION', 'HISTORY_LIMIT',
                            'OLLAMA_URL', 
                            'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GROQ_API_KEY', 'DEEPSEEK_API_KEY',
                            'ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID',
                            'MEM0_API_KEY', // <-- NYTT FÄLT FÖR MEM0
                            'HA_BASE_URL', 'HA_TOKEN', 
                            'MQTT_BROKER_IP', 'MQTT_PORT', 'MQTT_TOPIC_BASE',
                            'GARMIN_EMAIL', 'GARMIN_PASSWORD',
                            'STRAVA_CLIENT_ID', 'STRAVA_CLIENT_SECRET', 'STRAVA_REFRESH_TOKEN',
                            'WITHINGS_CLIENT_ID', 'WITHINGS_CLIENT_SECRET', 'WITHINGS_REFRESH_TOKEN',
                            'LATITUDE', 'LONGITUDE'
                        ].map(key => (
                            <div key={key}>
                                <label style={{ display: 'block', fontSize: '12px', marginBottom: '5px', color: '#8b949e' }}>{key}</label>
                                <input 
                                    type="text" 
                                    value={configData[key] || ''} 
                                    onChange={(e) => handleSettingChange(key, e.target.value)}
                                    style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', color: '#e0e6ed', padding: '8px', borderRadius: '4px' }}
                                />
                            </div>
                        ))}
                        
                        <div style={{ paddingTop: '20px', borderTop: '1px solid #30363d', marginBottom: '20px' }}>
                            <button type="submit" disabled={isSaving} style={{ background: '#238636', color: 'white', border: 'none', padding: '10px 20px', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer', width: '100%' }}>
                                {isSaving ? 'SAVING...' : 'SAVE CONFIGURATION'}
                            </button>
                        </div>
                    </form>
                </div>
            )}
        </div>

        {/* INPUT FÄLT (Visas ENDAST i chatt-läget) */}
        {viewMode === 'chat' && (
            <form onSubmit={sendMessage} style={{ display: 'flex', gap: '10px' }}>
                <button type="button" style={{ background: '#161b22', border: '1px solid #30363d', color: '#58a6ff', width: '40px', display:'flex', alignItems:'center', justifyContent:'center', borderRadius:'4px' }}><Mic size={18}/></button>
                <input value={input} onChange={e => setInput(e.target.value)} placeholder="Type command..." style={{ flex: 1, background: '#0d1117', border: '1px solid #30363d', color: '#00ffcc', padding: '10px', fontWeight: 'bold', outline:'none', borderRadius:'4px' }} />
                <button type="submit" style={{ background: '#161b22', border: '1px solid #30363d', color: '#58a6ff', padding: '0 20px', borderRadius:'4px', fontWeight:'bold', cursor:'pointer' }}>SEND</button>
            </form>
        )}
      </div>

      {/* HÖGER: VISION & MODEL */}
      <div style={{ ...panelStyle, width: '320px' }}>
        
        {/* HEADER: Nu med Kugghjulet */}
        <div style={titleStyle}>
            <Eye size={16}/> VISION FEED
            
            {/* KUGGHJUL / AKTIVITETSIKON */}
            <div 
                style={{ marginLeft: 'auto', cursor: 'pointer', color: viewMode === 'settings' ? '#ff4444' : '#58a6ff' }}
                onClick={() => {
                    if (viewMode === 'chat') {
                        loadSettings();
                        setViewMode('settings');
                    } else {
                        setViewMode('chat');
                    }
                }}
            >
                {viewMode === 'settings' ? (
                    // I editering-läge: Visa aktivitet-ikonen (för att gå tillbaka)
                    <Activity size={16} /> 
                ) : (
                    // I chatt-läge: Visa kugghjulet (för att gå till settings)
                    <Settings size={16} />
                )}
            </div>
        </div>

        <div style={{ height: '240px', background: '#000', margin: '10px', border: '1px solid #30363d', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#333', fontSize: '12px', overflow: 'hidden' }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        <div style={{ padding: '0 15px', display:'flex', flexDirection:'column', gap:'12px' }}>
            
            {/* --- MODEL SELECTOR --- */}
            <div style={{display:'flex', flexDirection:'column', gap:'5px'}}>
                <div style={{color: '#c9d1d9', fontSize:'12px', display:'flex', alignItems:'center', gap:'5px'}}>
                    <Cpu size={14}/> AI Model:
                </div>
                <select 
                    value={selectedModel} 
                    onChange={(e) => setSelectedModel(e.target.value)}
                    style={{ background: '#0d1117', color: '#00ffcc', border: '1px solid #30363d', padding: '8px', borderRadius: '4px', outline: 'none', fontSize: '13px', cursor: 'pointer', width: '100%' }}
                >
                    {models.map((m, i) => (
                        <option key={i} value={m.id}>{m.name}</option>
                    ))}
                </select>
            </div>
            
            <hr style={{border: '0', borderTop: '1px solid #30363d', width: '100%', margin: '5px 0'}}/>
            <div style={{color: '#c9d1d9', fontSize:'12px'}}>Image Source: Webcam</div>
            <label style={{display:'flex', alignItems:'center', gap:'10px', color:'#c9d1d9', fontSize:'13px', cursor:'pointer'}}><input type="checkbox" style={{accentColor: '#00ffcc'}} /> <span><Zap size={14} style={{verticalAlign:'middle'}}/> AUTO MOTION</span></label>
            <label style={{display:'flex', alignItems:'center', gap:'10px', color:'#c9d1d9', fontSize:'13px', cursor:'pointer'}}><input type="checkbox" style={{accentColor: '#00ffcc'}} /> <span><Eye size={14} style={{verticalAlign:'middle'}}/> SEND IMAGE</span></label>
            <div style={{marginTop:'10px', paddingTop:'10px'}}>
                <button onClick={() => setIsMuted(!isMuted)} style={{ width:'100%', padding:'10px', background: '#161b22', border: '1px solid #30363d', color: isMuted ? '#ff4444' : '#58a6ff', fontWeight:'bold', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:'8px', borderRadius:'4px' }}>
                    {isMuted ? <VolumeX size={16}/> : <Volume2 size={16}/>} {isMuted ? "UNMUTE" : "MUTE"}
                </button>
            </div>
        </div>
      </div>
    </div>
  );
}

export default App;