"""
Initialize AuraNexus with user's model
"""
import sys
sys.path.insert(0, r'C:\Users\hirog\All-In-One\AuraNexus\electron-app.OLD\backend')

from llm_manager import load_model

# User's model path
MODEL_PATH = r"C:\Users\hirog\OneDrive\Desktop\4. Models\Llama-3.1-8B-Lexi-Uncensored-V2-Q8_0.gguf"

print("🔄 Loading Llama 3.1 8B model...")
print(f"📍 Path: {MODEL_PATH}")

success = load_model(
    model_path=MODEL_PATH,
    n_ctx=4096,  # 4K context window
    n_gpu_layers=33,  # Offload layers to GPU (auto-detect available)
    n_batch=512,
    verbose=False
)

if success:
    print("✅ Model loaded successfully!")
    print("✅ AuraNexus is ready to use")
else:
    print("❌ Failed to load model")
    sys.exit(1)
