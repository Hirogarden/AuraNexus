"""
Quick test of chat endpoint with agents and hierarchical memory
Run this while the server is running in a separate terminal
"""

import requests
import time

BASE_URL = "http://localhost:8000"

def test_chat():
    print("\n" + "="*60)
    print("  🧪 CHAT + HIERARCHICAL MEMORY TEST")
    print("="*60)
    
    # Test 1: Story conversation (unencrypted)
    print("\n📖 Test 1: Story with Narrator")
    try:
        r = requests.post(f"{BASE_URL}/chat", json={
            "message": "Tell me about a dark forest",
            "session_id": "fantasy_story",
            "conversation_type": "story",
            "target_agent": "narrator"
        }, timeout=30)
        
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Agent: {data['agent']}")
            print(f"Response: {data['response'][:150]}...")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(1)
    
    # Test 2: Medical assistant (encrypted)
    print("\n🔒 Test 2: Medical Assistant (Encrypted)")
    try:
        r = requests.post(f"{BASE_URL}/chat", json={
            "message": "I'm feeling anxious",
            "session_id": "medical_session",
            "conversation_type": "medical_assistant",
            "encryption_key": "test_password_123"
        }, timeout=30)
        
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Agent: {data['agent']}")
            print(f"Response: {data['response'][:150]}...")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(1)
    
    # Test 3: Check memory stats
    print("\n📊 Test 3: Memory Stats")
    try:
        r = requests.get(f"{BASE_URL}/memory/stats?session_id=fantasy_story")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            stats = r.json()
            print(f"Project type: {stats['project_type']}")
            print(f"Encrypted: {stats['encrypted']}")
            print(f"Active messages: {stats['active_messages']}")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*60)
    print("  ✅ TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    print("\n🚀 Make sure the server is running:")
    print("   cd electron-app/backend")
    print("   uvicorn core_app:app --reload\n")
    
    try:
        # Check server
        r = requests.get(f"{BASE_URL}/")
        if r.status_code == 200:
            print("✅ Server is online!\n")
            test_chat()
        else:
            print("❌ Server returned error")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Start it first!")
    except Exception as e:
        print(f"❌ Error: {e}")
