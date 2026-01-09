const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile('index.html');
  mainWindow.webContents.openDevTools(); // Remove in production
}

function startPythonBackend() {
  // Start Python FastAPI server
  const pythonPath = path.join(__dirname, 'resources', 'python', 'core_app.exe');
  
  // Check if backend exists
  const fs = require('fs');
  if (!fs.existsSync(pythonPath)) {
    console.log('Python backend not found (will be created later)');
    return;
  }

  try {
    pythonProcess = spawn(pythonPath, ['--port', '8000']);

    pythonProcess.stdout.on('data', (data) => {
      console.log(`Python: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`Python Error: ${data}`);
    });
  } catch (error) {
    console.error('Failed to start Python backend:', error);
  }
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow(); // Start immediately, don't wait for backend
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});
