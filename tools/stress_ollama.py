#!/usr/bin/env python3
"""Stress test Ollama by firing multiple concurrent chat requests with large payloads.
"""
import requests, json, threading, os
OLLAMA = "http://localhost:11434"
LOG = os.path.join(os.path.dirname(__file__), "ollama_stress.log")

def send(i):
    memory = "Memory: " + ("lorem ipsum " * 2000)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "assistant", "content": memory},
        {"role": "user", "content": "Summarize the user's preferences in one paragraph."}
    ]
    payload = {"model": "llama3:latest", "stream": False, "messages": messages}
    try:
        r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=30)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{i}] Status: {r.status_code}\n")
            f.write(f"[{i}] Body: {r.text[:2000]}\n")
        print(f"[{i}] {r.status_code}")
    except Exception as e:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{i}] Exception: {e}\n")
        print(f"[{i}] Exception: {e}")

threads = []
for i in range(8):
    t = threading.Thread(target=send, args=(i,), daemon=True)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print('Stress test complete. Log:', LOG)
