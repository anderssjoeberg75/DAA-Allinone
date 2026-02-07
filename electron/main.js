const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let backendProcess = null;

// --- SETTINGS ---
const BACKEND_DIR = path.resolve(__dirname, '..', 'backend');
const BACKEND_PATH = path.join(BACKEND_DIR, 'server.py');
const FRONTEND_URL = 'http://localhost:5173';

function getPythonPath() {
  // Linux/Mac uses 'bin', Windows uses 'Scripts'
  const isWin = process.platform === 'win32';
  const binFolder = isWin ? 'Scripts' : 'bin';
  const exeName = isWin ? 'python.exe' : 'python';

  const venvPython = path.join(BACKEND_DIR, 'venv', binFolder, exeName);

  if (fs.existsSync(venvPython)) {
    console.log(`[Electron] Found venv Python: ${venvPython}`);
    return venvPython;
  }

  // Fallback
  console.log("[Electron] Warning: venv not found. Trying global python...");
  return isWin ? 'python' : 'python3';
}

function startBackend() {
  const pythonCmd = getPythonPath();
  console.log(`[Electron] Starting backend with: ${pythonCmd}`);
  console.log(`[Electron] File: ${BACKEND_PATH}`);

  // Start Python. 
  backendProcess = spawn(pythonCmd, [BACKEND_PATH], {
    windowsHide: true,
    stdio: 'pipe',
    cwd: BACKEND_DIR // Important: Set working directory to backend folder
  });

  // Log what the server says
  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend]: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error]: ${data}`);
  });

  backendProcess.on('close', (code) => {
    console.log(`[Backend] Process exited with code ${code}`);
  });

  backendProcess.on('error', (err) => {
    console.error(`[Electron] Failed to start Python: ${err.message}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      // --- SECURITY FIX START ---
      nodeIntegration: false,      // Prevent React from using require() and OS calls
      contextIsolation: true,      // Protect memory (Sandbox)
      enableRemoteModule: false,   // Disable insecure remote module
      preload: path.join(__dirname, 'preload.js') // Load security bridge
      // --- SECURITY FIX END ---
    },
  });

  // Try to load frontend
  mainWindow.loadURL(FRONTEND_URL).catch((err) => {
    console.log("Frontend (Vite) doesn't seem to be running. Start it with 'npm run dev'.");
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.on('ready', () => {
  startBackend();
  createWindow();
});

// Clean up processes when closing window
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (backendProcess) {
    console.log("[Electron] Shutting down backend...");
    backendProcess.kill();
  }
});
