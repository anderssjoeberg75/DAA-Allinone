import React, { useEffect, useState, useRef } from 'react';
import SystemLog from './components/SystemLog';
import ChatPanel from './components/ChatPanel';
import SettingsPanel from './components/SettingsPanel';
import PromptsPanel from './components/PromptsPanel';
import MemoryPanel from './components/MemoryPanel';  // <--- ADDED MISSING IMPORT
import VideoFeed from './components/VideoFeed';
import VoiceMode from './components/VoiceMode';
import './index.css';

import { useAudioQueue } from './hooks/useAudioQueue';
import { useSocket } from './hooks/useSocket';

function App() {
  const [logs, setLogs] = useState([]);
  const [viewMode, setViewMode] = useState('chat'); // 'chat', 'settings', 'prompts', 'voice'
  const [configData, setConfigData] = useState({});
  const [messages, setMessages] = useState([]);
  const [isMuted, setIsMuted] = useState(false);

  const [models, setModels] = useState([{ id: 'loading', name: 'Loading models...' }]);
  const [selectedModel, setSelectedModel] = useState("loading");

  // Live Chat Mode toggle
  const [useLiveMode, setUseLiveMode] = useState(false);

  const currentResponseRef = useRef("");

  // Custom Hooks
  const { socket, isConnected } = useSocket();
  const { addToQueue, addTextToBuffer, clearAudio, filterTextForTTS } = useAudioQueue();

  const addLog = (text) => setLogs(prev => [...prev, text]);

  // Handle Socket Events
  useEffect(() => {
    if (!socket) return;

    const onConnect = () => { addLog("[NET] Connected"); socket.emit('get_models'); };
    const onDisconnect = () => { addLog("[NET] Disconnected"); };
    const onStatus = (d) => addLog(`[SYS] ${d.msg}`);
    const onError = (d) => addLog(`[ERR] ${d.msg}`);

    const onModelsList = (data) => {
      if (data.models && data.models.length > 0) {
        setModels(data.models);
        const currentIsValid = data.models.some(m => m.id === selectedModel);
        if (!currentIsValid) {
          setSelectedModel(data.models[0].id);
          addLog(`[SYS] Auto-selected model: ${data.models[0].name}`);
        }
      }
    };

    const onAiChunk = (data) => {
      const chunk = data.text || '';
      currentResponseRef.current += chunk;

      // Add chunk to text buffer for TTS processing (filtered)
      const filteredChunk = filterTextForTTS(chunk);
      if (filteredChunk && !isMuted && !useLiveMode) {
        addTextToBuffer(filteredChunk, isMuted);
      }

      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'ai' && last.isStreaming) {
          return [...prev.slice(0, -1), { ...last, text: last.text + chunk }];
        }
        return [...prev, { role: 'ai', text: chunk, isStreaming: true }];
      });
    };

    const onAiDone = () => {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last) return [...prev.slice(0, -1), { ...last, isStreaming: false }];
        return prev;
      });
    };

    const onAudioChunk = (data) => {
      console.log('🎵 [LIVE CHAT] Got audio chunk!', data.audio?.substring(0, 50));
      if (isMuted) return;

      try {
        const audioData = atob(data.audio);
        const audioArray = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
          audioArray[i] = audioData.charCodeAt(i);
        }
        const blob = new Blob([audioArray], { type: 'audio/pcm' });
        addToQueue(blob);
      } catch (e) {
        console.warn("Audio chunk decode error:", e);
      }
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('status', onStatus);
    socket.on('error', onError);
    socket.on('models_list', onModelsList);
    socket.on('ai_chunk', onAiChunk);
    socket.on('ai_done', onAiDone);
    socket.on('audio_chunk', onAudioChunk);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('status', onStatus);
      socket.off('error', onError);
      socket.off('models_list', onModelsList);
      socket.off('ai_chunk', onAiChunk);
      socket.off('ai_done', onAiDone);
      socket.off('audio_chunk', onAudioChunk);
    };
  }, [socket, selectedModel, isMuted, useLiveMode, addToQueue, addTextToBuffer, filterTextForTTS]);


  const handleSendMessage = (messageData) => {
    if (!socket || !isConnected) return;
    clearAudio();

    // Determine if message is text string or object with image
    let text = "";
    let image = null;

    if (typeof messageData === 'string') {
      text = messageData;
    } else {
      text = messageData.text;
      image = messageData.image;
    }

    setMessages(prev => [...prev, { role: 'user', text: text, image: image }]);
    currentResponseRef.current = "";

    if (useLiveMode) {
      // Live mode currently only supports text start, but we can expand lated
      socket.emit('start_live_chat', { message: text });
    } else {
      socket.emit('user_message', { text: text, image: image, model: selectedModel });
    }
  };

  const loadSettings = async () => {
    try {
      const url = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${url}/api/settings`);
      setConfigData(await res.json());
    } catch (e) { addLog(`[ERR] Settings error: ${e.message}`); }
  };

  const saveSettings = async (e) => {
    e.preventDefault();
    try {
      const url = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      await fetch(`${url}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: configData })
      });
      addLog("[SYS] Settings saved.");
      setViewMode('chat');
    } catch (e) { addLog(`[ERR] Save failed: ${e.message}`); }
  };

  const toggleViewMode = () => {
    if (viewMode === 'chat') {
      loadSettings();
      setViewMode('settings');
    } else {
      setViewMode('chat');
    }
  };

  return (
    <div className="app-container">
      <SystemLog logs={logs} />

      <div className="main-area">
        {viewMode === 'settings' ? (
          <div className="chat-window">
            <SettingsPanel
              config={configData}
              onSave={saveSettings}
              onChange={(key, val) => setConfigData(prev => ({ ...prev, [key]: val }))}
            />
          </div>
        ) : viewMode === 'prompts' ? (
          <div className="chat-window">
            <PromptsPanel />
          </div>
        ) : viewMode === 'memory' ? (
          <div className="chat-window">
            <MemoryPanel />
          </div>
        ) : viewMode === 'voice' ? (
          <div className="chat-window">
            <VoiceMode socket={socket} isActive={true} onClose={() => setViewMode('chat')} />
          </div>
        ) : (
          <ChatPanel messages={messages} onSendMessage={handleSendMessage} />
        )}
      </div>

      <VideoFeed
        viewMode={viewMode}
        onToggleView={toggleViewMode}
        onTogglePrompts={() => setViewMode(viewMode === 'prompts' ? 'chat' : 'prompts')}
        onToggleVoice={() => setViewMode(viewMode === 'voice' ? 'chat' : 'voice')}
        onToggleMemory={() => setViewMode(viewMode === 'memory' ? 'chat' : 'memory')}
        models={models}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        isMuted={isMuted}
        onToggleMute={() => setIsMuted(!isMuted)}
        useLiveMode={useLiveMode}
        onToggleLiveMode={setUseLiveMode}
        addLog={addLog}
      />
    </div>
  );
}

export default App;