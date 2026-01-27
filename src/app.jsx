import React, { useEffect, useState, useRef } from 'react';
import io from 'socket.io-client';
import Orb from './components/Orb';
import SystemLog from './components/SystemLog';
import ChatPanel from './components/ChatPanel';
import SettingsPanel from './components/SettingsPanel';
import PromptsPanel from './components/PromptsPanel'; // <-- IMPORTERA DEN NYA PANELEN
import VideoFeed from './components/VideoFeed';
import './index.css';

const socket = io('http://localhost:8000', {
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 2000,
  transports: ['websocket', 'polling'] 
});

function App() {
  const [logs, setLogs] = useState([]);
  const [orbStatus, setOrbStatus] = useState("idle"); 
  const [viewMode, setViewMode] = useState('chat'); 
  const [configData, setConfigData] = useState({});
  const [messages, setMessages] = useState([]);
  const [isMuted, setIsMuted] = useState(false);
  
  const [models, setModels] = useState([{id: 'loading', name: 'Laddar modeller...'}]);
  const [selectedModel, setSelectedModel] = useState("loading");
  
  const currentResponseRef = useRef(""); 

  const addLog = (text) => setLogs(prev => [...prev, text]);

  const speak = async (text) => {
    if (isMuted || !text) return;
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
    } catch (e) { console.warn("TTS failed:", e); }

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

  const handleSendMessage = (text) => {
    if (!socket.connected) return;
    window.speechSynthesis.cancel();
    setMessages(prev => [...prev, { role: 'user', text: text }]);
    currentResponseRef.current = ""; 
    socket.emit('user_message', { text: text, model: selectedModel });
  };

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
    socket.on('connect', () => { addLog("[NET] Connected"); socket.emit('get_models'); });
    socket.on('disconnect', () => { addLog("[NET] Disconnected"); setOrbStatus("idle"); });
    socket.on('status', (d) => {
        addLog(`[SYS] ${d.msg}`);
        if (d.msg === 'DAA Live: Active') setOrbStatus('active');
        if (d.msg === 'DAA Live Stopped') setOrbStatus('idle');
    });
    socket.on('error', (d) => { addLog(`[ERR] ${d.msg}`); setOrbStatus('error'); });
    
    socket.on('models_list', (data) => {
        if (data.models && data.models.length > 0) {
            setModels(data.models);
            const currentIsValid = data.models.some(m => m.id === selectedModel);
            if (!currentIsValid) {
                setSelectedModel(data.models[0].id);
                addLog(`[SYS] Auto-selected model: ${data.models[0].name}`);
            }
        }
    });

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
  }, [selectedModel, isMuted]);

  const toggleViewMode = () => {
    if (viewMode === 'chat') {
        loadSettings();
        setViewMode('settings');
    } else {
        setViewMode('chat');
    }
  };

  // NY FUNKTION: Växla till prompts
  const togglePromptsMode = () => {
    setViewMode(viewMode === 'prompts' ? 'chat' : 'prompts');
  };

  return (
    <div className="app-container">
      <SystemLog logs={logs} />
      
      <div className="main-area">
        <div className="orb-section">
            <Orb status={orbStatus} onClick={toggleLiveSession} />
            <div className="orb-label">
                {orbStatus === 'active' ? 'LISTENING...' : 'TAP TO SPEAK'}
            </div>
        </div>
        
        {/* LOGIK FÖR ATT VISA RÄTT PANEL */}
        {viewMode === 'settings' ? (
           <div className="chat-window">
             <SettingsPanel 
                config={configData} 
                onSave={saveSettings} 
                onChange={(key, val) => setConfigData(prev => ({...prev, [key]: val}))} 
             />
           </div>
        ) : viewMode === 'prompts' ? (
           <div className="chat-window">
             <PromptsPanel />
           </div>
        ) : (
           <ChatPanel messages={messages} onSendMessage={handleSendMessage} />
        )}
      </div>

      <VideoFeed 
        viewMode={viewMode}
        onToggleView={toggleViewMode}
        onTogglePrompts={togglePromptsMode}
        models={models}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        isMuted={isMuted}
        onToggleMute={() => setIsMuted(!isMuted)}
        addLog={addLog}
      />
    </div>
  );
}

export default App;