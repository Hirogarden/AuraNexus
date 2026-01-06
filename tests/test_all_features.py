"""Test all Ollama features - comprehensive test suite."""

import sys
import os
import base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ollama_client import OllamaClient, Message


def test_generate():
    """Test /api/generate endpoint for text generation."""
    print("\n" + "=" * 60)
    print("TEST 1: Generate Endpoint (Text Completion)")
    print("=" * 60)
    
    client = OllamaClient()
    
    # Simple text generation
    print("\n1. Simple generation:")
    result = client.generate("Write a haiku about coding")
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        print(f"  ✓ Response: {result['response'][:100]}...")
        print(f"  ✓ Tokens: {result.get('eval_count', 0)}")
    
    # Code completion with suffix
    print("\n2. Code completion (fill-in-the-middle):")
    result = client.generate(
        prompt="def calculate_fibonacci(n):",
        suffix="    return result",
        system="You are a code completion assistant",
        model="llama3.2"
    )
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        response = result.get('response', '')
        print(f"  ✓ Completed code:\n{response}")


def test_vision():
    """Test vision/multimodal support."""
    print("\n" + "=" * 60)
    print("TEST 2: Vision Support (Multimodal)")
    print("=" * 60)
    
    client = OllamaClient()
    
    # Check if llava is available
    models = client.list_models()
    if not any('llava' in m.lower() for m in models):
        print("  ⚠️  Skipping: llava model not installed")
        print("  Install with: ollama pull llava")
        return
    
    # Create a simple test image (red square, base64 PNG)
    # This is a tiny 2x2 red PNG
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEklEQVR42mP8z8DwHw" \
                "YMEwMABBMCAQegQnwAAAAASUVORK5CYII="
    
    print("\n1. Describe image:")
    result = client.generate(
        prompt="What do you see in this image?",
        images=[test_image],
        model="llava"
    )
    if "error" in result:
        print(f"  ❌ Error: {result['error']}")
    else:
        print(f"  ✓ Response: {result['response'][:150]}...")


def test_model_management():
    """Test model copy and version check."""
    print("\n" + "=" * 60)
    print("TEST 3: Model Management")
    print("=" * 60)
    
    client = OllamaClient()
    
    # Get version
    print("\n1. Ollama version:")
    version = client.get_version()
    if version:
        print(f"  ✓ Version: {version}")
    else:
        print("  ❌ Could not retrieve version")
    
    # Copy model
    print("\n2. Copy model:")
    models = client.list_models()
    if models:
        source = models[0]
        dest = f"{source.split(':')[0]}-test-copy:latest"
        
        print(f"  Copying {source} → {dest}")
        success = client.copy_model(source, dest)
        if success:
            print("  ✓ Model copied successfully")
            
            # Verify
            updated_models = client.list_models()
            if dest in updated_models:
                print(f"  ✓ Verified: {dest} exists")
                
                # Clean up
                print("  Cleaning up test copy...")
                client.delete_model(dest)
            else:
                print(f"  ⚠️  Copy succeeded but {dest} not in list")
        else:
            print("  ❌ Failed to copy model")
    else:
        print("  ⚠️  No models available to copy")


def test_streaming_generate():
    """Test streaming generation."""
    print("\n" + "=" * 60)
    print("TEST 4: Streaming Generation")
    print("=" * 60)
    
    client = OllamaClient()
    
    print("\n1. Stream text generation:")
    print("  Response: ", end="", flush=True)
    
    tokens = 0
    for chunk in client.generate_stream("Count from 1 to 5 slowly", 
                                       options={"num_predict": 50}):
        if "error" in chunk:
            print(f"\n  ❌ Error: {chunk['error']}")
            break
        
        response = chunk.get("response", "")
        if response:
            print(response, end="", flush=True)
            tokens += 1
        
        if chunk.get("done"):
            print(f"\n  ✓ Streamed {tokens} chunks")
            break


def test_all_endpoints():
    """Test comprehensive API coverage."""
    print("\n" + "=" * 60)
    print("TEST 5: API Coverage Check")
    print("=" * 60)
    
    client = OllamaClient()
    
    endpoints = {
        "chat": hasattr(client, 'chat'),
        "chat_stream": hasattr(client, 'chat_stream'),
        "generate": hasattr(client, 'generate'),
        "generate_stream": hasattr(client, 'generate_stream'),
        "embed": hasattr(client, 'embed'),
        "list_models": hasattr(client, 'list_models'),
        "pull_model": hasattr(client, 'pull_model'),
        "delete_model": hasattr(client, 'delete_model'),
        "show_model": hasattr(client, 'show_model'),
        "copy_model": hasattr(client, 'copy_model'),
        "create_from_modelfile": hasattr(client, 'create_from_modelfile'),
        "list_running_models": hasattr(client, 'list_running_models'),
        "unload_model": hasattr(client, 'unload_model'),
        "get_version": hasattr(client, 'get_version'),
    }
    
    implemented = sum(endpoints.values())
    total = len(endpoints)
    
    print(f"\nImplemented endpoints: {implemented}/{total}")
    print("\nEndpoint Status:")
    for name, exists in sorted(endpoints.items()):
        status = "✓" if exists else "✗"
        print(f"  {status} {name}")
    
    print(f"\nCoverage: {implemented/total*100:.1f}%")


if __name__ == "__main__":
    print("=" * 60)
    print("OLLAMA CLIENT - COMPREHENSIVE FEATURE TEST")
    print("=" * 60)
    
    try:
        test_generate()
        test_vision()
        test_model_management()
        test_streaming_generate()
        test_all_endpoints()
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETE!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
