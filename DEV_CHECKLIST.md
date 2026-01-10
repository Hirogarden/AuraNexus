# AuraNexus Development Checklist
## Quick reference for maintaining HIPAA compliance

---

## ✅ Before Starting ANY Coding Session

- [ ] Read the latest SESSION_SUMMARY (check for newest date)
- [ ] Review [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)
- [ ] Check Phase status (1=Complete, 2=In Progress, 3=Planned)

---

## ✅ Before Implementing ANY Feature

- [ ] Read [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) relevant sections
- [ ] Open [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) in separate tab
- [ ] Review [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md) for process
- [ ] Complete all checklist items as you code
- [ ] Keep [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md) visible

---

## ✅ While Coding

**NEVER do these (see HIPAA_COMPLIANCE.md "Prohibited Practices"):**
- [ ] ❌ External API calls with PHI
- [ ] ❌ Unencrypted storage of PHI
- [ ] ❌ PHI in logs or errors
- [ ] ❌ Cloud storage or services
- [ ] ❌ Telemetry/analytics with PHI
- [ ] ❌ Third-party services with PHI

**ALWAYS do these:**
- [ ] ✅ In-process LLM only (llm_manager)
- [ ] ✅ Encrypt before storing (crypto.py in Phase 2)
- [ ] ✅ Safe logging (no PHI details)
- [ ] ✅ Local storage only
- [ ] ✅ Audit logging (Phase 2)
- [ ] ✅ Input validation

---

## ✅ Before Committing Code

- [ ] All [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) items complete
- [ ] No prohibited patterns in code (grep check)
- [ ] Security tests written and passing
- [ ] No PHI in logs verified
- [ ] Code reviewed by another developer (if available)

**Quick security grep checks:**
```powershell
# Check for prohibited patterns
grep -r "import requests" electron-app/backend/
grep -r "import openai" electron-app/backend/
grep -r "import anthropic" electron-app/backend/
grep -r "\.post\(" electron-app/backend/  # Look for HTTP posts
```

---

## ✅ Commit Message Format

```
type: Short description

HIPAA Compliance:
- Security measure 1
- Security measure 2

Changes:
- Change 1
- Change 2

Testing:
- Test 1 passed
- Security test passed
```

---

## ✅ After Implementing Feature

- [ ] Run all tests: `pytest electron-app/tests/ -v`
- [ ] Run security tests specifically
- [ ] Review audit logs (Phase 2)
- [ ] Update documentation if needed
- [ ] Mark SECURITY_CHECKLIST as complete
- [ ] Get second-person security review

---

## ✅ Phase-Specific Checks

### Phase 1 (Complete ✅)
- [x] In-process LLM working
- [x] Async architecture working
- [x] No external APIs for PHI
- [x] Documentation complete

### Phase 2 (Next - In Progress 🔄)
When implementing Phase 2:
- [ ] Install: `pip install -r requirements-phase2.txt`
- [ ] SQLCipher encryption working
- [ ] Separate databases (mental_health_db, general_db)
- [ ] Crypto shredding tested
- [ ] Audit logging functional
- [ ] Observer mode implemented
- [ ] Consent system implemented
- [ ] All data encrypted at rest

### Phase 3 (Planned 📋)
- [ ] E2E encryption
- [ ] Access controls
- [ ] MFA (optional)
- [ ] Backup/restore

---

## ✅ Language Guidelines (Peer Support)

When writing user-facing text:
- [ ] ❌ Avoid: "I've been there" / "I know how you feel"
- [ ] ✅ Use: "I understand the struggle" / "Your experience is unique"
- [ ] Acknowledge differences while offering empathy
- [ ] "While our journeys differ..." construction

---

## 🚨 Red Flags - Stop Immediately

If you see any of these in code review:
- 🚨 `requests.post()` or any HTTP library with PHI
- 🚨 `open("file.txt", "w")` without encryption
- 🚨 `logger.debug(f"User said: {message}")`
- 🚨 `import openai` or `import anthropic`
- 🚨 Cloud service imports (`boto3`, `firebase`, etc.)

**Action:** Review [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) "Prohibited Practices" section

---

## 📞 When In Doubt

1. Check [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md)
2. Search [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md)
3. Review [COMPLIANCE_DOCS_INDEX.md](./COMPLIANCE_DOCS_INDEX.md)
4. Assume it's PHI and protect accordingly
5. Request security review

---

## 🎯 Success Criteria

Your feature is ready when:
- [ ] All SECURITY_CHECKLIST items checked
- [ ] No prohibited patterns
- [ ] Security tests pass
- [ ] Works offline
- [ ] PHI encrypted (Phase 2+)
- [ ] Audit logs present (Phase 2+)
- [ ] Code reviewed
- [ ] Documentation updated

---

**Remember: Security is not optional. Every feature must maintain HIPAA compliance.**

---

*Keep this checklist handy during all development sessions*
*Last updated: 2026-01-10*
