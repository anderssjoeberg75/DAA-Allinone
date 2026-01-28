import React from 'react';
import { Mic, Power } from 'lucide-react';

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

export default Orb;