# Chat Integration with Hierarchical Memory

## ✅ COMPLETED: Chat Endpoints Now Use Hierarchical Memory

The chat system has been upgraded to use hierarchical memory with automatic session management, encryption for medical conversations, and proper data isolation.

---

## 🔄 What Changed

### Before (Old Memory System)
```python
# All conversations mixed together
# No encryption
# Simple short-term + long-term
POST /chat {"message": "Hello"}
```

### After (Hierarchical Memory)
```python
# Isolated sessions per conversation type
# Automatic encryption for medical
# 5-layer memory architecture
POST /chat {
    "message": "Hello",
    "session_id": "my_session",
    "conversation_type": "medical_assistant",
    "encryption_key": "secure_key"
}
```

---

## 📡 Updated API Endpoints

### 1. `/chat` - Send Message (Enhanced)

**Request:**
```json
{
    "message": "I'm feeling anxious today",
    "target_agent": "meta_hiro",
    "session_id": "peer_support_jan2026",
    "conversation_type": "peer_support",
    "encryption_key": "my_secure_password"
}
```

**Fields:**
- `message` (required): The user's message
- `target_agent` (optional): Specific agent to respond
- `session_id` (optional): Session identifier (default: "default_chat")
- `conversation_type` (optional): Type of conversation
  - `"peer_support"` → Encrypted peer support (Meta-Hiro)
  - `"medical_assistant"` → Encrypted medical AI assistant
  - `"story"` → Story-specific isolation
  - `"general"` → General conversation (default)
- `encryption_key` (optional): Required for medical conversations

**Auto-Session Creation:**
- If session doesn't exist, it's created automatically
- Encryption enabled based on `conversation_type`
- Messages stored in appropriate directory (medical_secure/ vs general/)

**Response:**
```json
{
    "agent": "meta_hiro",
    "role": "peer_support",
    "response": "I hear you. Let's talk about it...",
    "timestamp": "2026-01-12T10:30:00"
}
```

---

### 2. `/memory/stats` - Get Session Stats

**Request:**
```
GET /memory/stats?session_id=peer_support_jan2026
```

**Response:**
```json
{
    "project_id": "peer_support_jan2026",
    "project_type": "medical_peer",
    "encrypted": true,
    "active_messages": 10,
    "short_term_messages": 5,
    "compression_queue": 0,
    "bookmarks": 2,
    "rag_enabled": true,
    "medium_term_count": 0,
    "long_term_count": 0,
    "archived_count": 0
}
```

---

### 3. `/memory/recent` - Get Recent Messages

**Request:**
```
GET /memory/recent?session_id=my_session&n=10
```

**Response:**
```json
{
    "session_id": "my_session",
    "messages": [
        {"content": "Hello", "role": "user", "timestamp": "..."},
        {"content": "Hi there!", "role": "assistant", "timestamp": "..."}
    ],
    "count": 2,
    "total_active": 2
}
```

---

### 4. `/memory/query` - Semantic Search

**Request:**
```json
{
    "query": "anxiety coping strategies",
    "session_id": "peer_support_jan2026",
    "n_results": 5,
    "layers": ["medium_term", "long_term"]
}
```

**Response:**
```json
{
    "session_id": "peer_support_jan2026",
    "results": [
        {
            "content": "We discussed breathing exercises...",
            "layer": "medium_term",
            "metadata": {"timestamp": "..."},
            "distance": 0.23
        }
    ]
}
```

---

### 5. `/memory/context` - Get LLM Context (NEW)

**Request:**
```
GET /memory/context?session_id=my_session&n=10
```

**Response:**
```json
{
    "session_id": "my_session",
    "context": "user: Hello\nassistant: Hi there!\nuser: How are you?",
    "message_count": 10
}
```

---

## 🔐 Encryption Behavior

### Automatic Encryption
```python
# These conversation types enable encryption automatically:
conversation_type = "peer_support"        # → Encrypted
conversation_type = "medical_assistant"   # → Encrypted

# These types do NOT encrypt:
conversation_type = "story"               # → Not encrypted
conversation_type = "general"             # → Not encrypted
```

### Storage Separation
```
data/memory/
├── medical_secure/           # ENCRYPTED sessions
│   ├── peer_support_jan2026/
│   └── medical_assistant_user1/
└── general/                  # NOT ENCRYPTED sessions
    ├── default_chat/
    └── fantasy_adventure_01/
```

---

## 🧪 Testing

### Start Backend
```bash
cd electron-app/backend
uvicorn core_app:app --reload
```

### Run Integration Test
```bash
python test_chat_integration.py
```

**Tests:**
1. ✅ General chat (unencrypted)
2. ✅ Medical assistant (encrypted)
3. ✅ Peer support (encrypted)
4. ✅ Session listing
5. ✅ Medical data deletion

---

## 📝 Usage Examples

### Example 1: Casual Chat
```python
requests.post("http://localhost:8000/chat", json={
    "message": "Tell me a joke",
    "session_id": "casual_chat",
    "conversation_type": "general"
})
```

### Example 2: Peer Support (Encrypted)
```python
requests.post("http://localhost:8000/chat", json={
    "message": "I'm struggling with anxiety",
    "session_id": "metahiro_session_1",
    "conversation_type": "peer_support",
    "encryption_key": "user_password_123"
})
```

### Example 3: Medical Assistant (Encrypted)
```python
requests.post("http://localhost:8000/chat", json={
    "message": "Can you explain my symptoms?",
    "session_id": "medical_ai_user1",
    "conversation_type": "medical_assistant",
    "encryption_key": "secure_medical_key"
})
```

### Example 4: Story Session
```python
requests.post("http://localhost:8000/chat", json={
    "message": "The hero enters the dark forest",
    "session_id": "fantasy_story_ch1",
    "conversation_type": "story",
    "target_agent": "narrator"
})
```

---

## 🗑️ Medical Data Management

### Check Medical Sessions
```bash
GET /medical/summary
```

### Delete ALL Medical Data
```bash
POST /medical/delete-all
{
    "confirmation": "DELETE_ALL_MEDICAL_DATA"
}
```

**Result:**
- ✅ All peer support sessions deleted
- ✅ All medical assistant sessions deleted
- ✅ General chat and stories preserved

---

## 🎯 Next Steps

1. **Frontend Integration**: Update UI to:
   - Add conversation type selector
   - Show encryption status
   - Provide medical deletion button

2. **Session Persistence**: Sessions auto-save to disk, reload on restart

3. **Background Compression**: Runs automatically during idle time

4. **Bookmark Navigation**: Add UI for bookmarks (sticky notes)

---

## ⚠️ Important Notes

- **Encryption keys**: Store securely, required to decrypt later
- **Session IDs**: Must be unique per conversation thread
- **Medical deletion**: IRREVERSIBLE - use confirmation string
- **Default behavior**: If no `conversation_type` specified, uses "general" (unencrypted)

---

## 🔍 Troubleshooting

### "Session not found"
- Session auto-creates on first message
- Check session_id spelling

### "Encryption key required"
- Medical conversations need `encryption_key` parameter
- Use strong password/key

### "cryptography package required"
- Run: `pip install cryptography==41.0.7`
- Required for medical conversations

---

**Status**: ✅ Production Ready
**Date**: January 12, 2026
**Changes**: Chat endpoints migrated to hierarchical memory with encryption
