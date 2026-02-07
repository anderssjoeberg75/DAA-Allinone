import React, { useEffect, useRef, useState } from 'react';
import { Eye, Settings, Cpu, Volume2, VolumeX, Activity, FileText, Camera, CameraOff, Mic, Brain } from 'lucide-react';

const VideoFeed = ({ viewMode, onToggleView, onTogglePrompts, onToggleVoice, onToggleMemory, models, selectedModel, onModelChange, isMuted, onToggleMute, useLiveMode, onToggleLiveMode, addLog }) => {
    const videoRef = useRef(null);
    const [cameraOn, setCameraOn] = useState(true); // Tracks whether camera should be on

    useEffect(() => {
        let activeStream = null;

        const manageCamera = async () => {
            // If camera is off, stop all tracks and clear
            if (!cameraOn) {
                if (videoRef.current && videoRef.current.srcObject) {
                    const tracks = videoRef.current.srcObject.getTracks();
                    tracks.forEach(track => track.stop());
                    videoRef.current.srcObject = null;
                }
                return;
            }

            // If camera should be on, start it
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                activeStream = stream;
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
            } catch (err) {
                if (addLog) addLog(`[VIS] Camera Error: ${err.message}`);
            }
        };

        manageCamera();

        // Cleanup when component unmounts or camera is turned off
        return () => {
            if (activeStream) {
                activeStream.getTracks().forEach(t => t.stop());
            }
        };
    }, [cameraOn, addLog]);

    return (
        <div className="panel" style={{ width: '320px' }}>
            <div className="panel-title">
                <span>Video Feed</span>
                <div className="panel-header-controls">

                    {/* CAMERA ON/OFF */}
                    <div
                        className={`control-icon ${cameraOn ? 'active' : 'inactive'}`}
                        onClick={() => setCameraOn(!cameraOn)}
                        title={cameraOn ? "Turn off camera" : "Turn on camera"}
                    >
                        {cameraOn ? <Camera size={16} /> : <CameraOff size={16} />}
                    </div>

                    {/* TTS MUTE (Left of the document icon) */}
                    <div
                        className={`control-icon ${isMuted ? 'inactive' : 'active'}`}
                        onClick={onToggleMute}
                        title={isMuted ? "Turn on audio (TTS)" : "Mute audio (TTS)"}
                    >
                        {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
                    </div>

                    {/* MEMORY EXPLORER (Brain Icon) */}
                    <div
                        className={`control-icon ${viewMode === 'memory' ? 'inactive' : 'active'}`}
                        style={{ color: viewMode === 'memory' ? '#A78BFA' : '#58a6ff' }}
                        onClick={onToggleMemory}
                        title="Memory Explorer"
                    >
                        <Brain size={16} />
                    </div>

                    {/* PROMPTS (Document) */}
                    <div
                        className={`control-icon ${viewMode === 'prompts' ? 'inactive' : 'active'}`}
                        style={{ color: viewMode === 'prompts' ? '#ff4444' : '#58a6ff' }}
                        onClick={onTogglePrompts}
                        title="Edit Prompts"
                    >
                        <FileText size={16} />
                    </div>

                    {/* VOICE MODE */}
                    <div
                        className={`control-icon ${viewMode === 'voice' ? 'active' : 'inactive'}`}
                        style={{ color: viewMode === 'voice' ? '#00ffcc' : '#c9d1d9' }}
                        onClick={onToggleVoice}
                        title="Voice Mode"
                    >
                        <Mic size={16} />
                    </div>

                    {/* SETTINGS */}
                    <div
                        className={`control-icon ${viewMode === 'settings' ? 'inactive' : 'active'}`}
                        style={{ color: viewMode === 'settings' ? '#ff4444' : '#58a6ff' }}
                        onClick={onToggleView}
                        title="Settings"
                    >
                        {viewMode === 'settings' ? <Activity size={16} /> : <Settings size={16} />}
                    </div>
                </div>
            </div>

            <div className="video-container">
                {cameraOn ? (
                    <video ref={videoRef} autoPlay playsInline muted className="video-element" />
                ) : (
                    <div className="camera-off-placeholder">
                        <CameraOff size={32} />
                        <span>Camera off</span>
                    </div>
                )}
            </div>

            <div className="controls-section">
                {/* LIVE MODE TOGGLE */}
                <div className="model-selector-group">
                    <div className="model-label">
                        <Activity size={14} /> Chat Mode:
                    </div>
                    <select
                        className="model-select"
                        value={useLiveMode ? 'live' : 'legacy'}
                        onChange={(e) => onToggleLiveMode(e.target.value === 'live')}
                        title={useLiveMode ? "Live: Direct audio from AI" : "Legacy: Text-based TTS"}
                    >
                        <option value="live">🚀 Live Mode (Fast)</option>
                        <option value="legacy">📝 Legacy Mode</option>
                    </select>
                </div>

                <div className="model-selector-group">
                    <div className="model-label">
                        <Cpu size={14} /> Text Chat Model:
                    </div>
                    <select className="model-select" value={selectedModel} onChange={(e) => onModelChange(e.target.value)}>
                        {models.map((m, i) => (<option key={i} value={m.id}>{m.name}</option>))}
                    </select>
                </div>
            </div>
        </div>
    );
};

export default VideoFeed;
