"""Test memory management and embedding features."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ollama_client import OllamaClient


def test_embeddings():
    """Test the new /api/embed endpoint."""
    print("\n=== Testing Embeddings ===")
    client = OllamaClient()
    
    # Single text
    print("\n1. Single embedding:")
    result = client.embed("Hello world")
    if "error" in result:
        print(f"  Error: {result['error']}")
    else:
        embeddings = result.get("embeddings", [])
        if embeddings:
            print(f"  Model: {result.get('model')}")
            print(f"  Embedding dimensions: {len(embeddings[0])}")
            print(f"  First 5 values: {embeddings[0][:5]}")
    
    # Batch embeddings
    print("\n2. Batch embeddings:")
    texts = ["Hello world", "How are you?", "This is a test"]
    result = client.embed(texts)
    if "error" in result:
        print(f"  Error: {result['error']}")
    else:
        embeddings = result.get("embeddings", [])
        print(f"  Processed {len(embeddings)} texts")
        for i, text in enumerate(texts):
            print(f"  '{text}': {len(embeddings[i])} dimensions")


def test_memory_management():
    """Test model memory management."""
    print("\n\n=== Testing Memory Management ===")
    client = OllamaClient()
    
    # List running models
    print("\n1. Currently loaded models:")
    result = client.list_running_models()
    if "error" in result:
        print(f"  Error: {result['error']}")
    else:
        models = result.get("models", [])
        if not models:
            print("  No models loaded")
        else:
            for m in models:
                name = m.get("name", "Unknown")
                size = m.get("size", 0) / (1024 * 1024)  # Convert to MB
                vram = m.get("size_vram", 0) / (1024 * 1024)
                print(f"  • {name}")
                print(f"    RAM: {size:.1f} MB | VRAM: {vram:.1f} MB")
    
    # Test unload (if a model is loaded)
    if result.get("models"):
        model_name = result["models"][0]["name"]
        print(f"\n2. Unloading {model_name}...")
        if client.unload_model(model_name):
            print("  ✓ Successfully unloaded")
            
            # Check again
            result = client.list_running_models()
            remaining = len(result.get("models", []))
            print(f"  Models still loaded: {remaining}")
        else:
            print("  ✗ Failed to unload")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing New Ollama Features")
    print("=" * 60)
    
    test_embeddings()
    test_memory_management()
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)
