import React, { useEffect, useState, useRef } from 'react';
import io from 'socket.io-client';
import { Activity, Eye, Mic, Volume2, VolumeX, Zap, Cpu, Settings, Power, Send } from 'lucide-react';

const socket = io('http://localhost:8000', {
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 2000,
  transports: ['websocket', 'polling'] 
});

const Orb = ({ status, onClick }) => { 
  const getColor = () => {
    if (status === 'active') return 'rgba(0, 255, 136, 0.6)';
    if (status === 'connecting') return 'rgba(255, 215, 0, 0.6)';
    if (status === 'error') return 'rgba(255, 0, 85, 0.6)';
    return 'rgba(0, 120, 255, 0.3)';
  };

  return (
    <div 
      onClick={onClick} 
      style={{
      width: '120px', height: '120px', borderRadius: '50%',
      background: `radial-gradient(circle, ${getColor()} 0%, rgba(0,0,0,0) 70%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: `0 0 30px ${getColor()}`,
      transition: 'all 0.5s ease',
      cursor: 'pointer',
      margin: '0 auto',
      animation: status === 'active' ? 'pulse 2s infinite ease-in-out' : 'none'
    }}>
      <style>{`@keyframes pulse { 0% { transform: scale(0.95); opacity: 0.8; } 50% { transform: scale(1.05); opacity: 1; } 100% { transform: scale(0.95); opacity: 0.8; } }`}</style>
      <div style={{ width: '60%', height: '60%', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '50%', display:'flex', alignItems:'center', justifyContent:'center' }}>
          {status === 'active' ? <Mic size={30} color="white" style={{opacity:0.8}} /> : <Power size={30} color="white" style={{opacity:0.8}} />}
      </div>
    </div>
  );
};

function App() {
  const [logs, setLogs] = useState([]);
  const [orbStatus, setOrbStatus] = useState("idle"); 
  const [viewMode, setViewMode] = useState('chat'); 
  const [configData, setConfigData] = useState({});
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isMuted, setIsMuted] = useState(false);
  const [models, setModels] = useState([{id: 'loading', name: 'Loading models...'}]);
  const [selectedModel, setSelectedModel] = useState("gemini-1.5-flash");
  
  const logEndRef = useRef(null);
  const messagesEndRef = useRef(null);
  const videoRef = useRef(null);
  const currentResponseRef = useRef(""); 

  useEffect(() => logEndRef.current?.scrollIntoView({ behavior: "smooth" }), [logs]);
  useEffect(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const addLog = (text) => setLogs(prev => [...prev, text]);

  // --- TTS (Fungerar för BÅDE text och röst nu) ---
  const speak = async (text) => {
    if (isMuted || !text) return;
    
    // Försök med ElevenLabs via backend
    try {
        const response = await fetch('http://localhost:8000/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play();
            return;
        }
    } catch (e) { 
        console.warn("ElevenLabs TTS failed, using fallback:", e); 
    }

    // Fallback till webbläsarens röst
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'sv-SE'; 
    window.speechSynthesis.speak(utterance);
  };

  const toggleLiveSession = () => {
    if (orbStatus === 'active') {
        socket.emit('stop_audio');
        setOrbStatus('idle');
    } else {
        setOrbStatus('connecting');
        socket.emit('start_audio');
    }
  };

  const sendMessage = (e) => {
    e.preventDefault();
    if (!input.trim() || !socket.connected) return;
    window.speechSynthesis.cancel();
    setMessages(prev => [...prev, { role: 'user', text: input }]);
    currentResponseRef.current = ""; 
    socket.emit('user_message', { text: input, model: selectedModel });
    setInput("");
  };

  useEffect(() => {
    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) videoRef.current.srcObject = stream;
        } catch (err) { addLog(`[VIS] Camera Error: ${err.message}`); }
    };
    startCamera();
  }, []);

  const loadSettings = async () => {
    try {
        const res = await fetch('http://localhost:8000/api/settings');
        setConfigData(await res.json());
    } catch (e) { addLog(`[ERR] Settings error: ${e.message}`); }
  };

  const saveSettings = async (e) => {
    e.preventDefault();
    try {
        await fetch('http://localhost:8000/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ settings: configData })
        });
        addLog("[SYS] Settings saved.");
        setViewMode('chat');
    } catch (e) { addLog(`[ERR] Save failed: ${e.message}`); }
  };

  useEffect(() => {
    socket.on('connect', () => {
        addLog("[NET] Connected");
        socket.emit('get_models');
    });

    socket.on('disconnect', () => {
        addLog("[NET] Disconnected");
        setOrbStatus("idle");
    });

    socket.on('status', (d) => {
        addLog(`[SYS] ${d.msg}`);
        if (d.msg === 'DAA Live: Active') setOrbStatus('active');
        if (d.msg === 'DAA Live Stopped') setOrbStatus('idle');
    });

    socket.on('error', (d) => {
        addLog(`[ERR] ${d.msg}`);
        setOrbStatus('error');
    });

    socket.on('models_list', (data) => {
        if (data.models && data.models.length > 0) {
            setModels(data.models);
            if (!data.models.some(m => m.id === selectedModel)) setSelectedModel(data.models[0].id);
        }
    });

    // Tar emot text-delar (både från chatt och röst)
    socket.on('ai_chunk', (data) => {
      currentResponseRef.current += data.text;
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'ai' && last.isStreaming) {
          return [...prev.slice(0, -1), { ...last, text: last.text + data.text }];
        }
        return [...prev, { role: 'ai', text: data.text, isStreaming: true }];
      });
    });

    // När svaret är klart -> PRATA (oavsett källa)
    socket.on('ai_done', () => {
        speak(currentResponseRef.current);
        
        setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last) return [...prev.slice(0, -1), { ...last, isStreaming: false }];
            return prev;
        });
    });

    return () => {
        socket.off('connect');
        socket.off('disconnect');
        socket.off('status');
        socket.off('error');
        socket.off('models_list');
        socket.off('ai_chunk');
        socket.off('ai_done');
    };
  }, [selectedModel, isMuted]); // tog bort orbStatus beroendet då det inte behövs för logiken längre

  const panelStyle = { width: '300px', background: '#0b0e14', border: '1px solid #30363d', borderRadius: '6px', display: 'flex', flexDirection: 'column', overflow: 'hidden' };
  const titleStyle = { padding: '10px', borderBottom: '1px solid #30363d', color: '#58a6ff', fontWeight: 'bold', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', padding: '10px', boxSizing: 'border-box', gap: '10px' }}>
      <div style={{ ...panelStyle, width: '300px' }}>
        <div style={titleStyle}><Activity size={16}/> SYSTEM ACTIVITY</div>
        <div style={{ flex: 1, padding: '10px', overflowY: 'auto', fontFamily: 'Consolas, monospace', fontSize: '11px', color: '#e0e6ed' }}>
            {logs.map((l, i) => <div key={i} style={{marginBottom:'4px'}}>{l}</div>)}
            <div ref={logEndRef}/>
        </div>
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div style={{ flexShrink: 0, padding: '10px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <Orb status={orbStatus} onClick={toggleLiveSession} />
            <div style={{ color: '#58a6ff', fontSize: '11px', letterSpacing: '1px', marginTop: '10px' }}>
                {orbStatus === 'active' ? 'LISTENING...' : 'TAP TO SPEAK'}
            </div>
        </div>
        <div style={{ flex: 1, background: '#0a0a1a', border: '1px solid #1f293a', borderRadius: '6px', padding: '15px', overflowY: 'auto', display:'flex', flexDirection:'column', gap:'10px' }}>
            {viewMode === 'settings' ? (
                <div style={{ color: '#c9d1d9', padding: '10px' }}>
                    <h3 style={{ marginTop: 0, color: '#58a6ff' }}>System Configuration</h3>
                    <form onSubmit={saveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                        {['GOOGLE_API_KEY', 'OPENAI_API_KEY', 'ELEVENLABS_API_KEY', 'GARMIN_EMAIL', 'GARMIN_PASSWORD', 'STRAVA_CLIENT_ID'].map(key => (
                            <div key={key}>
                                <label style={{ display: 'block', fontSize: '12px', marginBottom: '5px', color: '#8b949e' }}>{key}</label>
                                <input type="text" value={configData[key] || ''} onChange={(e) => setConfigData(prev => ({...prev, [key]: e.target.value}))} style={{ width: '100%', background: '#0d1117', border: '1px solid #30363d', color: '#e0e6ed', padding: '8px', borderRadius: '4px' }}/>
                            </div>
                        ))}
                        <button type="submit" style={{ background: '#238636', color: 'white', border: 'none', padding: '10px', borderRadius: '6px', cursor: 'pointer' }}>SAVE</button>
                    </form>
                </div>
            ) : (
                <>
                    {messages.map((m, i) => (
                        <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth:'85%' }}>
                            <div style={{ fontSize:'10px', color: m.role==='user'?'#00ffcc':'#58a6ff', marginBottom:'2px', textAlign: m.role==='user'?'right':'left' }}>{m.role === 'user' ? 'YOU' : 'DAA'}</div>
                            <div style={{ color: '#e0e6ed', whiteSpace: 'pre-wrap', fontSize: '14px', background: m.role === 'user' ? '#0d1117' : 'transparent', border: m.role === 'user' ? '1px solid #30363d' : 'none', padding: m.role === 'user' ? '8px 12px' : '0', borderRadius: '6px' }}>{m.text}</div>
                        </div>
                    ))}
                    <div ref={messagesEndRef}/>
                </>
            )}
        </div>
        {viewMode === 'chat' && (
            <form onSubmit={sendMessage} style={{ display: 'flex', gap: '10px' }}>
                <input value={input} onChange={e => setInput(e.target.value)} placeholder="Type command..." style={{ flex: 1, background: '#0d1117', border: '1px solid #30363d', color: '#00ffcc', padding: '10px', borderRadius:'4px' }} />
                <button type="submit" style={{ background: '#161b22', border: '1px solid #30363d', color: '#58a6ff', padding: '0 15px', borderRadius:'4px', cursor:'pointer' }}><Send size={18} /></button>
            </form>
        )}
      </div>
      <div style={{ ...panelStyle, width: '320px' }}>
        <div style={titleStyle}>
            <Eye size={16}/> VISION FEED
            <div style={{ marginLeft: 'auto', cursor: 'pointer', color: viewMode === 'settings' ? '#ff4444' : '#58a6ff' }} onClick={() => { viewMode === 'chat' ? (loadSettings(), setViewMode('settings')) : setViewMode('chat') }}>
                {viewMode === 'settings' ? <Activity size={16} /> : <Settings size={16} />}
            </div>
        </div>
        <div style={{ height: '240px', background: '#000', margin: '10px', border: '1px solid #30363d', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        <div style={{ padding: '0 15px', display:'flex', flexDirection:'column', gap:'12px' }}>
            <div style={{display:'flex', flexDirection:'column', gap:'5px'}}>
                <div style={{color: '#c9d1d9', fontSize:'12px', display:'flex', alignItems:'center', gap:'5px'}}><Cpu size={14}/> Text Chat Model:</div>
                <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} style={{ background: '#0d1117', color: '#00ffcc', border: '1px solid #30363d', padding: '8px', borderRadius: '4px', width: '100%' }}>
                    {models.map((m, i) => (<option key={i} value={m.id}>{m.name}</option>))}
                </select>
            </div>
            <button onClick={() => setIsMuted(!isMuted)} style={{ width:'100%', padding:'10px', background: '#161b22', border: '1px solid #30363d', color: isMuted ? '#ff4444' : '#58a6ff', cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:'8px', borderRadius:'4px' }}>
                 {isMuted ? <VolumeX size={16}/> : <Volume2 size={16}/>} {isMuted ? "UNMUTE TTS" : "MUTE TTS"}
            </button>
        </div>
      </div>
    </div>
  );
}

export default App;