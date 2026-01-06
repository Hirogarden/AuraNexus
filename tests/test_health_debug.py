"""Quick health check debug test."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import asyncio
from ollama_client import AsyncOllamaClient

async def test():
    print("Testing AsyncOllamaClient...")
    try:
        async with AsyncOllamaClient() as client:
            print(f"Client created: {client.base_url}")
            
            print("Checking health...")
            healthy = await client.health_check()
            print(f"Health: {healthy}")
            
            if healthy:
                print("Getting version...")
                version = await client.get_version()
                print(f"Version: {version}")
                
                print("Listing models...")
                models = await client.list_models()
                print(f"Models: {models}")
            else:
                print("Health check failed - Ollama might not be running")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
