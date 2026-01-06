"""Test model import using different API approaches."""
import requests
import json
import sys
from pathlib import Path

def test_create_endpoint(file_path: str, model_name: str = "test-import:latest"):
    """Test the /api/create endpoint with different formats."""
    
    print(f"\n{'='*60}")
    print(f"Testing /api/create endpoint")
    print(f"File: {file_path}")
    print(f"Model: {model_name}")
    print(f"{'='*60}\n")
    
    base_url = "http://localhost:11434"
    modelfile_path = file_path.replace('\\', '/')
    
    # Test 1: Standard modelfile format
    print("\n--- Test 1: Modelfile with FROM (uppercase) ---")
    payload1 = {
        "name": model_name,
        "modelfile": f"FROM {modelfile_path}"
    }
    print(f"Payload: {json.dumps(payload1, indent=2)}")
    
    try:
        resp = requests.post(f"{base_url}/api/create", json=payload1, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}\n")
        if resp.status_code == 200:
            return True
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 2: Using 'from' field directly
    print("\n--- Test 2: Direct 'from' field ---")
    payload2 = {
        "name": model_name,
        "from": modelfile_path
    }
    print(f"Payload: {json.dumps(payload2, indent=2)}")
    
    try:
        resp = requests.post(f"{base_url}/api/create", json=payload2, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}\n")
        if resp.status_code == 200:
            return True
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 3: Using 'model' field
    print("\n--- Test 3: Using 'model' field ---")
    payload3 = {
        "model": model_name,
        "from": modelfile_path
    }
    print(f"Payload: {json.dumps(payload3, indent=2)}")
    
    try:
        resp = requests.post(f"{base_url}/api/create", json=payload3, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}\n")
        if resp.status_code == 200:
            return True
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 4: Using 'files' field
    print("\n--- Test 4: Using 'files' field ---")
    payload4 = {
        "model": model_name,
        "files": [modelfile_path]
    }
    print(f"Payload: {json.dumps(payload4, indent=2)}")
    
    try:
        resp = requests.post(f"{base_url}/api/create", json=payload4, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}\n")
        if resp.status_code == 200:
            return True
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 5: Modelfile without quotes
    print("\n--- Test 5: Modelfile FROM without path quotes ---")
    payload5 = {
        "model": model_name,
        "modelfile": f"FROM {modelfile_path}",
        "stream": True
    }
    print(f"Payload: {json.dumps(payload5, indent=2)}")
    
    try:
        resp = requests.post(f"{base_url}/api/create", json=payload5, stream=True, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Success! Streaming response:")
            for line in resp.iter_lines():
                if line:
                    print(f"  {line.decode('utf-8')}")
            return True
        else:
            print(f"Response: {resp.text}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        print("Usage: python test_model_import_v2.py <path_to_gguf>")
        sys.exit(1)
    
    if not Path(file_path).exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)
    
    success = test_create_endpoint(file_path)
    
    if success:
        print("\n" + "="*60)
        print("✓ SUCCESS! Found a working format.")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ All formats failed.")
        print("="*60)
