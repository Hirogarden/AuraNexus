"""Test model loading to see exact error"""
import sys
sys.path.insert(0, r"C:\Users\hirog\All-In-One\AuraNexus\electron-app.OLD\backend")

import llm_manager

print("=" * 60)
print("[TEST] Attempting to load model...")
print("=" * 60)

model_path = r"C:\Users\hirog\OneDrive\Desktop\4. Models\Llama-3.1-8B-Lexi-Uncensored-V2-Q8_0.gguf"
success = llm_manager.load_model(model_path, n_ctx=4096, n_gpu_layers=33)

print("=" * 60)
if success:
    print("[RESULT] SUCCESS - Model loaded!")
    # Try generating something
    response = llm_manager.generate("Hello!", max_tokens=50)
    print(f"[TEST GENERATION] {response[:100]}...")
else:
    print("[RESULT] FAILED - Model did not load")
print("=" * 60)
