"""Test launcher integration with upgraded OllamaClient."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_import():
    """Test that aura_nexus_app imports successfully."""
    print("Testing imports...")
    try:
        # This will test all the imports and class definitions
        from aura_nexus_app import OllamaClient, Message, AsyncOllamaClient
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_ollama_client_creation():
    """Test OllamaClient wrapper creation."""
    print("\nTesting OllamaClient creation...")
    try:
        from aura_nexus_app import OllamaClient
        client = OllamaClient()
        print(f"✓ OllamaClient created: base_url={client.base_url}, model={client.model}")
        print(f"✓ Has async client: {client._async_client is not None}")
        return True
    except Exception as e:
        print(f"✗ OllamaClient creation failed: {e}")
        return False

def test_async_health_check():
    """Test async health check functionality."""
    print("\nTesting async health check...")
    try:
        import asyncio
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from ollama_client import AsyncOllamaClient
        
        async def check():
            async with AsyncOllamaClient() as client:
                healthy = await client.health_check()
                if healthy:
                    version = await client.get_version()
                    models = await client.list_models()
                    return healthy, version, models
                return healthy, None, []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            healthy, version, models = loop.run_until_complete(check())
            if healthy:
                print(f"✓ Health check: HEALTHY")
                print(f"✓ Ollama version: {version}")
                print(f"✓ Available models: {len(models)}")
                for model in models[:3]:  # Show first 3
                    print(f"  - {model}")
            else:
                print("✗ Health check: OFFLINE")
            return healthy
        finally:
            loop.close()
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_message_compatibility():
    """Test Message class compatibility."""
    print("\nTesting Message compatibility...")
    try:
        from aura_nexus_app import Message
        from ollama_client import Message as OllamaMessage
        
        # Create app message
        app_msg = Message(role='user', content='Hello')
        print(f"✓ App Message: {app_msg.role}: {app_msg.content}")
        
        # Create ollama message
        ollama_msg = OllamaMessage(role='assistant', content='Hi there')
        print(f"✓ Ollama Message: {ollama_msg.role}: {ollama_msg.content}")
        
        return True
    except Exception as e:
        print(f"✗ Message test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("LAUNCHER INTEGRATION TESTS")
    print("=" * 60)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_import()))
    
    # Test 2: OllamaClient creation
    results.append(("OllamaClient Creation", test_ollama_client_creation()))
    
    # Test 3: Async health check
    results.append(("Async Health Check", test_async_health_check()))
    
    # Test 4: Message compatibility
    results.append(("Message Compatibility", test_message_compatibility()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Launcher integration successful!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
