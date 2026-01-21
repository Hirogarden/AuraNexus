"""Download and test with small model first"""
import sys
sys.path.insert(0, r"C:\Users\hirog\All-In-One\AuraNexus\electron-app.OLD\backend")

import llm_manager

print("=" * 70)
print("STEP 1: Downloading small test model (~350MB)")
print("=" * 70)

model_path = llm_manager.download_starter_model()

if model_path:
    print("\n" + "=" * 70)
    print(f"STEP 2: Loading model from {model_path}")
    print("=" * 70)
    
    success = llm_manager.load_model(model_path, n_ctx=2048, n_gpu_layers=20)
    
    if success:
        print("\n" + "=" * 70)
        print("STEP 3: Testing generation")
        print("=" * 70)
        
        response = llm_manager.generate("Hello! Please introduce yourself briefly.", max_tokens=100)
        print(f"\n[MODEL RESPONSE]:\n{response}\n")
        
        print("=" * 70)
        print("✅ SUCCESS! Small model works!")
        print("Now you can start llm_server.py to use it in the app")
        print("=" * 70)
    else:
        print("\n❌ Failed to load model")
else:
    print("\n❌ Failed to download model")
