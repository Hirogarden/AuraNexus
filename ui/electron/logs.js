const API_BASE = 'http://127.0.0.1:8000';

const filesEl = document.getElementById('files');
const viewer = document.getElementById('viewer');
const refreshBtn = document.getElementById('refreshFiles');
const linesInput = document.getElementById('lines');
const autoEl = document.getElementById('autorefresh');

let currentFile = null;
let autoTimer = null;

async function listFiles() {
  try {
    const r = await fetch(`${API_BASE}/logs`);
    const files = await r.json();
    filesEl.innerHTML = '';
    files.forEach(f => {
      const b = document.createElement('button');
      b.textContent = f;
      b.style.display = 'block';
      b.style.width = '100%';
      b.onclick = () => { loadFile(f); };
      filesEl.appendChild(b);
    });
  } catch (e) {
    filesEl.innerText = 'Failed to load files: ' + e;
  }
}

async function loadFile(name) {
  currentFile = name;
  const lines = Number(linesInput.value) || 200;
  viewer.textContent = 'Loading...';
  try {
    const r = await fetch(`${API_BASE}/logs/${encodeURIComponent(name)}?lines=${lines}`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const txt = await r.text();
    viewer.textContent = txt;
    viewer.scrollTop = viewer.scrollHeight;
  } catch (e) {
    viewer.textContent = 'Failed to load log: ' + e;
  }
}

refreshBtn.onclick = () => listFiles();

function startAuto() {
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = setInterval(() => { if (currentFile) loadFile(currentFile); }, 5000);
}

autoEl.onchange = () => {
  if (autoEl.checked) startAuto(); else { clearInterval(autoTimer); autoTimer = null; }
};

// initial
listFiles();
