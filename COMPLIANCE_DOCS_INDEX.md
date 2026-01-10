# AuraNexus - HIPAA Compliance Documentation Index
## Your guide to building secure, compliant mental health software

---

## 📚 Documentation Overview

This project maintains **strict HIPAA compliance** for handling Protected Health Information (PHI) in mental health support applications. All documentation works together to ensure security at every level.

---

## 🎯 Start Here

### If you're NEW to the project:
1. **[README.md](./README.md)** - Project overview, security features, quick start
2. **[HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md)** - Core security framework (MUST READ)
3. **[HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)** - Quick reference card
4. **[DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)** - How to build features securely

### If you're ADDING A FEATURE:
1. **[SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md)** - Complete this for every feature
2. **[DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)** - Follow the 5-phase process
3. **[HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)** - Keep handy while coding

### If you're REVIEWING CODE:
1. **[SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md)** - Verify all items checked
2. **[HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md)** - Check against prohibited practices
3. **[HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)** - Verify patterns used

---

## 📖 Document Purposes

### Core Security Documents

#### [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) 
**The Constitution - Complete Security Framework**
- Mission statement and compliance status
- HIPAA technical/physical/administrative safeguards
- Architectural principles (non-negotiable)
- Feature development checklist
- Prohibited practices (what never to do)
- Mental health specific requirements
- Implementation roadmap (Phases 1-4)
- Code review guidelines
- Encryption standards
- Testing requirements
- Incident response plan

**When to use:** 
- Before starting any new work
- When unsure about security requirements
- During code reviews
- When designing new features
- During security audits

---

#### [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md)
**Feature Development Checklist - 13 Sections**
- Pre-implementation review (data classification, architecture)
- Implementation checklist (code security, audit logging, access control)
- Testing checklist (security, integration, compliance)
- Documentation checklist
- Deployment checklist
- Common safe/unsafe patterns
- Sign-off section

**When to use:**
- For EVERY new feature (no exceptions)
- Before starting implementation
- During development (check off items)
- Before code review
- Before deployment

---

#### [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)
**Developer Quick Reference Card**
- 5 golden rules
- Never/always do code examples
- Before coding checklist
- Code review questions
- Current phase status
- Mental health specific notes
- Emergency reference

**When to use:**
- Daily development work
- Quick pattern lookups
- While writing code
- During debugging
- Keep this file open while coding

---

#### [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)
**Step-by-Step Feature Development Process**
- 5-phase workflow (Planning → Implementation → Testing → Review → Deployment)
- Security-focused code templates
- Red flags (stop and review)
- Green flags (approved patterns)
- Common development tasks
- Pre-commit checklist
- Phase 2 implementation guide
- Learning resources

**When to use:**
- When building new features
- When unsure of development process
- For code templates/examples
- Training new developers
- Planning feature implementation

---

### Architecture Documents

#### [electron-app/INPROCESS_LLM_ARCHITECTURE.md](./electron-app/INPROCESS_LLM_ARCHITECTURE.md)
**In-Process LLM Security Architecture**
- Why in-process is HIPAA-compliant
- Architecture comparison (external vs in-process)
- Component breakdown with diagrams
- Data flow visualization
- Configuration guide
- Memory requirements
- GPU acceleration
- Performance benchmarks
- Troubleshooting

**When to use:**
- Understanding LLM security
- Configuring models
- Performance optimization
- Troubleshooting LLM issues
- Explaining architecture to stakeholders

---

#### [electron-app/KOBOLDCPP_SETUP.md](./electron-app/KOBOLDCPP_SETUP.md)
**External KoboldCPP Setup (Non-Compliant)**
- KoboldCPP server setup (testing only)
- Model recommendations
- Configuration instructions
- Troubleshooting

**⚠️ WARNING:** 
- External mode is NOT HIPAA-compliant
- Use only for testing non-PHI data
- Never use in production with PHI

---

### Project Documents

#### [README.md](./README.md)
**Project Overview**
- Security features overview
- Quick start guide
- Installation instructions
- Project structure
- Current architecture
- Usage instructions

**When to use:**
- Project introduction
- Setup instructions
- Understanding project scope
- Showing project to stakeholders

---

## 🔐 Security Principles Summary

All documents reinforce these core principles:

### 1. **Data Containment**
- All PHI stays within application process
- No external APIs with PHI
- No cloud services
- Local-first architecture

### 2. **Encryption by Default**
- AES-256-GCM for all PHI at rest
- Argon2id for key derivation
- SQLCipher for databases
- Encrypted IPC between processes

### 3. **Zero Trust**
- Validate all inputs
- Sanitize all outputs
- No PHI in logs/errors
- Defense in depth

### 4. **Audit Everything**
- Log all PHI access
- Immutable audit logs
- User-accessible audit trail
- Encrypted audit logs

### 5. **Local First**
- Works 100% offline
- No internet required
- User controls their data
- No server dependencies

### 6. **Mental Health Focus**
- Emotional data = highly sensitive PHI
- Crisis detection (local only)
- Therapeutic context protection
- Medication tracking security

---

## 🚀 Implementation Phases

### ✅ Phase 1: Foundation (COMPLETE)
- In-process LLM (llama-cpp-python)
- Async architecture (no multiprocessing)
- No external APIs for PHI
- Basic security patterns established

### 🔄 Phase 2: Core Security (IN PROGRESS)
**Priority: HIGH - Next 2-4 weeks**

Tasks to implement:
1. **Encrypted Storage**
   - SQLCipher for database encryption
   - AES-256-GCM for file encryption
   - Secure key derivation with Argon2id

2. **Encrypted RAG/Memory**
   - Encrypt vector embeddings
   - Encrypt metadata
   - Local ChromaDB/Qdrant setup

3. **Audit Logging System**
   - Immutable log structure
   - Encrypted audit logs
   - User-accessible audit viewer

4. **User Profile Security**
   - Encrypted user database
   - Secure password hashing
   - Session management

**Files to create:**
- `electron-app/backend/crypto.py` - Encryption utilities
- `electron-app/backend/database.py` - SQLCipher integration
- `electron-app/backend/audit.py` - Audit logging
- `electron-app/backend/memory_manager.py` - Encrypted memory/RAG
- Tests for all new modules

### 📋 Phase 3: Advanced Security (PLANNED)
**Priority: MEDIUM - 1-2 months**

- End-to-end encryption for all PHI
- Secure backup/restore system
- Data retention policies
- Secure deletion (crypto shredding)
- Access control system
- Multi-factor authentication

### 📋 Phase 4: Compliance Certification (PLANNED)
**Priority: MEDIUM - 3-6 months**

- Complete HIPAA Security Rule compliance
- Complete HIPAA Privacy Rule compliance
- Third-party security audit
- Penetration testing
- Compliance certification

---

## 🎯 Quick Decision Tree

**Need to implement a feature?**
```
START
  ↓
Does it handle PHI? ──NO──→ Follow normal development
  ↓ YES
Read HIPAA_COMPLIANCE.md
  ↓
Complete SECURITY_CHECKLIST.md
  ↓
Follow DEVELOPMENT_WORKFLOW.md
  ↓
Use patterns from HIPAA_QUICK_REFERENCE.md
  ↓
Code review with security focus
  ↓
All checklist items complete? ──NO──→ Fix issues, return to checklist
  ↓ YES
Deploy with monitoring
  ↓
END
```

**Unsure if something is secure?**
```
START
  ↓
Check HIPAA_COMPLIANCE.md "Prohibited Practices" ──FOUND──→ DON'T DO IT
  ↓ NOT FOUND
Check HIPAA_QUICK_REFERENCE.md patterns ──FOUND GREEN FLAG──→ SAFE TO USE
  ↓ FOUND RED FLAG
DON'T DO IT
  ↓ NOT FOUND
Assume it's unsafe, ask for review
  ↓
END
```

---

## 📝 Development Templates

### New Feature Implementation

```python
"""
Feature: [NAME]
File: [PATH]
Developer: [NAME]
Date: [DATE]

PHI Handled: [Yes/No]
If Yes, types: [List]

Security Review:
- SECURITY_CHECKLIST.md: [Complete/In Progress]
- HIPAA_COMPLIANCE.md: [Reviewed/Compliant]
- Code Review By: [NAME]
- Date: [DATE]

SECURITY CONSIDERATIONS:
- [List key considerations]
- [List PHI protection measures]
- [List encryption methods]
- [List audit logging]
"""

# See DEVELOPMENT_WORKFLOW.md for full template
```

### Commit Message Template

```
feat|fix|security: [Short description]

HIPAA Compliance:
- [Security measure 1]
- [Security measure 2]
- [Reference to checklist/document]

Changes:
- [Change 1]
- [Change 2]

Testing:
- [Test 1 passed]
- [Security test passed]

Refs: #[Issue number if applicable]
```

---

## 🔍 Code Review Checklist

Reviewer should verify:

- [ ] SECURITY_CHECKLIST.md completed and signed
- [ ] No prohibited patterns (see HIPAA_COMPLIANCE.md)
- [ ] All PHI encrypted before storage
- [ ] No PHI in logs or errors
- [ ] No external API calls with PHI
- [ ] Audit logs implemented (Phase 2)
- [ ] Input validation present
- [ ] Security tests written and passing
- [ ] Works offline
- [ ] User can delete their data

---

## 🚨 Emergency Procedures

### If Security Breach Suspected:

1. **Immediate:** Isolate affected systems
2. **Document:** Preserve logs and evidence
3. **Assess:** Determine scope and data accessed
4. **Remediate:** Patch vulnerability, rotate keys
5. **Notify:** Follow incident response plan (HIPAA_COMPLIANCE.md)

### If Unsure About Security:

1. **STOP:** Don't commit/deploy
2. **Check:** HIPAA_COMPLIANCE.md and HIPAA_QUICK_REFERENCE.md
3. **Ask:** Request security review
4. **Document:** Write down concerns
5. **Decide:** Only proceed when certain

---

## 📊 Metrics & Tracking

### Current Status (2026-01-10)

**HIPAA Compliance Score: Phase 1 Complete**

| Category | Status | Progress |
|----------|--------|----------|
| In-Process LLM | ✅ Complete | 100% |
| No External APIs | ✅ Complete | 100% |
| Async Architecture | ✅ Complete | 100% |
| Encrypted Storage | 🔄 Phase 2 | 0% |
| Audit Logging | 🔄 Phase 2 | 0% |
| Access Control | 📋 Phase 3 | 0% |
| E2E Encryption | 📋 Phase 3 | 0% |

**Phase 2 Priorities:**
1. SQLCipher integration (HIGH)
2. Conversation encryption (HIGH)
3. Audit logging system (HIGH)
4. Memory/RAG encryption (HIGH)

---

## 🎓 Training Path

### Week 1: Foundations
- Day 1-2: Read all compliance docs
- Day 3-4: Study existing secure code
- Day 5: Practice with examples

### Week 2: Implementation
- Day 1-2: Implement small feature with checklist
- Day 3-4: Code review and fixes
- Day 5: Retrospective, lessons learned

### Week 3: Advanced
- Day 1-2: Design larger feature securely
- Day 3-5: Implement with security focus

### Week 4: Mastery
- Day 1-3: Review others' code
- Day 4-5: Document patterns, improve process

---

## 🔗 Quick Links

- **Core Docs:** [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) | [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) | [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)
- **Workflow:** [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)
- **Architecture:** [INPROCESS_LLM_ARCHITECTURE.md](./electron-app/INPROCESS_LLM_ARCHITECTURE.md)
- **Tests:** [test_inprocess_llm.py](./electron-app/test_inprocess_llm.py)

---

## 📞 Support & Questions

**For HIPAA questions:**
- Check [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) first
- Use [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md) for patterns
- Request security review if unsure

**For development questions:**
- Follow [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)
- Use [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md)
- Check code templates and examples

**For architecture questions:**
- See [INPROCESS_LLM_ARCHITECTURE.md](./electron-app/INPROCESS_LLM_ARCHITECTURE.md)
- Review existing implementations
- Ask for architectural review

---

## ✅ Success Criteria

**Your feature is ready when:**
- [ ] All SECURITY_CHECKLIST.md items checked
- [ ] No prohibited patterns used
- [ ] Security tests pass
- [ ] Works offline
- [ ] PHI encrypted (Phase 2)
- [ ] Audit logs present (Phase 2)
- [ ] Code review approved
- [ ] Documentation updated
- [ ] User can delete their data

---

**Remember: Security is not negotiable. Every feature must maintain HIPAA compliance.**

**When in doubt, protect user privacy first.**

---

*Last Updated: 2026-01-10*
*Version: 1.0*
*Maintained by: AuraNexus Security Team*
