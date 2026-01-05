const { execSync } = require('child_process');

function ok(cmd) {
  try {
    execSync(cmd, { stdio: 'ignore' });
    return true;
  } catch (e) {
    return false;
  }
}

const checks = [
  { name: 'Node.js', ok: ok('node -v'), url: 'https://nodejs.org/en/' },
  { name: 'npm', ok: ok('npm -v'), url: 'https://nodejs.org/en/' },
  { name: 'Python', ok: ok('python --version') || ok('python3 --version'), url: 'https://www.python.org/downloads/' },
  { name: 'pip', ok: ok('pip --version') || ok('pip3 --version'), url: 'https://pip.pypa.io/en/stable/installation/' }
];

let okAll = true;
console.log('AuraNexus prerequisite check:');
for (const c of checks) {
  if (c.ok) {
    console.log(`  ✓ ${c.name}`);
  } else {
    console.error(`  ✗ ${c.name}  (see ${c.url})`);
    okAll = false;
  }
}

if (!okAll) {
  console.error('\nOne or more prerequisites are missing. Visit the URLs above to install them, then re-run setup.');
  process.exit(2);
}

console.log('\nAll prerequisites found.');
process.exit(0);
