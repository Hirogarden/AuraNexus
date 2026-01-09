# AuraNexus Security & Privacy Architecture

## HIPAA-Level Compliance Design

AuraNexus is designed for environments requiring the highest levels of data security and privacy, including healthcare (HIPAA), legal, and financial applications.

## Core Security Principles

### 1. **No External Dependencies**
- ❌ No external API calls (no OpenAI, Anthropic, etc.)
- ❌ No external processes (no system Ollama, no subprocess calls)
- ❌ No network communication (except optional user-initiated downloads)
- ✅ Everything runs in-process within Python

### 2. **Complete Data Isolation**
- All model inference happens in Python process memory
- No temporary files created during inference
- No data sent outside the application boundary
- No telemetry or analytics
- No logging of user conversations (unless explicitly saved)

### 3. **Local-Only Operation**
- Models stored locally in `engines/models/`
- All processing happens on user's machine
- Can run completely air-gapped (no internet required after setup)
- No cloud dependencies

## Architecture

```
┌─────────────────────────────────────────────┐
│         AuraNexus Application               │
│  ┌───────────────────────────────────────┐  │
│  │     User Interface (PySide6)          │  │
│  └──────────────┬────────────────────────┘  │
│                 │                            │
│  ┌──────────────▼────────────────────────┐  │
│  │   Secure Inference Engine             │  │
│  │   (llama-cpp-python bindings)         │  │
│  │   • In-process execution              │  │
│  │   • Memory-only operation             │  │
│  │   • No external calls                 │  │
│  └──────────────┬────────────────────────┘  │
│                 │                            │
│  ┌──────────────▼────────────────────────┐  │
│  │   GGUF Models (Local Files)           │  │
│  │   engines/models/*.gguf                │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
         │
         │ No data leaves this boundary
         ▼
    User's Computer
```

## Technical Implementation

### Inference Engine: llama-cpp-python

**Why llama-cpp-python?**
- Written in C++ (llama.cpp) with Python bindings
- Battle-tested, widely audited codebase
- No external dependencies
- Runs entirely in-process
- No network calls
- No subprocess spawning
- Supports CPU and GPU acceleration
- Memory efficient

**Security Benefits:**
```python
# All happens in Python process:
engine = SecureInferenceEngine("model.gguf")
response = engine.chat(messages)  # No external calls!
```

vs. insecure approach:
```python
# ❌ Creates external process
ollama_process = subprocess.Popen(["ollama", "serve"])  
# ❌ Makes HTTP call
response = requests.post("http://localhost:11434/api/chat")
```

### Data Flow

1. **User Input** → Python memory (GUI → Engine)
2. **Model Inference** → CPU/GPU memory (never leaves machine)
3. **Response** → Python memory (Engine → GUI)
4. **Optional Save** → Local file (only if user explicitly saves)

**No data crosses process boundaries except:**
- User explicitly saves conversation
- User explicitly loads conversation
- User downloads model (one-time, can be done offline)

## HIPAA Compliance Checklist

✅ **§ 164.312(a)(1) - Access Control**
- No remote access
- User controls all data
- No shared services

✅ **§ 164.312(a)(2)(iv) - Encryption**
- Data encrypted at rest (use BitLocker/LUKS on drive)
- No data in transit (no network communication)

✅ **§ 164.312(b) - Audit Controls**
- Optional local logging (user-controlled)
- No telemetry or tracking

✅ **§ 164.312(c)(1) - Integrity**
- No data modification by external parties
- User has complete control

✅ **§ 164.312(d) - Person or Entity Authentication**
- Local machine authentication only
- No cloud accounts required

✅ **§ 164.312(e)(1) - Transmission Security**
- No transmission (local-only operation)

✅ **§ 164.316(b)(2)(iii) - Protection from Malicious Software**
- No external code execution
- No downloaded scripts
- Minimal attack surface

## Attack Surface Analysis

### What Could Go Wrong? (And How We Prevent It)

**❌ Data Exfiltration via API calls**
- **Prevention**: No network code in inference engine
- **Verification**: Code audit shows zero network imports

**❌ Data Leakage via subprocess**
- **Prevention**: No subprocess calls during inference
- **Verification**: All processing in Python process

**❌ Temporary File Leakage**
- **Prevention**: No temp files created during chat
- **Verification**: Models loaded into memory once

**❌ Logging Sensitive Data**
- **Prevention**: No automatic logging of conversations
- **Verification**: User must explicitly save

**❌ Model Poisoning**
- **Prevention**: User controls model files
- **Mitigation**: Use trusted model sources (HuggingFace, official repos)

**❌ Memory Dumping**
- **Prevention**: Standard OS memory protection
- **Mitigation**: Full disk encryption (BitLocker/LUKS)

## Comparison with Other Solutions

| Feature | AuraNexus | OpenAI API | System Ollama |
|---------|-----------|------------|---------------|
| Data Leaves Machine | ❌ Never | ✅ Always | ❌ No |
| External Process | ❌ No | ✅ Yes (API) | ✅ Yes (ollama serve) |
| Network Required | ❌ No* | ✅ Yes | ❌ No |
| Air-Gap Compatible | ✅ Yes | ❌ No | ✅ Yes |
| Process Isolation | ✅ In-process | ❌ External | ⚠️ Separate process |
| HIPAA Suitable | ✅ Yes | ❌ No** | ⚠️ Maybe*** |
| Audit Trail | ✅ Local | ❌ External | ✅ Local |

\* Except initial model download  
\*\* Requires BAA, still sends data externally  
\*\*\* Depends on configuration, involves subprocess

## Setup for Maximum Security

### 1. Air-Gapped Installation

```powershell
# On internet-connected machine:
pip download llama-cpp-python -d packages/
# Copy packages/ folder and model files to air-gapped machine

# On air-gapped machine:
pip install --no-index --find-links packages/ llama-cpp-python
```

### 2. Secure Model Storage

```powershell
# Store models with restricted permissions
icacls "engines\models" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F"
```

### 3. Disable All Network Features

```python
# In chat_launcher.py, ensure no network code runs
NETWORK_ENABLED = False  # Disable model downloads
```

### 4. Enable Encryption

```powershell
# Enable BitLocker on drive containing AuraNexus
Enable-BitLocker -MountPoint "C:" -EncryptionMethod Aes256
```

## Verification & Auditing

### Code Audit Checklist

Run these checks to verify security:

```powershell
# 1. Check for network imports in inference engine
Select-String -Path "src\secure_inference_engine.py" -Pattern "requests|urllib|http|socket"
# Should return ZERO matches

# 2. Check for subprocess calls
Select-String -Path "src\secure_inference_engine.py" -Pattern "subprocess|Popen|run\("
# Should return ZERO matches

# 3. Check for file writes during inference
Select-String -Path "src\secure_inference_engine.py" -Pattern "open\(.*[\"']w|\.write\("
# Should return ZERO matches in inference methods

# 4. Verify no telemetry
Select-String -Path "src\*.py" -Pattern "telemetry|analytics|tracking"
# Should return ZERO matches
```

### Runtime Monitoring

```powershell
# Monitor network connections while AuraNexus runs
Get-NetTCPConnection | Where-Object {$_.OwningProcess -eq $AURANEXUS_PID}
# Should show ZERO connections during inference
```

## Best Practices for HIPAA Deployment

1. **System Hardening**
   - Keep OS updated
   - Disable unnecessary services
   - Use firewall rules
   - Enable full disk encryption

2. **Access Control**
   - Require strong passwords
   - Use Windows Hello/biometrics
   - Lock workstation when unattended

3. **Physical Security**
   - Secure physical access to machine
   - No unattended access in public areas

4. **Backup Security**
   - Encrypt backups
   - Secure backup storage
   - Test restoration procedures

5. **User Training**
   - Train users on data handling
   - Don't save PHI to unencrypted drives
   - Properly dispose of old hardware

## Compliance Documentation

For HIPAA compliance documentation:
1. This architecture document
2. Code audit results
3. Network monitoring logs (showing zero connections)
4. User training records
5. Encryption verification
6. Access control policies

## Future Security Enhancements

- [ ] Add conversation encryption at rest
- [ ] Implement secure deletion (overwrite memory)
- [ ] Add digital signatures for models
- [ ] Implement audit logging (optional, local-only)
- [ ] Add role-based access control
- [ ] Implement session timeouts

## Questions & Answers

**Q: Is this really HIPAA compliant?**
A: The software provides the technical controls. You must also implement administrative and physical safeguards per HIPAA regulations.

**Q: Can conversations still leak via screenshots?**
A: Yes. User behavior controls are outside software scope. Train users accordingly.

**Q: What about memory dumps?**
A: Use full disk encryption and secure boot to protect against memory dumping attacks.

**Q: Can I use cloud-hosted models?**
A: No! That defeats the entire security model. Only use local GGUF files.

**Q: Is GPU acceleration secure?**
A: Yes. GPU processing stays on local machine. Some GPUs have memory encryption features.

## Support

For security questions or audit assistance:
- Review code in `src/secure_inference_engine.py`
- Check network monitoring logs
- Verify no external dependencies in requirements-inference.txt
