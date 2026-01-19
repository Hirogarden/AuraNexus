"""
Test the auto-download functionality for starter model
"""
import sys
sys.path.insert(0, 'backend')

from backend import llm_manager

print("🧪 Testing auto-download of starter model...")
print("This will download ~350MB if model doesn't exist")
print()

success = llm_manager.auto_load_model()

if success:
    print("\n✅ SUCCESS! Model loaded and ready")
    print(f"Model: {llm_manager._model_path}")
    print("\nTesting generation...")
    
    response = llm_manager.generate(
        "Hello! Tell me a very short story about a robot.",
        max_tokens=50
    )
    
    print(f"\nGenerated: {response}")
else:
    print("\n❌ Failed to load model")
    print("Check logs above for details")
