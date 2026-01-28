import React from 'react';

const SettingsPanel = ({ config, onSave, onChange }) => {
  // 1. Hämta alla nycklar som finns i config-objektet
  // 2. Filtrera bort interna systemvariabler som inte ska ändras via UI
  const keys = Object.keys(config).filter(key => 
    !['DB_PATH', 'SERVICE_ACCOUNT_FILE', 'id'].includes(key)
  );

  // 3. Sortera i bokstavsordning så det blir lätt att hitta
  keys.sort();

  return (
    <div className="settings-container">
      <h3 style={{ marginTop: 0, color: '#58a6ff' }}>System Configuration</h3>
      <div style={{ marginBottom: '15px', fontSize: '12px', color: '#8b949e' }}>
        Här visas alla värden som finns lagrade i databasen.
      </div>
      
      <form onSubmit={onSave}>
        {keys.map(key => (
          <div key={key} className="settings-group">
            <label className="settings-label">{key}</label>
            <input 
              type="text" 
              className="settings-input"
              value={config[key] || ''} 
              onChange={(e) => onChange(key, e.target.value)} 
            />
          </div>
        ))}
        
        {/* Knapp för att lägga till en helt ny inställning om det behövs framöver */}
        {keys.length === 0 && (
            <div style={{color: '#ff4444', fontSize: '12px'}}>
                Inga inställningar hittades. Kontrollera att backend körs.
            </div>
        )}

        <button type="submit" className="btn-save">SPARA INSTÄLLNINGAR</button>
      </form>
    </div>
  );
};

export default SettingsPanel;