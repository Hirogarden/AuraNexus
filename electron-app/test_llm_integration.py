"""
Test LLM integration with KoboldCPP
Checks if KoboldCPP is available and tests agent responses
"""

import asyncio
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from agent_manager_async import AsyncAgentManager

KCPP_URL = os.getenv('KCPP_URL', 'http://127.0.0.1:5001')


async def check_koboldcpp():
    """Check if KoboldCPP is running"""
    print(f"Checking KoboldCPP at {KCPP_URL}...")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{KCPP_URL}/api/v1/model")
            if response.status_code == 200:
                model_info = response.json()
                print(f"✅ KoboldCPP is running")
                print(f"   Model: {model_info.get('result', 'Unknown')}")
                return True
            else:
                print(f"❌ KoboldCPP returned status {response.status_code}")
                return False
        except httpx.ConnectError:
            print(f"❌ Cannot connect to KoboldCPP at {KCPP_URL}")
            print("   Make sure KoboldCPP is running with: python koboldcpp.py --model <your_model.gguf>")
            return False
        except Exception as e:
            print(f"❌ Error checking KoboldCPP: {e}")
            return False


async def test_with_llm():
    """Test agents with LLM responses"""
    print("\n=== Testing with KoboldCPP LLM ===\n")
    
    async with AsyncAgentManager() as manager:
        print("Agents started with LLM enabled\n")
        
        # Test narrator
        print("1. Testing narrator with LLM...")
        response = await manager.send_message(
            "A mysterious stranger approaches the village gates at sunset",
            target_agent="narrator"
        )
        print(f"   Response: {response['response']}\n")
        
        # Test character
        print("2. Testing character_1 with LLM...")
        response = await manager.send_message(
            "What do you think about the stranger?",
            target_agent="character_1"
        )
        print(f"   Response: {response['response']}\n")
        
        # Test director
        print("3. Testing director with LLM...")
        response = await manager.send_message(
            "The tension rises as storm clouds gather",
            target_agent="director"
        )
        print(f"   Response: {response['response']}\n")
        
        print("✅ All LLM tests completed!")


async def test_fallback_mode():
    """Test agents with LLM disabled (fallback mode)"""
    print("\n=== Testing Fallback Mode (No LLM) ===\n")
    
    manager = AsyncAgentManager()
    
    # Disable LLM for all agents
    for config in manager.agent_configs.values():
        config["use_llm"] = False
    
    async with manager:
        print("Agents started with LLM disabled\n")
        
        response = await manager.send_message(
            "Test message",
            target_agent="narrator"
        )
        print(f"   Fallback response: {response['response']}\n")
        
        print("✅ Fallback mode working!")


async def main():
    """Run tests"""
    print("="*60)
    print("KoboldCPP Integration Test")
    print("="*60 + "\n")
    
    # Check if KoboldCPP is available
    kcpp_available = await check_koboldcpp()
    
    if kcpp_available:
        # Test with real LLM
        await test_with_llm()
    else:
        print("\n⚠️  KoboldCPP not available, testing fallback mode only")
    
    # Always test fallback mode
    await test_fallback_mode()
    
    print("\n" + "="*60)
    print("Tests Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
