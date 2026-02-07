import React from 'react';

const SettingsPanel = ({ config, onSave, onChange }) => {
  // 1. Get all keys from the config object
  // 2. Filter out internal system variables that shouldn't be changed via UI
  const keys = Object.keys(config).filter(key =>
    !['DB_PATH', 'SERVICE_ACCOUNT_FILE', 'id'].includes(key)
  );

  // 3. Sort alphabetically for easy navigation
  keys.sort();

  return (
    <div className="settings-container">
      <h3 style={{ marginTop: 0, color: '#58a6ff' }}>System Configuration</h3>
      <div style={{ marginBottom: '15px', fontSize: '12px', color: '#8b949e' }}>
        All values stored in the database are displayed here.
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

        {/* Button to add new settings if needed in the future */}
        {keys.length === 0 && (
          <div style={{ color: '#ff4444', fontSize: '12px' }}>
            No settings found. Check that backend is running.
          </div>
        )}

        <button type="submit" className="btn-save">SAVE SETTINGS</button>
      </form>
    </div>
  );
};

export default SettingsPanel;