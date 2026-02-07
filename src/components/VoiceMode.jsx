import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Phone, PhoneOff } from 'lucide-react';

export function VoiceMode({ socket, isActive, onClose }) {
    const [isConnected, setIsConnected] = useState(false);
    const [status, setStatus] = useState('Disconnected');
    const [aiTranscript, setAiTranscript] = useState('');
    const [error, setError] = useState(null);
    const transcriptRef = useRef(null);

    useEffect(() => {
        if (!socket || !isActive) return;

        // Listen for voice events
        socket.on('voice_started', () => {
            setIsConnected(true);
            setStatus('Connected');
            setError(null);
        });

        socket.on('voice_stopped', () => {
            setIsConnected(false);
            setStatus('Disconnected');
        });

        socket.on('voice_status', (data) => {
            setStatus(data.status || 'Active');
        });

        socket.on('ai_transcription', (data) => {
            setAiTranscript(prev => prev + (data.text || ''));
        });

        socket.on('voice_turn_complete', () => {
            // AI finished speaking - could add visual indicator here
            console.log('[VOICE] AI turn complete');
        });

        socket.on('voice_error', (data) => {
            setError(data.error);
            setStatus('Error');
            console.error('[VOICE ERROR]', data.error);
        });

        // Start voice mode
        socket.emit('start_voice_mode');

        // Cleanup
        return () => {
            socket.off('voice_started');
            socket.off('voice_stopped');
            socket.off('voice_status');
            socket.off('ai_transcription');
            socket.off('voice_turn_complete');
            socket.off('voice_error');

            if (isConnected) {
                socket.emit('stop_voice_mode');
            }
        };
    }, [socket, isActive]);

    // Auto-scroll transcript
    useEffect(() => {
        if (transcriptRef.current) {
            transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
        }
    }, [aiTranscript]);

    const handleStop = () => {
        if (socket) {
            socket.emit('stop_voice_mode');
        }
        onClose();
    };

    const clearTranscript = () => {
        setAiTranscript('');
    };

    return (
        <div className="voice-mode-container">
            {/* Header */}
            <div className="voice-header">
                <div className="voice-status">
                    <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></div>
                    <span className="status-text">{status}</span>
                </div>
                <button onClick={handleStop} className="stop-button" title="Stop Voice Mode">
                    <PhoneOff size={20} />
                </button>
            </div>

            {/* Microphone Indicator */}
            <div className="mic-indicator">
                {isConnected ? (
                    <div className="mic-active">
                        <Mic size={48} className="mic-icon pulsing" />
                        <p>Listening...</p>
                    </div>
                ) : (
                    <div className="mic-inactive">
                        <MicOff size={48} className="mic-icon" />
                        <p>Not connected</p>
                    </div>
                )}
            </div>

            {/* Error Display */}
            {error && (
                <div className="voice-error">
                    <strong>Error:</strong> {error}
                </div>
            )}

            {/* Transcript */}
            <div className="transcript-container">
                <div className="transcript-header">
                    <h3>DAA Response</h3>
                    <button onClick={clearTranscript} className="clear-btn">Clear</button>
                </div>
                <div
                    ref={transcriptRef}
                    className="transcript-content"
                >
                    {aiTranscript || <span className="transcript-placeholder">DAA's responses will appear here...</span>}
                </div>
            </div>

            {/* Info */}
            <div className="voice-info">
                <p>💡 <strong>Tip:</strong> Speak naturally. All tools work in voice mode!</p>
            </div>
        </div>
    );
}

export default VoiceMode;
