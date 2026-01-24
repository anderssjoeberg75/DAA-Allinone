const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let backendProcess = null;

// --- INSTÄLLNINGAR ---
const BACKEND_DIR = path.resolve(__dirname, '..', 'backend');
const BACKEND_PATH = path.join(BACKEND_DIR, 'server.py');
const FRONTEND_URL = 'http://localhost:5173'; 

function getPythonPath() {
  // 1. Försök hitta Python i den virtuella miljön (venv) som setup_windows.bat skapade
  // På Windows ligger den i backend/venv/Scripts/python.exe
  const venvPython = path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe');
  
  if (fs.existsSync(venvPython)) {
    console.log(`[Electron] Hittade venv Python: ${venvPython}`);
    return venvPython;
  }

  // 2. Fallback: Försök med global 'python' eller 'python3' om venv saknas
  console.log("[Electron] Varning: Hittade inte venv. Försöker med global python...");
  return process.platform === 'win32' ? 'python' : 'python3';
}

function startBackend() {
  const pythonCmd = getPythonPath();
  console.log(`[Electron] Startar backend med: ${pythonCmd}`);
  console.log(`[Electron] Fil: ${BACKEND_PATH}`);

  // Startar Python. 
  backendProcess = spawn(pythonCmd, [BACKEND_PATH], {
    windowsHide: true, 
    stdio: 'pipe',
    cwd: BACKEND_DIR // Viktigt: Sätt working directory till backend-mappen
  });

  // Logga vad servern säger
  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend]: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error]: ${data}`);
  });

  backendProcess.on('close', (code) => {
    console.log(`[Backend] Process avslutad med kod ${code}`);
  });
  
  backendProcess.on('error', (err) => {
    console.error(`[Electron] Misslyckades att starta Python: ${err.message}`);
    console.error(`[Electron] TIPS: Kör 'setup_windows.bat' för att skapa venv.`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  // Försök ladda frontend
  mainWindow.loadURL(FRONTEND_URL).catch((err) => {
    console.log("Frontend (Vite) verkar inte vara igång. Starta den med 'npm run dev'.");
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.on('ready', () => {
  startBackend();
  createWindow();
});

// Städa upp processer när man stänger fönstret
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (backendProcess) {
    console.log("[Electron] Stänger ner backend...");
    backendProcess.kill();
  }
});