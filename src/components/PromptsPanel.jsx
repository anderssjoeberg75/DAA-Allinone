import React, { useEffect, useState } from 'react';

const PromptsPanel = () => {
  const [prompts, setPrompts] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/prompts')
      .then(res => res.json())
      .then(data => {
        setPrompts(data);
        setLoading(false);
      })
      .catch(err => console.error("Failed to load prompts", err));
  }, []);

  const handleSave = () => {
    fetch('http://localhost:8000/api/prompts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ prompts })
    }).then(() => alert("Prompter sparade! Starta om en ny konversation för att testa."));
  };

  const handleChange = (key, value) => {
    setPrompts(prev => ({...prev, [key]: value}));
  };

  if (loading) return <div style={{padding: 20}}>Laddar...</div>;

  return (
    <div className="settings-container">
      <h3 style={{ marginTop: 0, color: '#58a6ff' }}>AI Personlighet (Prompts)</h3>
      <div style={{ marginBottom: '15px', fontSize: '12px', color: '#8b949e' }}>
        Här styr du exakt hur DAA tänker och agerar.
      </div>
      
      {Object.keys(prompts).map(key => (
        <div key={key} className="settings-group">
          <label className="settings-label" style={{color: '#00ffcc'}}>{key}</label>
          <textarea 
            value={prompts[key]} 
            onChange={(e) => handleChange(key, e.target.value)} 
            style={{
                width: '100%', minHeight: '150px', 
                background: '#0d1117', border: '1px solid #30363d', 
                color: '#e0e6ed', padding: '10px', borderRadius: '4px',
                fontFamily: 'Consolas, monospace', fontSize: '12px'
            }}
          />
        </div>
      ))}

      <button onClick={handleSave} className="btn-save">SPARA ÄNDRINGAR</button>
    </div>
  );
};

export default PromptsPanel;