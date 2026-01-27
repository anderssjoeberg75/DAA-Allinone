import React, { useEffect, useRef, useState } from 'react';
import { Eye, Settings, Cpu, Volume2, VolumeX, Activity, FileText, Camera, CameraOff } from 'lucide-react'; 

const VideoFeed = ({ viewMode, onToggleView, onTogglePrompts, models, selectedModel, onModelChange, isMuted, onToggleMute, addLog }) => {
  const videoRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(true); // Håller koll på om kameran ska vara igång

  useEffect(() => {
    let activeStream = null;

    const manageCamera = async () => {
        // Om kameran är avstängd, stäng alla spår och rensa
        if (!cameraOn) {
            if (videoRef.current && videoRef.current.srcObject) {
                const tracks = videoRef.current.srcObject.getTracks();
                tracks.forEach(track => track.stop());
                videoRef.current.srcObject = null;
            }
            return;
        }

        // Om kameran ska vara på, starta den
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            activeStream = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) { 
            if(addLog) addLog(`[VIS] Camera Error: ${err.message}`); 
        }
    };

    manageCamera();

    // Städning när komponenten avmonteras eller kameran stängs av
    return () => {
        if (activeStream) {
            activeStream.getTracks().forEach(t => t.stop());
        }
    };
  }, [cameraOn, addLog]);

  return (
    <div className="panel" style={{ width: '320px' }}>
      <div className="panel-title">
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '10px' }}>
              
              {/* KAMERA ON/OFF */}
              <div 
                style={{ cursor: 'pointer', color: cameraOn ? '#58a6ff' : '#ff4444' }} 
                onClick={() => setCameraOn(!cameraOn)}
                title={cameraOn ? "Stäng av kamera" : "Sätt på kamera"}
              >
                  {cameraOn ? <Camera size={16} /> : <CameraOff size={16} />}
              </div>

              {/* TTS MUTE (Till vänster om pappret) */}
              <div 
                style={{ cursor: 'pointer', color: isMuted ? '#ff4444' : '#58a6ff' }} 
                onClick={onToggleMute}
                title={isMuted ? "Slå på ljud (TTS)" : "Muta ljud (TTS)"}
              >
                  {isMuted ? <VolumeX size={16}/> : <Volume2 size={16}/>}
              </div>

              {/* PROMPTS (Pappret) */}
              <div 
                style={{ cursor: 'pointer', color: viewMode === 'prompts' ? '#ff4444' : '#58a6ff' }} 
                onClick={onTogglePrompts}
                title="Redigera Prompts"
              >
                  <FileText size={16} />
              </div>

              {/* INSTÄLLNINGAR */}
              <div 
                style={{ cursor: 'pointer', color: viewMode === 'settings' ? '#ff4444' : '#58a6ff' }} 
                onClick={onToggleView}
                title="Inställningar"
              >
                  {viewMode === 'settings' ? <Activity size={16} /> : <Settings size={16} />}
              </div>
          </div>
      </div>
      
      <div className="video-container">
          {cameraOn ? (
              <video ref={videoRef} autoPlay playsInline muted className="video-element" />
          ) : (
              <div style={{color: '#30363d', fontSize: '12px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px'}}>
                  <CameraOff size={32} color="#30363d" />
                  <span>Kamera avstängd</span>
              </div>
          )}
      </div>

      <div className="controls-section">
          <div style={{display:'flex', flexDirection:'column', gap:'5px'}}>
              <div style={{color: '#c9d1d9', fontSize:'12px', display:'flex', alignItems:'center', gap:'5px'}}>
                <Cpu size={14}/> Text Chat Model:
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