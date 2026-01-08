import requests
import json

# Try the exact format that worked in CLI
modelfile_content = 'FROM "C:/Users/hirog/OneDrive/Desktop/4. Models/Llama-3.1-8B-Lexi-Uncensored-V2-Q8_0.gguf"'

# Test both 'name' and 'model' field names
tests = [
    ("Using 'name' field", {"name": "testimport5", "modelfile": modelfile_content}),
    ("Using 'model' field", {"model": "testimport6", "modelfile": modelfile_content}),
    ("Using 'name' field + stream", {"name": "testimport7", "modelfile": modelfile_content, "stream": True}),
    ("Using 'model' field + stream", {"model": "testimport8", "modelfile": modelfile_content, "stream": True}),
]

for test_name, payload in tests:
    print(f"\n--- {test_name} ---")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    stream = payload.get("stream", False)
    resp = requests.post("http://localhost:11434/api/create", json=payload, stream=stream)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        print("✓ SUCCESS!")
        if stream:
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    if "status" in data:
                        print(f"  Status: {data['status']}")
                    if data.get("done"):
                        break
        else:
            print(f"Response: {resp.text}")
        break  # Stop on first success
    else:
        print(f"✗ Error: {resp.text}")

