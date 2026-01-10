# Development Workflow - HIPAA-Compliant Features
## How to build features that maintain security compliance

---

## 🔄 Standard Feature Development Flow

### 1. **Planning Phase** (Before Writing Code)

```markdown
☑️ Define the feature
   - What does it do?
   - What data does it access?
   - Does it handle PHI? (Assume YES unless proven otherwise)

☑️ Read compliance docs
   - Review HIPAA_COMPLIANCE.md (core principles)
   - Review SECURITY_CHECKLIST.md (specific requirements)
   - Review HIPAA_QUICK_REFERENCE.md (common patterns)

☑️ Design with security first
   - Can this work 100% offline?
   - Where will data be stored? (Must be encrypted)
   - What audit logs are needed?
   - What are the attack vectors?

☑️ Create security design doc
   - Data flow diagram
   - Encryption strategy
   - Audit logging plan
   - Threat model
```

### 2. **Implementation Phase** (Writing Code)

```python
# Template: New Feature Implementation

"""
Feature: [FEATURE_NAME]
PHI Handled: [Yes/No - list types if yes]
Security Review: [Date] by [Developer]

SECURITY CONSIDERATIONS:
- [List key security considerations]
- [List PHI protection measures]
- [List encryption methods used]
"""

import logging
from typing import Optional, Dict
# ⚠️ NEVER: import requests, openai, anthropic, boto3

logger = logging.getLogger(__name__)

# ✅ PATTERN: Use local dependencies only
from backend.llm_manager import LLMManager
from backend.crypto import encrypt_data, decrypt_data  # Phase 2
from backend.audit import log_phi_access  # Phase 2

def secure_feature_function(user_id: str, data: Dict) -> Dict:
    """
    Securely process user data with PHI protection.
    
    Args:
        user_id: User identifier (not PHI)
        data: User data (may contain PHI)
    
    Returns:
        Processed data (encrypted if contains PHI)
    
    Security:
        - All PHI encrypted before storage
        - Audit log created for access
        - No external API calls
    """
    try:
        # ✅ Log action without PHI
        logger.info(f"Processing feature for user {user_id}")
        
        # ✅ Validate inputs (prevent injection)
        if not isinstance(data, dict):
            raise ValueError("Invalid data format")
        
        # ✅ Process with in-process LLM if needed
        llm = LLMManager.get_instance()
        if llm.is_model_loaded():
            result = llm.generate(data.get("prompt", ""))
        else:
            result = "Fallback response"
        
        # ✅ Encrypt before storage (Phase 2)
        # encrypted_result = encrypt_data(result)
        
        # ✅ Audit log (Phase 2)
        # log_phi_access(
        #     user_id=user_id,
        #     action="feature_process",
        #     resource_type="feature_data",
        #     success=True
        # )
        
        return {"result": result, "encrypted": False}  # Will be True in Phase 2
        
    except Exception as e:
        # ✅ Log error WITHOUT PHI details
        logger.error(f"Feature processing failed for user {user_id}: {type(e).__name__}")
        # ❌ NEVER: logger.error(f"Failed processing: {data}")
        
        # ✅ Audit failed attempt (Phase 2)
        # log_phi_access(
        #     user_id=user_id,
        #     action="feature_process",
        #     resource_type="feature_data",
        #     success=False,
        #     error=type(e).__name__
        # )
        
        raise
```

### 3. **Testing Phase**

```python
# Template: Security-Focused Tests

import pytest
from feature_module import secure_feature_function

class TestFeatureSecurity:
    """Test security aspects of feature"""
    
    def test_no_phi_in_logs(self, caplog):
        """Verify PHI doesn't leak to logs"""
        phi_data = {"message": "I feel depressed", "mood": "sad"}
        secure_feature_function("user123", phi_data)
        
        # Assert no PHI in logs
        for record in caplog.records:
            assert "depressed" not in record.message.lower()
            assert "sad" not in record.message.lower()
            assert "I feel" not in record.message
    
    def test_encryption_applied(self):
        """Verify data is encrypted (Phase 2)"""
        data = {"sensitive": "PHI data"}
        result = secure_feature_function("user123", data)
        # assert result["encrypted"] == True  # Phase 2
    
    def test_audit_log_created(self):
        """Verify audit log entry (Phase 2)"""
        # Check audit log was written
        pass
    
    def test_works_offline(self):
        """Verify feature works without internet"""
        # Disconnect network, test feature still works
        pass
    
    def test_input_validation(self):
        """Test malicious input handling"""
        malicious_inputs = [
            {"prompt": "'; DROP TABLE users; --"},
            {"prompt": "<script>alert('xss')</script>"},
            {"prompt": "../../../etc/passwd"},
        ]
        for bad_input in malicious_inputs:
            # Should handle gracefully, not crash or execute
            with pytest.raises(ValueError):
                secure_feature_function("user123", bad_input)
```

### 4. **Review Phase**

```markdown
☑️ Self-review with SECURITY_CHECKLIST.md
   - Go through all 13 sections
   - Mark each item as complete
   - Document any exceptions

☑️ Code review with security focus
   - Another developer reviews code
   - Focus on prohibited patterns (see HIPAA_COMPLIANCE.md)
   - Verify encryption, audit logs, no external calls

☑️ Test coverage verification
   - All security tests pass
   - No PHI in logs/errors
   - Encryption verified (Phase 2)
   - Audit logs verified (Phase 2)

☑️ Documentation
   - Security considerations documented
   - API endpoints documented (if added)
   - Threat model documented
```

### 5. **Deployment Phase**

```markdown
☑️ Final security check
   - Run full test suite
   - Run HIPAA compliance tests
   - Verify no external dependencies added

☑️ Update compliance tracking
   - Update HIPAA_COMPLIANCE.md status if needed
   - Update security test results
   - Document any new risks

☑️ Deploy and monitor
   - Deploy feature
   - Monitor audit logs (Phase 2)
   - Watch for security issues
```

---

## 🚨 Red Flags - Stop and Review

If you see ANY of these, STOP and review with HIPAA_COMPLIANCE.md:

```python
# 🚨 EXTERNAL API CALLS
import requests
import openai
import anthropic
import boto3
response = requests.post(...)

# 🚨 UNENCRYPTED STORAGE
with open("data.txt", "w") as f:
    f.write(user_data)

# 🚨 PHI IN LOGS
logger.debug(f"User message: {message}")
print(f"Emotion: {emotion}")

# 🚨 CLOUD SERVICES
s3.upload_file(...)
firebase.write(...)

# 🚨 NETWORK TRANSMISSION
socket.send(user_data)
websocket.send(phi)

# 🚨 SUBPROCESS WITH PHI
subprocess.run(["external_tool", user_message])

# 🚨 TELEMETRY/ANALYTICS
analytics.track("event", {"user_data": phi})
```

---

## ✅ Green Flags - Good Patterns

```python
# ✅ IN-PROCESS LLM
from backend.llm_manager import LLMManager
llm = LLMManager.get_instance()
response = llm.generate(prompt)

# ✅ ENCRYPTED STORAGE (Phase 2)
from backend.crypto import encrypt_data
encrypted = encrypt_data(phi)
db.insert(encrypted)

# ✅ SAFE LOGGING (No PHI)
logger.info(f"Processing request for user {user_id}")

# ✅ LOCAL PROCESSING ONLY
result = local_function(data)

# ✅ AUDIT LOGGING (Phase 2)
from backend.audit import log_phi_access
log_phi_access(user_id, "read", resource_id)

# ✅ INPUT VALIDATION
if not validate_input(data):
    raise ValueError("Invalid input")
```

---

## 📝 Common Development Tasks

### Adding a new API endpoint

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class SecureRequest(BaseModel):
    """Request model - validate all inputs"""
    user_id: str
    # ⚠️ Never expose PHI in API docs/schemas
    data: dict  # Contains PHI, but not documented

@router.post("/secure-endpoint")
async def secure_endpoint(request: SecureRequest):
    """
    Secure endpoint with PHI handling.
    
    Security:
        - Validates inputs
        - Encrypts PHI before storage
        - Audit logs access
        - No external API calls
    """
    # ✅ Log without PHI
    logger.info(f"Request for user {request.user_id}")
    
    try:
        # ✅ Validate inputs
        if not request.user_id:
            raise HTTPException(400, "Invalid user_id")
        
        # ✅ Process locally
        result = process_securely(request.data)
        
        # ✅ Audit log (Phase 2)
        # log_phi_access(request.user_id, "endpoint_access", "secure_endpoint")
        
        return {"success": True, "result": result}
        
    except Exception as e:
        # ✅ Log error WITHOUT details
        logger.error(f"Endpoint failed: {type(e).__name__}")
        raise HTTPException(500, "Processing failed")
```

### Adding database storage

```python
# ⚠️ Phase 2: All database storage must use SQLCipher

from backend.database import get_encrypted_db  # Phase 2

def store_conversation(user_id: str, conversation: dict):
    """
    Store conversation with encryption.
    
    Security:
        - Uses SQLCipher (AES-256)
        - Encrypts before insert
        - Audit logs write
    """
    # Phase 2 implementation:
    # db = get_encrypted_db()
    # encrypted = encrypt_data(conversation)
    # db.execute(
    #     "INSERT INTO conversations (user_id, data) VALUES (?, ?)",
    #     (user_id, encrypted)
    # )
    # log_phi_access(user_id, "write", "conversation")
    
    # Temporary Phase 1 (no encryption yet):
    logger.warning("Phase 1: Storing unencrypted (will encrypt in Phase 2)")
    # Use in-memory only or file with warning
```

### Adding memory/RAG feature

```python
# ⚠️ Phase 2: Vector DB must be encrypted

from backend.memory_manager import MemoryManager  # Phase 2

def add_memory(user_id: str, content: str):
    """
    Add memory to RAG with encryption.
    
    Security:
        - Encrypts embeddings
        - Encrypts metadata
        - Local vector DB only (no cloud)
        - Audit logs addition
    """
    # Phase 2 implementation:
    # memory_mgr = MemoryManager()
    # encrypted_content = encrypt_data(content)
    # memory_mgr.add(user_id, encrypted_content)
    # log_phi_access(user_id, "add_memory", "rag")
    
    pass  # Implement in Phase 2
```

---

## 🔍 Pre-Commit Checklist

Before committing code:

```bash
# 1. Check for prohibited patterns
grep -r "import requests" electron-app/backend/
grep -r "import openai" electron-app/backend/
grep -r "import boto3" electron-app/backend/
grep -r "logger.debug.*{" electron-app/backend/  # May log PHI

# 2. Run tests
cd electron-app
python -m pytest tests/ -v

# 3. Run HIPAA compliance test
python test_inprocess_llm.py

# 4. Review changes
git diff --cached

# 5. Verify commit message references security
git commit -m "feat: Add [feature] with PHI encryption and audit logging"
```

---

## 📊 Phase 2 - Encryption Implementation

When Phase 2 begins, add these patterns:

```python
# 1. Database setup
from backend.database import init_encrypted_db
db = init_encrypted_db(
    path="data/auranexus.db",
    key_source="user_password"  # Derived with Argon2id
)

# 2. File encryption
from backend.crypto import EncryptedFileStorage
storage = EncryptedFileStorage(key_manager)
storage.write("conversations.json", data)

# 3. Audit logging
from backend.audit import AuditLogger
audit = AuditLogger()
audit.log(
    timestamp=datetime.now(),
    user_id=user_id,
    action="read_conversation",
    resource_type="conversation",
    resource_id=conv_id,
    success=True
)

# 4. Memory encryption
from backend.memory import EncryptedMemoryStore
memory = EncryptedMemoryStore()
memory.add_encrypted(user_id, content, metadata)
```

---

## 🎓 Learning Resources

### For new developers:

1. **Day 1:** Read HIPAA_COMPLIANCE.md completely
2. **Day 2:** Review SECURITY_CHECKLIST.md and HIPAA_QUICK_REFERENCE.md
3. **Day 3:** Study existing code patterns (llm_manager.py, async_agent.py)
4. **Day 4:** Practice with test_inprocess_llm.py
5. **Week 1:** Implement first small feature with security review

### Questions to ask yourself:

- "Is this PHI?" → Encrypt it
- "Does this need network?" → Can I make it local?
- "Should I log this?" → Does it contain PHI? (If yes, don't log)
- "Can I use this library?" → Does it send data externally?
- "Is this secure enough?" → Check HIPAA_COMPLIANCE.md

---

## 🆘 When You Need Help

1. **Security question?** → Check HIPAA_COMPLIANCE.md first
2. **Pattern question?** → Check HIPAA_QUICK_REFERENCE.md
3. **Checklist question?** → Use SECURITY_CHECKLIST.md
4. **Still unsure?** → Ask for security review
5. **Found vulnerability?** → Report immediately, don't commit

---

**Remember: Security is not a feature, it's a requirement.**

Every line of code must respect user privacy and HIPAA compliance.

---

*Last Updated: 2026-01-10*
*Version: 1.0*
