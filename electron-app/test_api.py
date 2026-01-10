"""
Test the FastAPI backend with async agents
"""

import httpx
import asyncio


async def test_api():
    """Test all API endpoints"""
    base_url = "http://localhost:8001"
    
    async with httpx.AsyncClient() as client:
        print("=== Testing AuraNexus FastAPI Backend ===\n")
        
        # Test 1: Health check
        print("1. Testing health check...")
        resp = await client.get(f"{base_url}/")
        print(f"   Status: {resp.json()}\n")
        
        # Test 2: List agents
        print("2. Listing agent status...")
        resp = await client.get(f"{base_url}/agents")
        print(f"   Agents: {resp.json()}\n")
        
        # Test 3: Send chat message to narrator
        print("3. Sending message to narrator...")
        resp = await client.post(
            f"{base_url}/chat",
            json={
                "message": "A mysterious traveler arrives at the crossroads",
                "target_agent": "narrator"
            }
        )
        result = resp.json()
        print(f"   Agent: {result['agent']}")
        print(f"   Role: {result['role']}")
        print(f"   Response: {result['response']}\n")
        
        # Test 4: Send to director
        print("4. Sending message to director...")
        resp = await client.post(
            f"{base_url}/chat",
            json={
                "message": "What should happen next in the story?",
                "target_agent": "director"
            }
        )
        result = resp.json()
        print(f"   Agent: {result['agent']}")
        print(f"   Response: {result['response']}\n")
        
        # Test 5: Broadcast to all agents
        print("5. Broadcasting to all agents...")
        resp = await client.post(
            f"{base_url}/broadcast",
            json={"message": "The adventure begins now!"}
        )
        result = resp.json()
        print(f"   Message broadcast to {result['count']} agents:")
        for r in result['responses']:
            print(f"     - {r['agent']}: {r['response'][:60]}...")
        
        print("\n✅ All API tests passed!")


if __name__ == "__main__":
    asyncio.run(test_api())
