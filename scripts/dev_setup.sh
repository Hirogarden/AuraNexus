#!/usr/bin/env bash
# Cross-platform dev setup (macOS / Linux)
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$HERE"

echo "Running AuraNexus dev setup..."

echo "Checking prerequisites with ui/electron/scripts/check_prereqs.js"
node ui/electron/scripts/check_prereqs.js || { echo "Install missing prerequisites."; exit 2; }

echo "Setting up Python virtualenv..."
if [ ! -d app/.venv ]; then
  python3 -m venv app/.venv
fi

echo "Activating venv and installing Python requirements..."
source app/.venv/bin/activate
pip install -r app/requirements.txt

echo "Installing Electron UI dependencies..."
if [ -f ui/electron/package.json ]; then
  cd ui/electron
  node ./scripts/check_prereqs.js || { echo "Node prereq check failed."; exit 3; }
  npm install
else
  echo "ui/electron/package.json not found — skipping npm install"
fi

echo "Dev setup complete. To run the app:"
echo "  source app/.venv/bin/activate && python app/aura_launcher.py start-all" 
echo "  (then in another terminal) in ui/electron: npm run start"
