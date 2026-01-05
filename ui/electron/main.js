const { app, BrowserWindow, dialog, shell } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');

let mgrProc = null;

function checkPrereqs() {
  // Verify system prerequisites: node and python must be available on PATH
  try {
    execSync('node -v', { stdio: 'ignore' });
  } catch (e) {
    const resp = dialog.showMessageBoxSync({
      type: 'error',
      title: 'Prerequisite missing: Node.js',
      message: 'Node.js (and npm) was not found on your system PATH. Electron UI requires Node.js to run bundled front-ends and tools.',
      detail: 'Install Node.js LTS from https://nodejs.org/ and restart AuraNexus. Click "Open website" to open the download page.',
      buttons: ['Open website', 'OK']
    });
    if (resp === 0) shell.openExternal('https://nodejs.org/en/');
    return false;
  }

  try {
    execSync('python --version', { stdio: 'ignore' });
  } catch (e) {
    const resp = dialog.showMessageBoxSync({
      type: 'error',
      title: 'Prerequisite missing: Python',
      message: 'Python was not found on your system PATH. AuraNexus needs Python to run the launcher and backend scripts.',
      detail: 'Install Python 3.8+ from https://www.python.org/downloads/ and enable adding Python to PATH. Click "Open website" to open the download page.',
      buttons: ['Open website', 'OK']
    });
    if (resp === 0) shell.openExternal('https://www.python.org/downloads/');
    return false;
  }

  return true;
}

function startLauncher() {
  const script = path.join(__dirname, '..', '..', 'app', 'aura_launcher.py');
  mgrProc = spawn('python', [script, 'start-all'], { windowsHide: true });
  mgrProc.stdout.on('data', (d) => console.log('[launcher]', d.toString()));
  mgrProc.stderr.on('data', (d) => console.error('[launcher-err]', d.toString()));
}

function stopLauncher() {
  try {
    const script = path.join(__dirname, '..', '..', 'app', 'aura_launcher.py');
    // Ask the launcher to stop all services gracefully
    const stop = spawn('python', [script, 'stop-all'], { windowsHide: true });
    stop.stdout.on('data', (d) => console.log('[launcher-stop]', d.toString()));
    stop.stderr.on('data', (d) => console.error('[launcher-stop-err]', d.toString()));
    stop.on('close', (code) => {
      console.log('[launcher-stop] exited', code);
      // ensure the original mgrProc is killed if still running
      if (mgrProc) {
        try { mgrProc.kill(); } catch (e) { }
      }
    });
  }
  catch (e) {
    console.error('Error while stopping launcher:', e);
    if (mgrProc) {
      try { mgrProc.kill(); } catch (e) { }
    }
  }
}

async function tryLoadUrl(win, url, attempts = 30, delayMs = 500) {
  for (let i = 0; i < attempts; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(url, res => {
          res.destroy();
          resolve();
        });
        req.on('error', reject);
        req.setTimeout(2000, () => { req.destroy(); reject(new Error('timeout')); });
      });
      return true;
    } catch (e) {
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
  return false;
}

async function createWindow () {
  const win = new BrowserWindow({ width: 1200, height: 800, webPreferences: { nodeIntegration: false }});
  const frontendUrl = 'http://127.0.0.1:3000';
  const loaded = await tryLoadUrl(win, frontendUrl);
  if (loaded) {
    win.loadURL(frontendUrl);
  } else {
    // fallback to bundled index
    win.loadFile(path.join(__dirname, 'index.html'));
  }
}

app.whenReady().then(() => {
  startLauncher();
  createWindow();
  app.on('activate', function () { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => {
  stopLauncher();
  if (process.platform !== 'darwin') app.quit();
});
