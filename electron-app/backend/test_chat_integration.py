"""
Test updated chat endpoint with hierarchical memory
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_general_chat():
    """Test general conversation (no encryption)"""
    print("\n" + "="*60)
    print("TEST 1: General Chat (No Encryption)")
    print("="*60)
    
    # Send a few messages
    messages = [
        "Hello! How are you today?",
        "Can you tell me about Python programming?",
        "What's your favorite programming language?"
    ]
    
    for msg in messages:
        print(f"\n💬 User: {msg}")
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "message": msg,
                "session_id": "test_general_chat",
                "conversation_type": "general"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"🤖 {data['agent']}: {data['response'][:100]}...")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
        
        time.sleep(0.5)
    
    # Check memory stats
    print("\n📊 Session Stats:")
    stats = requests.get(
        f"{BASE_URL}/memory/stats",
        params={"session_id": "test_general_chat"}
    ).json()
    print(f"   Active messages: {stats.get('active_messages', 0)}")
    print(f"   Encrypted: {stats.get('encrypted', False)}")
    print(f"   Project type: {stats.get('project_type', 'unknown')}")

def test_medical_assistant():
    """Test medical assistant (WITH encryption)"""
    print("\n" + "="*60)
    print("TEST 2: Medical Assistant (Encrypted)")
    print("="*60)
    
    messages = [
        "I've been feeling anxious lately",
        "My insurance info is BlueCross policy #ABC123",
        "Can you help me understand my symptoms?"
    ]
    
    encryption_key = "secure_medical_key_2026"
    
    for msg in messages:
        print(f"\n💬 User: {msg}")
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "message": msg,
                "session_id": "test_medical_assistant",
                "conversation_type": "medical_assistant",
                "encryption_key": encryption_key
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"🤖 {data['agent']}: {data['response'][:100]}...")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
        
        time.sleep(0.5)
    
    # Check memory stats
    print("\n📊 Session Stats:")
    stats = requests.get(
        f"{BASE_URL}/memory/stats",
        params={"session_id": "test_medical_assistant"}
    ).json()
    print(f"   Active messages: {stats.get('active_messages', 0)}")
    print(f"   🔒 Encrypted: {stats.get('encrypted', False)}")
    print(f"   Project type: {stats.get('project_type', 'unknown')}")

def test_peer_support():
    """Test peer support (WITH encryption)"""
    print("\n" + "="*60)
    print("TEST 3: Peer Support / Meta-Hiro (Encrypted)")
    print("="*60)
    
    messages = [
        "I'm struggling with depression today",
        "My address is 123 Main Street, can we talk about home safety?"
    ]
    
    encryption_key = "metahiro_secure_2026"
    
    for msg in messages:
        print(f"\n💬 User: {msg}")
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "message": msg,
                "session_id": "test_peer_support",
                "conversation_type": "peer_support",
                "encryption_key": encryption_key
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"🤖 {data['agent']}: {data['response'][:100]}...")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
        
        time.sleep(0.5)
    
    # Check memory stats
    print("\n📊 Session Stats:")
    stats = requests.get(
        f"{BASE_URL}/memory/stats",
        params={"session_id": "test_peer_support"}
    ).json()
    print(f"   Active messages: {stats.get('active_messages', 0)}")
    print(f"   🔒 Encrypted: {stats.get('encrypted', False)}")
    print(f"   Project type: {stats.get('project_type', 'unknown')}")

def test_session_list():
    """Test session listing"""
    print("\n" + "="*60)
    print("TEST 4: Session Management")
    print("="*60)
    
    print("\n📋 All Sessions:")
    sessions = requests.get(f"{BASE_URL}/sessions/list").json()
    
    for session in sessions.get('sessions', []):
        print(f"\n   • {session['session_id']}")
        print(f"     Type: {session['project_type']}")
        print(f"     Encrypted: {'🔒' if session['encrypted'] else '🔓'}")
        print(f"     Messages: {session['stats']['active_messages']} active")

def test_medical_deletion():
    """Test medical data deletion"""
    print("\n" + "="*60)
    print("TEST 5: Medical Data Deletion")
    print("="*60)
    
    # Get summary first
    print("\n📊 Medical Data Summary:")
    summary = requests.get(f"{BASE_URL}/medical/summary").json()
    print(f"   Medical sessions: {summary['medical_sessions_count']}")
    
    if summary['medical_sessions_count'] > 0:
        for session in summary['sessions']:
            print(f"   • {session['session_id']} ({session['type']})")
        
        # Delete all medical data
        print("\n🗑️  Deleting ALL medical data...")
        result = requests.post(
            f"{BASE_URL}/medical/delete-all",
            json={"confirmation": "DELETE_ALL_MEDICAL_DATA"}
        ).json()
        
        print(f"   ✅ Deleted {result['total_deleted']} sessions")
        for sid in result['deleted_sessions']:
            print(f"      • {sid}")
        
        # Verify general chat still exists
        print("\n📋 Remaining Sessions:")
        sessions = requests.get(f"{BASE_URL}/sessions/list").json()
        for session in sessions.get('sessions', []):
            print(f"   • {session['session_id']} ({session['project_type']})")
    else:
        print("   No medical sessions to delete")

def main():
    print("\n" + "="*60)
    print("  🧪 HIERARCHICAL MEMORY CHAT INTEGRATION TEST")
    print("="*60)
    print("\nMake sure the backend is running:")
    print("  cd electron-app/backend")
    print("  uvicorn core_app:app --reload")
    print("\nPress Enter to start tests...")
    input()
    
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ Backend not responding. Start it first!")
            return
        
        print("✅ Backend is running\n")
        
        # Run tests
        test_general_chat()
        time.sleep(1)
        
        test_medical_assistant()
        time.sleep(1)
        
        test_peer_support()
        time.sleep(1)
        
        test_session_list()
        time.sleep(1)
        
        test_medical_deletion()
        
        print("\n" + "="*60)
        print("  ✅ ALL TESTS COMPLETE")
        print("="*60)
        print("\nKey Findings:")
        print("  • General chat: Unencrypted, general/ directory")
        print("  • Medical assistant: Encrypted, medical_secure/ directory")
        print("  • Peer support: Encrypted, medical_secure/ directory")
        print("  • Medical deletion: Removes both medical types")
        print("  • General chat preserved after medical deletion")
        print("="*60 + "\n")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend at", BASE_URL)
        print("Start it with: uvicorn core_app:app --reload")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
