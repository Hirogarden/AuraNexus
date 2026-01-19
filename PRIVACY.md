# Privacy & Security in AuraNexus

## Core Principle: Your Data Stays With You

AuraNexus is built on a simple principle: **your conversations and data should never leave your computer without your explicit consent.**

## Key Privacy Features

### 1. Fully Offline Operation
- No cloud synchronization
- No analytics or telemetry
- No "phone home" functionality
- Works completely without internet after initial setup

### 2. Local AI Processing
- All AI inference runs on your device using llama.cpp
- No API calls to external services (OpenAI, Anthropic, etc.)
- No data transmitted over the network during normal operation
- Model files stored locally

### 3. Local Data Storage
- Conversations stored in local SQLite database
- Memory indices kept in local vector store
- No cloud backups unless you explicitly create them
- All data resides in your user profile directory

### 4. Optional Encryption at Rest
Enable AES-256-GCM encryption for stored conversations:

```python
# In your configuration
encryption:
  enabled: true
  algorithm: "AES-256-GCM"
  key_derivation: "PBKDF2-SHA256"
```

This encrypts:
- All conversation history
- Stored memories and context
- User preferences and settings

### 5. No User Accounts
- No registration required
- No login credentials to manage
- No password that could be compromised
- No email collection

### 6. No Network Permissions Required
The application requests minimal permissions and never needs:
- Network access for normal operation
- Camera or microphone access
- Location services
- Contact list access

## What Data Does AuraNexus Store?

### Stored Locally
- **Conversations:** Your chat history with the AI
- **Memories:** Context and preferences learned over time
- **Settings:** UI preferences, model configuration
- **Temporary Files:** Model cache, embeddings cache

### Never Stored
- Personally identifiable information (unless you provide it in conversation)
- Usage analytics or telemetry
- Crash reports (without your permission)
- Any data sent to third parties

## Security Best Practices

### For Users

1. **Enable Encryption:** Turn on conversation encryption in settings
2. **Use Strong Models:** Larger models are generally more reliable and secure
3. **Regular Backups:** Backup your data folder to prevent data loss
4. **Keep Updated:** Install updates for security patches
5. **Review Conversations:** Periodically review stored conversations

### For Developers

1. **No External Calls:** Never add features that send data externally
2. **Encrypt Sensitive Data:** Use the encryption layer for all stored data
3. **Secure Defaults:** Privacy-preserving options should be the default
4. **Audit Logs:** Log access to sensitive functionality
5. **Security Reviews:** All PRs reviewed for privacy implications

## Threat Model

### What AuraNexus Protects Against

✅ **Cloud data breaches** - No cloud storage means no cloud breach
✅ **Network sniffing** - No data transmitted to intercept
✅ **Service shutdowns** - Fully offline, no dependencies
✅ **Terms of service changes** - You own your data
✅ **AI provider policy changes** - No external AI services

### What AuraNexus Does NOT Protect Against

❌ **Physical device theft** - Enable disk encryption at OS level
❌ **Malware on your system** - Use antivirus and keep OS updated
❌ **Compromised model files** - Only download models from trusted sources
❌ **Social engineering** - Don't share your device access

## Encryption Details

When encryption is enabled:

**Algorithm:** AES-256-GCM (Galois/Counter Mode)
**Key Derivation:** PBKDF2-SHA256 with 100,000 iterations
**Salt:** Randomly generated 32-byte salt per database
**Nonce:** Unique 12-byte nonce per encrypted field

This provides:
- Confidentiality (data is encrypted)
- Authenticity (tamper detection)
- Integrity (modification detection)

## Transparency

AuraNexus is fully open source. You can:
- Review the entire codebase
- Audit the security implementation
- Verify no telemetry exists
- Build from source yourself
- Fork and modify as needed

## Privacy Policy Summary

We don't have a privacy policy because we don't collect any data.

No data collection = No privacy policy needed.

## Questions?

If you have questions about privacy or security:
- Open an issue on GitHub
- Review the source code
- Check the documentation
- Ask in community discussions

---

**Remember:** The best privacy protection is keeping your data on your device, encrypted, and never sending it anywhere. That's the AuraNexus way.
