"""
Test the async agent system (no multiprocessing)
Run this to verify Windows compatibility
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from agent_manager_async import AsyncAgentManager


async def test_basic_agent():
    """Test basic agent communication"""
    print("=== Testing Async Agent System ===\n")
    
    # Create manager
    manager = AsyncAgentManager()
    
    try:
        # Start agents
        print("Starting agents...")
        await manager.start_all_agents()
        
        # Check status
        status = manager.get_agent_status()
        print(f"Agent status: {status}\n")
        
        # Send a test message
        print("Sending test message to narrator...")
        response = await manager.send_message(
            "A lone traveler enters the ancient forest",
            target_agent="narrator"
        )
        print(f"Response: {response}\n")
        
        # Broadcast message
        print("Broadcasting message to all agents...")
        responses = await manager.broadcast_message("The adventure begins!")
        for resp in responses:
            print(f"  {resp['agent']}: {resp['response']}")
        
        print("\n✅ All tests passed! No pickle errors.")
        
    finally:
        # Cleanup
        print("\nStopping agents...")
        await manager.stop_all_agents()
        print("Done.")


async def test_context_manager():
    """Test using manager as context manager"""
    print("\n=== Testing Context Manager ===\n")
    
    async with AsyncAgentManager() as manager:
        print("Agents started via context manager")
        
        response = await manager.send_message(
            "Quick test message",
            target_agent="director"
        )
        print(f"Response: {response}")
        
    print("Agents stopped automatically")


async def main():
    """Run all tests"""
    try:
        await test_basic_agent()
        await test_context_manager()
        
        print("\n" + "="*50)
        print("SUCCESS: Async agent system working!")
        print("No Windows multiprocessing errors!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run on Windows without issues
    asyncio.run(main())
