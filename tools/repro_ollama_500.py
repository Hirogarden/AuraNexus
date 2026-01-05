#!/usr/bin/env python3
"""Send a chat payload that simulates retrieval of AnythingLLM memory and capture response.
Writes a local log at tools/ollama_repro.log with full request/response for inspection.
"""
import json, os, sys
try:
    import requests
except ImportError:
    print("[ERROR] requests not installed. Run: pip install --user requests")
    sys.exit(1)

OLLAMA = "http://localhost:11434"
LOG = os.path.join(os.path.dirname(__file__), "ollama_repro.log")

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Simulated long memory content from AnythingLLM
memory_content = (
    "User memory: The user likes sci-fi books, often references Dune and Neal Stephenson. "
    "They prefer concise answers and to include bullet points when giving instructions. "
    "Recent notable details: visited Tokyo in 2024; working on a side project using PySide6. "
    "" * 200
)

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "assistant", "content": memory_content},
    {"role": "user", "content": "Summarize the user's preferences and give 3 suggestions for a reading list."}
]

payload = {"model": "llama3:latest", "stream": False, "system": "You are a helpful assistant.", "messages": messages}

print("Sending test payload to Ollama...")
log(f"REQUEST: {json.dumps(payload)[:2000]}")
try:
    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=30)
    print("Status:", r.status_code)
    text = r.text
    print("Response (first 1000 chars):\n", text[:1000])
    log(f"STATUS: {r.status_code}")
    log(f"RESPONSE: {text[:8000]}")
except Exception as e:
    print("Error while contacting Ollama:", e)
    log(f"EXCEPTION: {e}")

print("Done. Log file:", LOG)
