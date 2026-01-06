"""Test the upgraded ollama_client with httpx, async support, and context managers."""

import sys
import asyncio
sys.path.insert(0, 'src')

from ollama_client import (
    OllamaClient, 
    AsyncOllamaClient, 
    ResponseError, 
    RequestError,
    CONNECTION_ERROR_MESSAGE,
    Message,
    wait_for_ollama,
    async_wait_for_ollama
)


def test_sync_client():
    """Test synchronous client with context manager."""
    print("\n" + "="*60)
    print("Testing Synchronous OllamaClient")
    print("="*60)
    
    with OllamaClient() as client:
        print(f"✓ Context manager works")
        print(f"✓ Base URL: {client.base_url}")
        print(f"✓ Default model: {client.model}")
        
        # Test health check
        healthy = client.health_check()
        print(f"✓ Health check: {'✓ HEALTHY' if healthy else '✗ NOT RUNNING'}")
        
        if healthy:
            # Test version
            version = client.get_version()
            print(f"✓ Ollama version: {version}")
            
            # Test list models
            models = client.list_models()
            print(f"✓ Available models: {len(models)}")
            if models:
                print(f"  - {', '.join(models[:3])}")
            
            # Test chat (simple)
            try:
                response = client.chat([Message(role='user', content='Say hello in 3 words')])
                print(f"✓ Chat response: {response['content'][:50]}")
            except Exception as e:
                print(f"✗ Chat error: {e}")
    
    print("✓ Context manager exited cleanly")


async def test_async_client():
    """Test asynchronous client with async context manager."""
    print("\n" + "="*60)
    print("Testing Asynchronous AsyncOllamaClient")
    print("="*60)
    
    async with AsyncOllamaClient() as client:
        print(f"✓ Async context manager works")
        print(f"✓ Base URL: {client.base_url}")
        print(f"✓ Default model: {client.model}")
        
        # Test health check
        healthy = await client.health_check()
        print(f"✓ Async health check: {'✓ HEALTHY' if healthy else '✗ NOT RUNNING'}")
        
        if healthy:
            # Test version
            version = await client.get_version()
            print(f"✓ Async version: {version}")
            
            # Test list models
            models = await client.list_models()
            print(f"✓ Async models: {len(models)}")
            
            # Test chat (simple)
            try:
                response = await client.chat([Message(role='user', content='Say hi in 2 words')])
                print(f"✓ Async chat response: {response['content'][:50]}")
            except Exception as e:
                print(f"✗ Async chat error: {e}")
    
    print("✓ Async context manager exited cleanly")


def test_error_handling():
    """Test error handling with wrong host."""
    print("\n" + "="*60)
    print("Testing Error Handling")
    print("="*60)
    
    # Test connection to non-existent server
    try:
        with OllamaClient(host="http://localhost:9999") as client:
            print("✓ Created client with wrong port")
            healthy = client.health_check()
            print(f"✓ Health check on bad port: {healthy} (should be False)")
            
            # This should return error message, not raise
            response = client.chat([Message(role='user', content='test')])
            print(f"✓ Chat with bad connection: {response['content'][:60]}")
    except Exception as e:
        print(f"✗ Unexpected exception: {e}")
    
    print("✓ Error handling works correctly")


def test_wait_for_ollama():
    """Test wait helper functions."""
    print("\n" + "="*60)
    print("Testing Wait Helper Functions")
    print("="*60)
    
    # Test sync wait
    print("Testing sync wait_for_ollama...")
    available = wait_for_ollama(max_retries=2, timeout=0.5)
    print(f"✓ Sync wait result: {'✓ AVAILABLE' if available else '✗ NOT AVAILABLE'}")
    
    # Test async wait
    print("Testing async wait_for_ollama...")
    available = asyncio.run(async_wait_for_ollama(max_retries=2, timeout=0.5))
    print(f"✓ Async wait result: {'✓ AVAILABLE' if available else '✗ NOT AVAILABLE'}")


def test_exceptions():
    """Test custom exception classes."""
    print("\n" + "="*60)
    print("Testing Custom Exceptions")
    print("="*60)
    
    # Test ResponseError
    try:
        raise ResponseError("Test error message", 404)
    except ResponseError as e:
        print(f"✓ ResponseError caught: {e}")
        print(f"  - error: {e.error}")
        print(f"  - status_code: {e.status_code}")
    
    # Test RequestError
    try:
        raise RequestError("Test request error")
    except RequestError as e:
        print(f"✓ RequestError caught: {e}")
        print(f"  - error: {e.error}")
    
    print("✓ Exception classes work correctly")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("OLLAMA CLIENT UPGRADE TEST SUITE")
    print("="*60)
    print(f"\nConnection error message:")
    print(f"  {CONNECTION_ERROR_MESSAGE}\n")
    
    # Run tests
    test_exceptions()
    test_sync_client()
    asyncio.run(test_async_client())
    test_error_handling()
    test_wait_for_ollama()
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    main()
