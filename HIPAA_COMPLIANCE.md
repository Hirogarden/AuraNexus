# HIPAA COMPLIANCE FRAMEWORK
## AuraNexus - Mental Health Support Platform

**⚠️ CRITICAL: This document defines mandatory security and privacy requirements**
**ALL features must comply with these principles. No exceptions.**

---

## Mission Statement

AuraNexus is being designed as a **mental health support platform** that handles Protected Health Information (PHI). We are building toward full HIPAA compliance with the following core principle:

> **All user data, including conversations, emotional states, memories, and personal information, must be treated as Protected Health Information (PHI) and secured accordingly.**

---

## Current Compliance Status

### ✅ Implemented (Phase 1)
- [x] In-process LLM (no external servers)
- [x] No network calls during inference
- [x] Data stays within application boundary
- [x] Async architecture (no multiprocessing issues)
- [x] Self-contained executable design

### 🔄 In Progress (Phase 2)
- [ ] Encrypted storage for conversation logs
- [ ] Encrypted storage for RAG/memory data
- [ ] Encrypted database for user profiles
- [ ] Audit logging system
- [ ] Access control framework

### 📋 Planned (Phase 3)
- [ ] End-to-end encryption for all PHI
- [ ] Secure key management
- [ ] Data retention policies
- [ ] Breach notification system
- [ ] HIPAA Business Associate Agreement (BAA) framework
- [ ] Compliance audit trail
- [ ] Data anonymization tools

---

## HIPAA Requirements for Mental Health Data

### Technical Safeguards (§164.312)

#### Access Control (§164.312(a)(1))
```
REQUIREMENT: Implement technical policies to allow only authorized access
STATUS: Planned
IMPLEMENTATION:
  - User authentication system
  - Role-based access control (RBAC)
  - Session management with timeout
  - Unique user identifiers
```

#### Audit Controls (§164.312(b))
```
REQUIREMENT: Record and examine activity in systems with ePHI
STATUS: Planned
IMPLEMENTATION:
  - Log all access to PHI
  - Log all modifications to PHI
  - Log authentication attempts
  - Immutable audit logs with timestamps
  - Regular audit log reviews
```

#### Integrity (§164.312(c)(1))
```
REQUIREMENT: Protect ePHI from improper alteration or destruction
STATUS: Partial
IMPLEMENTATION:
  - Checksums for stored data ✅
  - Version control for memories
  - Backup and recovery system
  - Data validation on read/write
```

#### Person or Entity Authentication (§164.312(d))
```
REQUIREMENT: Verify identity of persons/entities accessing ePHI
STATUS: Planned
IMPLEMENTATION:
  - Secure password storage (bcrypt/Argon2)
  - Optional 2FA/MFA
  - Biometric authentication (optional)
  - Session token management
```

#### Transmission Security (§164.312(e)(1))
```
REQUIREMENT: Protect ePHI transmitted over networks
STATUS: ✅ COMPLIANT (no network transmission)
IMPLEMENTATION:
  - In-process LLM (no external API calls) ✅
  - Local storage only ✅
  - Encrypted IPC between Electron processes
  - No cloud services for PHI
```

### Physical Safeguards (§164.310)

#### Device and Media Controls (§164.310(d)(1))
```
REQUIREMENT: Protect devices/media containing ePHI
STATUS: Partial
IMPLEMENTATION:
  - Encrypted storage at rest
  - Secure deletion of temporary files
  - No PHI in swap files
  - Memory scrubbing on exit
  - Disk encryption recommendations
```

### Administrative Safeguards (§164.308)

#### Risk Analysis (§164.308(a)(1)(ii)(A))
```
REQUIREMENT: Regular risk assessments
STATUS: Ongoing
IMPLEMENTATION:
  - Security review checklist for features
  - Threat modeling for new components
  - Vulnerability scanning
  - Penetration testing (future)
```

---

## Architectural Principles (Non-Negotiable)

### 1. Data Containment
```
✅ DO: Keep all PHI within application process boundary
❌ DON'T: Send PHI to external APIs, servers, or cloud services

RATIONALE: 
  - Minimizes attack surface
  - Reduces compliance scope
  - Eliminates third-party risk
  - User maintains control
```

### 2. Local-First Architecture
```
✅ DO: Store all data locally on user's device
❌ DON'T: Require internet connectivity for core features

RATIONALE:
  - User controls their data
  - No server breaches possible
  - Works offline/air-gapped
  - HIPAA compliance simplified
```

### 3. Encryption by Default
```
✅ DO: Encrypt all PHI at rest and in transit
❌ DON'T: Store plaintext PHI anywhere

IMPLEMENTATION:
  - AES-256-GCM for file encryption
  - Argon2id for key derivation
  - Encrypted SQLite databases
  - Encrypted memory dumps
  - Secure key storage (OS keychain)
```

### 4. Minimal Data Collection
```
✅ DO: Collect only data necessary for functionality
❌ DON'T: Collect telemetry, analytics, or diagnostic data with PHI

RATIONALE:
  - Reduces risk exposure
  - Respects user privacy
  - Simplifies compliance
  - No data to breach
```

### 5. Zero Trust Model
```
✅ DO: Assume all components could be compromised
❌ DON'T: Trust data from any source without validation

IMPLEMENTATION:
  - Validate all inputs
  - Sanitize all outputs
  - Encrypt inter-process communication
  - Verify data integrity
  - Defense in depth
```

### 6. Audit Everything
```
✅ DO: Log all access and modifications to PHI
❌ DON'T: Allow silent data access or changes

IMPLEMENTATION:
  - Immutable audit logs
  - Tamper-evident logging
  - User-accessible audit trail
  - Automated anomaly detection
```

---

## Feature Development Checklist

**Before implementing ANY feature, verify:**

- [ ] Does this feature access, store, or process PHI?
- [ ] Is all PHI encrypted at rest?
- [ ] Does this require network communication?
  - If YES: Can it be made local-only?
  - If NO: Proceed with caution, document why
- [ ] Are audit logs implemented for PHI access?
- [ ] Can this feature work offline?
- [ ] Is there a data retention policy?
- [ ] Has threat modeling been done?
- [ ] Is user consent obtained for data collection?
- [ ] Can user delete their data completely?
- [ ] Are there any third-party dependencies?
  - If YES: Are they HIPAA-compliant?
- [ ] Is this feature documented in security review?

---

## Prohibited Practices

### ❌ NEVER Do These:

1. **External API Calls with PHI**
   ```python
   # ❌ FORBIDDEN
   requests.post("https://api.example.com", json={"user_message": phi_data})
   
   # ✅ ALLOWED
   local_llm.generate(phi_data)  # In-process only
   ```

2. **Unencrypted Storage**
   ```python
   # ❌ FORBIDDEN
   with open("conversations.txt", "w") as f:
       f.write(user_conversation)
   
   # ✅ ALLOWED
   encrypted_db.insert(encrypt(user_conversation))
   ```

3. **Cloud Storage**
   ```python
   # ❌ FORBIDDEN
   upload_to_s3(user_data)
   sync_to_cloud(memories)
   
   # ✅ ALLOWED
   local_storage.save(encrypted_data)
   ```

4. **Telemetry/Analytics**
   ```python
   # ❌ FORBIDDEN
   analytics.track("user_emotion", {"mood": "sad", "context": message})
   
   # ✅ ALLOWED
   local_logger.info("Emotion detected")  # No PHI in logs
   ```

5. **Insecure Logging**
   ```python
   # ❌ FORBIDDEN
   print(f"User said: {user_message}")
   logger.debug(f"Processing: {phi_data}")
   
   # ✅ ALLOWED
   logger.info("Processing user input")  # No PHI details
   secure_audit_log.record(encrypted_phi, action="process")
   ```

6. **Third-Party Services**
   ```python
   # ❌ FORBIDDEN
   openai.chat.completions.create(messages=[{"role": "user", "content": phi}])
   anthropic.messages.create(messages=[phi_conversation])
   
   # ✅ ALLOWED
   local_llm.generate(phi_data)  # In-process model only
   ```

---

## Mental Health Specific Requirements

### Emotional Data Protection
```
REQUIREMENT: Emotional state data is highly sensitive PHI
IMPLEMENTATION:
  - Treat mood/emotion logs as medical records
  - Encrypt emotional state database
  - No external sentiment analysis APIs
  - Local emotion detection only
  - User can delete emotional history
```

### Crisis Detection
```
REQUIREMENT: Detect crisis situations while maintaining privacy
IMPLEMENTATION:
  - Local pattern matching (no cloud AI)
  - User-controlled crisis settings
  - Encrypted crisis logs
  - Local emergency resources only
  - No automatic reporting to third parties
```

### Therapeutic Context
```
REQUIREMENT: Maintain therapeutic conversation history securely
IMPLEMENTATION:
  - Encrypted long-term memory
  - Secure session notes
  - User-controlled memory retention
  - Export capability (encrypted)
  - Complete deletion capability
```

### Medication/Treatment Tracking
```
REQUIREMENT: If added, must be highly secured
IMPLEMENTATION:
  - Encrypted medication logs
  - No sharing with pharmacies/providers
  - User-only access
  - Secure reminders (no cloud)
  - Audit trail for access
```

---

## Implementation Roadmap

### Phase 2 (Current): Core Security
```
Priority: HIGH
Timeline: Next 2-4 weeks

Tasks:
  1. Implement encrypted storage for conversations
     - Use SQLCipher for SQLite encryption
     - AES-256-GCM for file encryption
     - Argon2id for key derivation
  
  2. Add encrypted RAG/memory storage
     - Encrypt vector embeddings
     - Encrypt metadata
     - Secure ChromaDB/Qdrant setup
  
  3. Create audit logging system
     - Immutable log structure
     - Encrypted audit logs
     - User-accessible audit viewer
  
  4. Implement secure user profiles
     - Encrypted user database
     - Secure password hashing
     - Session management
```

### Phase 3: Advanced Security
```
Priority: MEDIUM
Timeline: 1-2 months

Tasks:
  1. End-to-end encryption for all PHI
  2. Secure backup/restore system
  3. Data retention policies
  4. Secure deletion (crypto shredding)
  5. Access control system
  6. Multi-factor authentication (optional)
```

### Phase 4: Compliance Certification
```
Priority: MEDIUM
Timeline: 3-6 months

Tasks:
  1. Complete HIPAA Security Rule compliance
  2. Complete HIPAA Privacy Rule compliance
  3. Document compliance measures
  4. Third-party security audit
  5. Penetration testing
  6. Compliance certification (if needed)
```

---

## Code Review Guidelines

### Security Review Questions

For every pull request/feature:

1. **Data Flow Analysis**
   - Where does data come from?
   - Where does data go?
   - Is it encrypted in transit?
   - Is it encrypted at rest?

2. **Third-Party Risk**
   - Any new dependencies?
   - Are they audited/trusted?
   - Do they access PHI?
   - Can we eliminate them?

3. **Attack Surface**
   - Does this expose new endpoints?
   - Does this add network communication?
   - Does this add new file I/O?
   - Does this add new user inputs?

4. **Encryption Verification**
   - Is PHI encrypted before storage?
   - Are encryption keys secured?
   - Is key rotation supported?
   - Is crypto library up-to-date?

5. **Audit Trail**
   - Is PHI access logged?
   - Are logs immutable?
   - Are logs encrypted?
   - Can logs be reviewed by user?

---

## Encryption Standards

### Required Algorithms
```
File Encryption:    AES-256-GCM
Database:           SQLCipher (AES-256)
Key Derivation:     Argon2id (OWASP params)
Hashing:            SHA-256 (integrity), Argon2id (passwords)
Key Storage:        OS Keychain/Credential Manager
```

### Key Management
```python
# Key derivation from user password
from argon2 import PasswordHasher
ph = PasswordHasher(
    time_cost=3,        # OWASP recommendation
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16
)
key = ph.hash(user_password)

# File encryption
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
cipher = AESGCM(key)
encrypted = cipher.encrypt(nonce, plaintext, associated_data)

# Database encryption
import sqlcipher
conn = sqlcipher.connect("data.db")
conn.execute(f"PRAGMA key = '{key}'")
```

---

## Testing Requirements

### Security Test Cases

Every feature must have:

1. **Encryption Tests**
   - Verify data is encrypted at rest
   - Verify encryption keys are secured
   - Verify crypto algorithms are correct

2. **Access Control Tests**
   - Verify unauthorized access is blocked
   - Verify audit logs are created
   - Verify user permissions work

3. **Data Leakage Tests**
   - Verify no PHI in logs
   - Verify no PHI in errors
   - Verify no PHI in temp files
   - Verify memory is cleared

4. **Integration Tests**
   - Verify end-to-end encryption
   - Verify secure data flow
   - Verify no external calls with PHI

---

## Incident Response Plan

### If Security Breach Detected:

1. **Immediate Actions**
   - Isolate affected systems
   - Preserve evidence (logs, memory dumps)
   - Assess scope of breach
   - Notify security team

2. **Investigation**
   - Identify root cause
   - Determine what data was accessed
   - Identify affected users
   - Document timeline

3. **Remediation**
   - Patch vulnerability
   - Rotate encryption keys
   - Force password resets if needed
   - Update security measures

4. **Notification**
   - Notify affected users (required by HIPAA)
   - Document breach for compliance
   - Report to authorities if required
   - Provide remediation steps to users

---

## Resources

### HIPAA References
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [HIPAA Privacy Rule](https://www.hhs.gov/hipaa/for-professionals/privacy/index.html)
- [OCR Security Risk Assessment Tool](https://www.healthit.gov/topic/privacy-security-and-hipaa/security-risk-assessment-tool)

### Encryption Libraries
- cryptography.io (Python)
- SQLCipher (Encrypted SQLite)
- Argon2 (Key derivation)

### Compliance Tools
- NIST Cybersecurity Framework
- OWASP ASVS (Application Security Verification Standard)
- CIS Controls

---

## Version History

- **v1.0** (2026-01-10): Initial framework established
  - Defined core principles
  - Documented current status
  - Created roadmap
  - Established prohibited practices

---

**Remember: When in doubt, assume it's PHI and protect it accordingly.**
