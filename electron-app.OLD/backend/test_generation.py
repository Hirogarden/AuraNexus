"""
Test model generation
"""
import sys
sys.path.insert(0, r'C:\Users\hirog\All-In-One\AuraNexus\electron-app.OLD\backend')

from llm_manager import generate, get_llm_instance

# Check if model is loaded
if get_llm_instance() is None:
    print("❌ No model loaded. Run init_model.py first!")
    sys.exit(1)

print("✅ Model is loaded")
print("\n🧪 Testing generation...")
print("-" * 50)

# Test prompt
response = generate(
    prompt="You are a helpful AI assistant. User: Hello! How are you?\n\nAssistant:",
    max_tokens=100,
    temperature=0.7,
    top_p=0.95
)

if response:
    print(f"Response: {response}")
    print("-" * 50)
    print("✅ Model is working correctly!")
else:
    print("❌ No response generated")
