import React, { useEffect, useRef } from 'react';
import { Activity } from 'lucide-react';

const SystemLog = ({ logs }) => {
  const logEndRef = useRef(null);
  
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="panel" style={{ width: '300px' }}>
      <div className="panel-title"><Activity size={16}/> SYSTEM ACTIVITY</div>
      <div className="log-container">
          {logs.map((l, i) => <div key={i} className="log-entry">{l}</div>)}
          <div ref={logEndRef}/>
      </div>
    </div>
  );
};

export default SystemLog;