#!/usr/bin/env python3
"""AuraNexus service manager."""

Usage:
  python aura_launcher.py start-all
  python aura_launcher.py stop-all
  python aura_launcher.py status
"""
import subprocess
import sys
import signal
from pathlib import Path
from time import sleep
import os
try:
    import yaml
except Exception:
    yaml = None
import shutil

BASE = Path(__file__).resolve().parent.parent

# Load services from config if available, otherwise fall back to embedded defaults
CFG_PATH = BASE / "app" / "config" / "config.yaml"
def _default_services():
    return {
        "koboldcpp": {"cmd": [sys.executable, "koboldcpp_stub.py"], "cwd": BASE / "app"},
        "sillytavern": {"cmd": ["node", "server.js"], "cwd": BASE / "frontends" / "sillytavern"},
        "anything": {"cmd": ["node", "server.js"], "cwd": BASE / "data-manager" / "anything-llm"},
        "aura_api": {"cmd": [sys.executable, "-m", "uvicorn", "aura_api.app:app", "--host", "127.0.0.1", "--port", "8080"], "cwd": BASE / "app"},
    }

def load_services_from_config():
    if not CFG_PATH.exists() or yaml is None:
        return _default_services()
    cfg = None
    with open(CFG_PATH, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    services = {}
    for name, entry in (cfg.get('services') or {}).items():
        raw_cmd = entry.get('cmd', [])
        if isinstance(raw_cmd, str):
            cmd = raw_cmd.split()
        else:
            cmd = list(raw_cmd)
        cwd_raw = entry.get('cwd')
        if cwd_raw:
            cwd = (BASE / cwd_raw).resolve()
        else:
            cwd = BASE
        services[name] = {"cmd": cmd, "cwd": cwd}
    # Ensure aura_api present
    if 'aura_api' not in services:
        services['aura_api'] = _default_services()['aura_api']
    return services

SERVICES = load_services_from_config()

procs = {}

def start(name):
    cfg = SERVICES.get(name)
    if not cfg:
        print(f"Unknown service: {name}")
        return
    if name in procs and procs[name].poll() is None:
        print(f"{name} already running (pid={procs[name].pid})")
        return
    cwd = Path(cfg.get("cwd")) if cfg.get("cwd") else BASE
    if not cwd.exists():
        print(f"Skipping {name}: working directory does not exist ({cwd}).")
        print("  Hint: initialize submodules or update app/config/config.yaml to point to installed locations.")
        return
    try:
        print(f"Starting {name}...")
        p = subprocess.Popen(cfg["cmd"], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        procs[name] = p
        sleep(0.4)
        print(f"Started {name} pid={p.pid}")
    except Exception as e:
        print(f"Failed to start {name}: {e}")


def stop(name):
    p = procs.get(name)
    if not p:
        print(f"{name} not running")
        return
    if p.poll() is None:
        print(f"Stopping {name} (pid={p.pid})...")
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    print(f"Stopped {name}")
    procs.pop(name, None)


def status():
    for name, cfg in SERVICES.items():
        p = procs.get(name)
        s = 'stopped' if not p else ('running' if p.poll() is None else 'exited')
        pid = p.pid if p and p.poll() is None else '-' 
        print(f"{name}: {s} pid={pid}")


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'start-all'
    if cmd == 'start-all':
        for n in SERVICES:
            start(n)
        print('All start commands issued')
        try:
            print('Launcher running; press Ctrl-C to stop all services')
            while True:
                sleep(1)
        except KeyboardInterrupt:
            print('\nKeyboard interrupt received — stopping services...')
            # Stop any running services
            for name in list(procs.keys()):
                try:
                    stop(name)
                except Exception:
                    pass
            print('All services stopped')
    elif cmd == 'stop-all':
        #!/usr/bin/env python3
        """AuraNexus service manager (config-driven).

        Commands:
          python aura_launcher.py start-all
          python aura_launcher.py stop-all
          python aura_launcher.py restart-all
          python aura_launcher.py status

        Reads `app/config/config.yaml` for service commands and working directories.
        """
        import subprocess
        import sys
        from pathlib import Path
        from time import sleep
        import yaml
        import os

        BASE = Path(__file__).resolve().parent.parent
        CFG_PATH = BASE / "app" / "config" / "config.yaml"
        LOGDIR = BASE / "app" / "logs"
        LOGDIR.mkdir(parents=True, exist_ok=True)


        def load_config():
            if not CFG_PATH.exists():
                raise FileNotFoundError(f"Config not found: {CFG_PATH}")
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)


        cfg = load_config()
        SERVICES_CFG = cfg.get("services", {})

        # process store
        procs = {}


        def make_cmd_list(entry):
            # entry may be list or space-joined string
            if isinstance(entry, list):
                return entry
            if isinstance(entry, str):
                return entry.split()
            return []


        def start_service(name):
            service = SERVICES_CFG.get(name)
            if not service:
                print(f"Service not defined in config: {name}")
                return
            if name in procs and procs[name].poll() is None:
                print(f"{name} already running (pid={procs[name].pid})")
                return
            cmd = make_cmd_list(service.get("cmd", []))
            cwd = service.get("cwd")
            if cwd:
                cwd_path = (BASE / cwd).resolve()
            else:
                cwd_path = BASE
            # quick checks: ensure executable exists or script file is present
            if cmd:
                exe = cmd[0]
                # if exe looks like python script (endswith .py) check file exists in cwd
                if exe.lower().endswith('.py'):
                    script_path = (cwd_path / exe).resolve()
                    if not script_path.exists():
                        print(f"Skipping {name}: script not found: {script_path}")
                        return
                else:
                    # check executable on PATH
                    if not shutil.which(exe):
                        print(f"Skipping {name}: executable not found on PATH: {exe}")
                        return
            stdout_log = open(LOGDIR / f"{name}.out.log", "ab")
            stderr_log = open(LOGDIR / f"{name}.err.log", "ab")
            try:
                if not cwd_path.exists():
                    print(f"Skipping {name}: cwd not found ({cwd_path}) - not starting")
                    return
                print(f"Starting {name} with cwd={cwd_path} cmd={cmd}")
                # Use shell=False; cmd must be list
                p = subprocess.Popen(cmd, cwd=str(cwd_path), stdout=stdout_log, stderr=stderr_log, env=os.environ.copy())
                procs[name] = p
                sleep(0.2)
                print(f"Started {name} pid={p.pid}")
            except Exception as e:
                print(f"Failed to start {name}: {e}")


        def stop_service(name):
            p = procs.get(name)
            if not p:
                print(f"{name} not running")
                return
            if p.poll() is None:
                print(f"Stopping {name} (pid={p.pid})...")
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
            print(f"Stopped {name}")
            procs.pop(name, None)


        def status():
            for name in SERVICES_CFG.keys():
                p = procs.get(name)
                s = 'stopped' if not p else ('running' if p.poll() is None else 'exited')
                pid = p.pid if p and p.poll() is None else '-'
                print(f"{name}: {s} pid={pid}")


        def start_all():
            for name in SERVICES_CFG.keys():
                start_service(name)


        def stop_all():
            for name in list(procs.keys()):
                stop_service(name)


        if __name__ == '__main__':
            cmd = sys.argv[1] if len(sys.argv) > 1 else 'start-all'
            if cmd == 'start-all' or cmd == 'start_all':
                start_all()
                print('All start commands issued')
            elif cmd == 'stop-all' or cmd == 'stop_all':
                stop_all()
                print('All stop commands issued')
            elif cmd == 'restart-all' or cmd == 'restart_all':
                stop_all()
                start_all()
                print('Restarted all services')
            elif cmd == 'status':
                status()
            else:
                # allow controlling single service: start <name>, stop <name>
                if cmd == 'start' and len(sys.argv) > 2:
                    start_service(sys.argv[2])
                elif cmd == 'stop' and len(sys.argv) > 2:
                    stop_service(sys.argv[2])
                else:
                    print('Unknown command', cmd)
