#!/usr/bin/env python3
"""
Diagnose Ollama connectivity and request issues.
This script helps identify why Ollama is returning a 500 error.
"""

import sys
import json
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure requests is available
try:
    import requests
except ImportError:
    print("[ERROR] requests module not found. Install it with: pip install --user requests")
    sys.exit(1)

OLLAMA_URL = "http://localhost:11434"

def check_ollama_health():
    """Check if Ollama is running and responsive."""
    print("[1] Checking Ollama service health...")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('models', [])
            print(f"    ✓ Ollama is running")
            print(f"    ✓ Available models: {len(models)}")
            for model in models:
                name = model.get('name', 'unknown')
                size = model.get('size', 0)
                modified = model.get('modified_at', 'unknown')
                print(f"      - {name} ({size} bytes, modified: {modified})")
            return True
        else:
            print(f"    ✗ Unexpected status code: {resp.status_code}")
            print(f"    Response: {resp.text[:500]}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"    ✗ Cannot connect to Ollama at {OLLAMA_URL}")
        print("       Ensure Ollama is running: ollama serve")
        return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def test_simple_chat(model: str = "llama3"):
    """Test a simple chat request."""
    print(f"\n[2] Testing chat with model '{model}'...")
    url = f"{OLLAMA_URL}/api/chat"
    
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "user", "content": "Say 'hello' in one word."}
        ]
    }
    
    print(f"    Sending request to {url}")
    print(f"    Payload: {json.dumps(payload, indent=2)}")
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        print(f"    Status: {resp.status_code}")
        print(f"    Response body (first 500 chars):\n{resp.text[:500]}")
        
        if resp.status_code == 200:
            data = resp.json()
            content = data.get('message', {}).get('content', '')
            print(f"    ✓ Chat succeeded: {content}")
            return True
        elif resp.status_code == 500:
            print(f"    ✗ Server error (500). Possible causes:")
            print(f"       - Model '{model}' is not loaded (pull it: ollama pull {model})")
            print(f"       - Ollama ran out of memory")
            print(f"       - Malformed request payload")
            return False
        elif resp.status_code == 404:
            print(f"    ✗ Model not found (404). Available models:")
            try:
                models_resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
                if models_resp.status_code == 200:
                    models = models_resp.json().get('models', [])
                    for m in models:
                        print(f"       - {m.get('name', 'unknown')}")
            except Exception:
                pass
            return False
        else:
            print(f"    ✗ Unexpected status: {resp.status_code}")
            return False
    except requests.exceptions.Timeout:
        print(f"    ✗ Request timeout (model may be unresponsive or generating too long)")
        return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def test_with_system_prompt(model: str = "llama3"):
    """Test chat with a system prompt (as used by AuraNexus)."""
    print(f"\n[3] Testing chat with system prompt...")
    url = f"{OLLAMA_URL}/api/chat"
    
    system_prompt = "You are a helpful assistant."
    
    payload = {
        "model": model,
        "stream": False,
        "system": system_prompt,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Hello, how are you?"}
        ]
    }
    
    print(f"    Payload: {json.dumps(payload, indent=2)}")
    
    try:
        resp = requests.post(url, json=payload, timeout=15)
        print(f"    Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            content = data.get('message', {}).get('content', '')
            print(f"    ✓ Chat with system prompt succeeded")
            print(f"    Response: {content[:200]}...")
            return True
        else:
            print(f"    ✗ Error {resp.status_code}: {resp.text[:500]}")
            return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def check_logs():
    """Check if AuraNexus logs exist."""
    print(f"\n[4] Checking AuraNexus logs...")
    log_file = os.path.join(os.path.dirname(__file__), "..", "logs", "ollama_requests.log")
    
    if os.path.exists(log_file):
        print(f"    Found log file: {log_file}")
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"    Last 20 entries:")
                for line in lines[-20:]:
                    print(f"      {line.rstrip()}")
        except Exception as e:
            print(f"    Error reading log: {e}")
    else:
        print(f"    No log file found at {log_file}")
        print(f"    (Logs are created on first request)")


def main():
    print("=" * 60)
    print("Ollama Diagnostic Tool")
    print("=" * 60)
    
    # Step 1: Check health
    if not check_ollama_health():
        print("\n[FAIL] Ollama is not running or not accessible.")
        print("To fix: Start Ollama with 'ollama serve'")
        return
    
    # Step 2: Find first available model to test
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            if models:
                test_model = models[0].get('name', 'llama3')
            else:
                test_model = 'llama3'
                print(f"\n[WARNING] No models found. Using default: {test_model}")
        else:
            test_model = 'llama3'
    except Exception:
        test_model = 'llama3'
    
    # Step 3: Test simple chat
    test_simple_chat(test_model)
    
    # Step 4: Test with system prompt
    test_with_system_prompt(test_model)
    
    # Step 5: Check logs
    check_logs()
    
    print("\n" + "=" * 60)
    print("Diagnostic complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
