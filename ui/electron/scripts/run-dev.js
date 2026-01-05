const { spawn } = require('child_process');
const path = require('path');

const repoRoot = path.join(__dirname, '..', '..');
const launcher = path.join(repoRoot, 'app', 'aura_launcher.py');

console.log('Starting launcher...');
const py = process.platform === 'win32' ? 'python' : 'python3';
const lproc = spawn(py, [launcher, 'start-all'], { cwd: repoRoot, stdio: 'inherit' });

console.log('Starting Electron...');
const eproc = spawn('npx', ['electron', '.'], { cwd: path.join(repoRoot, 'ui', 'electron'), stdio: 'inherit', shell: true });

function shutdown() {
  console.log('Shutting down dev processes...');
  try { lproc.kill(); } catch (e) {}
  try { eproc.kill(); } catch (e) {}
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
process.on('exit', shutdown);
