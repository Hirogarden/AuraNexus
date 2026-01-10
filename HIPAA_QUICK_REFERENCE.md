# HIPAA Compliance Quick Reference
## Keep this card handy during development

---

## ⚠️ GOLDEN RULES

1. **PHI NEVER LEAVES THE APP**
   - No external APIs with user data
   - No cloud services
   - No analytics/telemetry
   - In-process LLM only

2. **ENCRYPT EVERYTHING**
   - All PHI encrypted at rest (AES-256-GCM)
   - Encrypted databases (SQLCipher)
   - Encrypted memory/RAG data
   - Secure key storage (OS keychain)

3. **AUDIT ALL ACCESS**
   - Log every PHI read/write
   - Immutable audit logs
   - User-accessible audit trail
   - Encrypted audit logs

4. **ZERO TRUST**
   - Validate all inputs
   - Sanitize all outputs
   - No PHI in logs/errors
   - Defense in depth

5. **LOCAL FIRST**
   - Works 100% offline
   - No internet required
   - User controls their data
   - No server dependencies

---

## 🚫 NEVER DO THIS

```python
# ❌ External API with PHI
requests.post("https://api.example.com", json=user_data)
openai.chat.completions.create(messages=[phi])

# ❌ Unencrypted storage
with open("conversations.txt", "w") as f:
    f.write(user_message)

# ❌ PHI in logs
logger.debug(f"User said: {message}")
print(f"Emotion: {emotion_data}")

# ❌ Cloud services
s3.upload_file("data.db", bucket, key)
```

---

## ✅ ALWAYS DO THIS

```python
# ✅ In-process LLM
from backend.llm_manager import LLMManager
llm = LLMManager.get_instance()
response = llm.generate(user_message)

# ✅ Encrypted storage
from backend.crypto import encrypt_data
encrypted = encrypt_data(phi_data)
db.insert(encrypted)

# ✅ Safe logging (no PHI)
logger.info(f"Processing message for user {user_id}")

# ✅ Audit logging
from backend.audit import log_phi_access
log_phi_access(user_id, "read_conversation", conversation_id)
```

---

## 📋 BEFORE CODING CHECKLIST

- [ ] Read HIPAA_COMPLIANCE.md
- [ ] Review SECURITY_CHECKLIST.md
- [ ] Confirm feature can work offline
- [ ] Plan encryption strategy
- [ ] Design audit logging
- [ ] No external dependencies with PHI

---

## 🔍 CODE REVIEW QUESTIONS

1. Does this handle PHI? → Encrypt it
2. Does this call external APIs? → Eliminate or make local
3. Does this log data? → Remove PHI from logs
4. Does this store data? → Encrypt at rest
5. Can user delete their data? → Implement deletion
6. Is there an audit log? → Add audit entry

---

## 📚 DOCUMENTATION

- [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) - Full framework (READ FIRST)
- [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) - Feature checklist
- [INPROCESS_LLM_ARCHITECTURE.md](./electron-app/INPROCESS_LLM_ARCHITECTURE.md) - LLM security

---

## 🎯 CURRENT PHASE

**Phase 1: Foundation** ✅ COMPLETE
- In-process LLM ✅
- No external APIs ✅
- Async architecture ✅

**Phase 2: Encryption** 🔄 IN PROGRESS
- [ ] SQLCipher integration
- [ ] Encrypted conversation storage
- [ ] Encrypted RAG/memory
- [ ] Audit logging system

**Phase 3: Advanced** 📋 PLANNED
- [ ] E2E encryption
- [ ] Access control
- [ ] Breach notification
- [ ] Compliance audit

---

## 💡 MENTAL HEALTH SPECIFIC

**Emotional Data** = Highly Sensitive PHI
- Mood logs
- Crisis indicators
- Therapeutic context
- Relationship data

**Requirements:**
- Extra encryption layer
- Separate access controls
- Crisis detection (local only)
- No external emergency services calls

---

## 🆘 WHEN IN DOUBT

1. Check [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md)
2. Run security checklist
3. Assume it's PHI and protect it
4. Keep it local, keep it encrypted
5. Never compromise on security

**Remember: One breach can destroy trust. Security is not optional.**

---

*Last Updated: 2026-01-10*
*Version: 1.0*
