# Security & HIPAA Compliance Checklist
## Use this checklist for EVERY new feature

**Feature Name:** _______________________  
**Developer:** _______________________  
**Date:** _______________________

---

## Pre-Implementation Review

### 1. Data Classification
- [ ] Does this feature handle Protected Health Information (PHI)?
  - If YES, list what types: _______________________
  - If NO, document why: _______________________

- [ ] What data does this feature access?
  ```
  - Conversations: YES / NO
  - Emotions/Mood: YES / NO
  - User Profile: YES / NO
  - Memories/RAG: YES / NO
  - System Logs: YES / NO
  - Other: _______________________
  ```

### 2. Architecture Review
- [ ] Can this feature work 100% offline?
- [ ] Does this require external network calls?
  - If YES, can it be redesigned to be local-only?
  - If absolutely necessary, how will PHI be protected?
- [ ] Are all dependencies HIPAA-compliant or audited?
- [ ] Does this feature increase attack surface?

### 3. Encryption Requirements
- [ ] Is all PHI encrypted at rest (AES-256-GCM)?
- [ ] Are encryption keys properly managed (OS keychain)?
- [ ] Is data validated before encryption/decryption?
- [ ] Are temporary files encrypted or avoided?
- [ ] Is memory cleared after processing PHI?

---

## Implementation Checklist

### 4. Code Security
- [ ] Input validation implemented
- [ ] Output sanitization implemented
- [ ] No PHI in logs (use placeholders like "***")
- [ ] No PHI in error messages
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitize HTML)
- [ ] Path traversal prevention (validate file paths)
- [ ] Command injection prevention (avoid shell=True)

### 5. Audit Logging
- [ ] Audit log entry created for PHI access
- [ ] Audit log includes: timestamp, action, user, success/failure
- [ ] Audit logs are encrypted
- [ ] Audit logs are immutable (append-only)
- [ ] Failed access attempts are logged

### 6. Access Control
- [ ] User authentication required
- [ ] Authorization checks implemented
- [ ] Session timeout configured
- [ ] Least privilege principle followed
- [ ] No hardcoded credentials

---

## Testing Checklist

### 7. Security Testing
- [ ] Unit tests for encryption/decryption
- [ ] Test with invalid/malicious inputs
- [ ] Test authentication bypass attempts
- [ ] Test authorization boundary violations
- [ ] Verify no PHI leakage in logs
- [ ] Verify no PHI in temporary files
- [ ] Memory leak testing
- [ ] Encryption key rotation testing

### 8. Integration Testing
- [ ] End-to-end encryption verified
- [ ] Data flow mapped and validated
- [ ] No unencrypted PHI at any stage
- [ ] Audit logs captured correctly
- [ ] Error handling doesn't expose PHI

### 9. Compliance Testing
- [ ] HIPAA Security Rule requirements met
- [ ] HIPAA Privacy Rule requirements met
- [ ] Data retention policy followed
- [ ] User can delete their data
- [ ] User can export their data (encrypted)

---

## Documentation Checklist

### 10. Documentation
- [ ] Security considerations documented
- [ ] Data flow diagram created
- [ ] Threat model completed
- [ ] API endpoints documented (if applicable)
- [ ] Configuration options documented
- [ ] Emergency procedures documented

### 11. Code Review
- [ ] Security-focused code review completed
- [ ] Reviewer name: _______________________
- [ ] All security concerns addressed
- [ ] HIPAA_COMPLIANCE.md reviewed and followed

---

## Deployment Checklist

### 12. Pre-Deployment
- [ ] Encryption keys generated securely
- [ ] Key backup procedure tested
- [ ] Database migrations tested
- [ ] Rollback plan documented
- [ ] Monitoring/alerting configured

### 13. Post-Deployment
- [ ] Feature tested in production-like environment
- [ ] Audit logs verified working
- [ ] Encryption verified working
- [ ] User acceptance testing completed
- [ ] Performance impact assessed

---

## Common Patterns

### ✅ SAFE Patterns

**Local LLM Generation:**
```python
from backend.llm_manager import LLMManager

llm = LLMManager.get_instance()
response = llm.generate(user_message)  # Stays in-process
```

**Encrypted Storage:**
```python
from backend.crypto import encrypt_data, decrypt_data

encrypted = encrypt_data(phi_data)
db.insert(encrypted)  # Store encrypted
```

**Audit Logging:**
```python
from backend.audit import log_phi_access

log_phi_access(
    user_id=user.id,
    action="read_conversation",
    resource_id=conversation.id,
    success=True
)
```

**Safe Logging:**
```python
logger.info(f"Processing message for user {user.id}")  # ✅ No PHI
# NOT: logger.info(f"User said: {message}")  # ❌ PHI leak
```

### ❌ UNSAFE Patterns

**External API (FORBIDDEN):**
```python
# ❌ NEVER DO THIS
import requests
requests.post("https://api.example.com", json={"message": phi_data})
```

**Unencrypted Storage (FORBIDDEN):**
```python
# ❌ NEVER DO THIS
with open("conversation.txt", "w") as f:
    f.write(phi_data)
```

**PHI in Logs (FORBIDDEN):**
```python
# ❌ NEVER DO THIS
logger.debug(f"User emotion: {emotion_data}")
print(f"Processing: {user_message}")
```

**Cloud Services (FORBIDDEN):**
```python
# ❌ NEVER DO THIS
boto3.client('s3').upload_file('conversations.db', bucket, key)
```

---

## Sign-Off

- [ ] All checklist items completed
- [ ] Security review passed
- [ ] HIPAA compliance verified
- [ ] Ready for deployment

**Developer Signature:** _______________________  
**Reviewer Signature:** _______________________  
**Date:** _______________________

---

**Reference:** See [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) for full framework.
