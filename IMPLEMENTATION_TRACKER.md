# AuraNexus Implementation Tracker
**Auto-generated from REPO_MAPPING.md**  
**Date:** 2026-01-17

Quick reference for which repos to use for each AuraNexus feature.

---

## 🎯 Current Sprint: Model Management (Phase 1)

### Step 2: Model Downloader
**Reference Repos:**
- `C:\Users\hirog\Repos\1-LLM-Inference\gpt4all\gpt4all-chat\src\download.cpp`
  - Resumable HTTP downloads
  - Range requests (`bytes=X-`)
  - SHA256 hash verification
  - Progress events
  
**Rust Crates Needed:**
- reqwest (streaming)
- sha2 (hashing)  
- tokio (async)

**Implementation Time:** 2-3 hours

---

### Step 3: Enhanced Model Info (GGUF Metadata)
**Reference Repos:**
- `C:\Users\hirog\Repos\1-LLM-Inference\llama.cpp\gguf-py\gguf\`
  - GGUF format parser
  - Metadata extraction

**Rust Crates Needed:**
- Custom GGUF parser or bindings to llama.cpp

**Implementation Time:** 2-3 hours

---

## 🏥 Phase 2: Healthcare Features

### Feature 1: Patient Card System
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Narratium.ai\
  src/components/character/ → Card UI components
  
C:\Users\hirog\Repos\6-SillyTavern-Ecosystem\character-card-spec-v2\
  spec.md → Format specification
  
C:\Users\hirog\Repos\9-Utilities\Character-Card\
  API usage examples
```

**Implementation Steps:**
1. PNG parser (read tEXt chunk with "chara" keyword)
2. Base64 decode embedded JSON
3. Parse SillyTavern v2 format
4. Map to PatientCard struct
5. UI for import/export

**Files to Create:**
- `tauri-app/src-tauri/src/patient_card.rs`
- `tauri-app/src/components/PatientCard.tsx`

**Implementation Time:** 2-3 days

---

### Feature 2: Memory System (Per-Patient)
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Inner-Self\
  memory/ → Segmented memory architecture
  brain/ → Self-organizing structure
  
C:\Users\hirog\Repos\3-Memory-RAG\mem0\
  Simpler persistence layer (if Inner-Self too complex)
```

**Implementation Steps:**
1. Per-patient conversation isolation
2. Short-term memory (recent messages)
3. Long-term memory (visit summaries)
4. Core memory (allergies, chronic conditions)
5. Auto-summarization on session end

**Files to Create:**
- `tauri-app/src-tauri/src/patient_memory.rs`
- Update `memory.rs` with isolation

**Implementation Time:** 3-4 days

---

### Feature 3: Entity Extraction
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Auto-Cards\
  extraction/ → Entity detection patterns
  medical/ → Clinical term recognition
```

**Implementation Steps:**
1. Real-time entity extraction (symptoms, meds, conditions)
2. Medical NER model integration
3. SOAP note field population
4. ICD-10 code suggestions

**Files to Create:**
- `tauri-app/src-tauri/src/clinical_extraction.rs`

**Implementation Time:** 4-6 days

---

### Feature 4: Auto-SOAP Notes
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\CharGen\
  src/agent/ → Planning-driven architecture
  src/tools/ → Tool system (SEARCH, ASK, REFLECT, COMPLETE)
```

**Implementation Steps:**
1. Port planning architecture to Rust
2. Create clinical tools:
   - SUBJECTIVE (extract symptoms, history)
   - OBJECTIVE (organize vitals, exam findings)
   - ASSESSMENT (formulate diagnosis)
   - PLAN (treatment, follow-up)
   - REFLECT_GAPS (completeness check)
   - COMPLETE_NOTE (finalize)
3. Task decomposition engine
4. LLM-driven tool selection
5. Forced optimization after each tool

**Files to Create:**
- `tauri-app/src-tauri/src/agent/mod.rs`
- `tauri-app/src-tauri/src/agent/tools.rs`
- `tauri-app/src-tauri/src/agent/planner.rs`

**Implementation Time:** 1 week

---

## 🌍 Phase 3: Advanced Features

### Feature 5: Treatment Visualization (React Flow)
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Narratium.ai\
  src/components/flow/ → React Flow integration
  src/store/conversation.ts → Branching conversation state
```

**Implementation Steps:**
1. Embed React app in Tauri window
2. Track treatment decision branches
3. Visualize patient journey as tree
4. Export pathway diagrams

**Files to Create:**
- `tauri-app/src/treatment-flow/` (React app)
- Tauri command bridge

**Implementation Time:** 3-4 days

---

### Feature 6: Plugin System
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Narratium.ai\
  public/plugins/ → Plugin architecture
  HOW_TO_ADD_PLUGINS.md → Documentation
```

**Implementation Steps:**
1. WebAssembly plugin loader
2. Sandboxed execution environment
3. Plugin API surface
4. Plugin marketplace UI

**Files to Create:**
- `tauri-app/src-tauri/src/plugins/mod.rs`
- `tauri-app/src-tauri/src/plugins/loader.rs`
- `tauri-app/src-tauri/src/plugins/api.rs`

**Implementation Time:** 4-5 days

---

### Feature 7: Multilingual Support
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Localized-Languages\
  languages/ → 200+ language definitions
  medical/ → Medical terminology preservation
```

**Implementation Steps:**
1. Language selection UI
2. Medical term translation database
3. Cultural sensitivity guidelines
4. Preserve clinical accuracy across languages

**Files to Create:**
- `tauri-app/src-tauri/src/i18n/mod.rs`
- `tauri-app/src-tauri/src/i18n/medical.rs`

**Implementation Time:** 2-3 days

---

### Feature 8: Progress Tracking
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Discovery-Journal\
  progress/ → Visual milestone indicators
  journal/ → Timeline tracking
```

**Implementation Steps:**
1. Treatment milestone definitions
2. Visual progress indicators (moon phases → checkpoints)
3. Patient journey timeline
4. Goal tracking

**Files to Create:**
- `tauri-app/src/components/ProgressTracker.tsx`

**Implementation Time:** 2-3 days

---

### Feature 9: Voice Accessibility
**Reference Repos:**
```
C:\Users\hirog\Repos\7-Voice-Audio\kokoro\
  inference/ → TTS model integration
  
C:\Users\hirog\Repos\7-Voice-Audio\misaki\
  g2p/ → Medical term pronunciation
  
C:\Users\hirog\Repos\6-SillyTavern-Ecosystem\Coqui-TTS\
  Alternative TTS option
```

**Implementation Steps:**
1. TTS model integration (Kokoro 82M)
2. Medical term G2P (Misaki)
3. Read clinical notes aloud
4. Multilingual voice support

**Files to Create:**
- `tauri-app/src-tauri/src/tts/mod.rs`

**Implementation Time:** 3-4 days

---

### Feature 10: Clinical Case Library
**Reference Repos:**
```
C:\Users\hirog\Repos\9-Utilities\Character-Card\
  API example code → GitHub API integration
  
C:\Users\hirog\Repos\9-Utilities\Narratium.ai\
  Case management UI patterns
```

**Implementation Steps:**
1. GitHub API client for case repository
2. Browse/filter cases by specialty
3. Import teaching cases
4. Create new cases from consultations
5. Share anonymized cases

**Files to Create:**
- `tauri-app/src-tauri/src/case_library.rs`
- `tauri-app/src/components/CaseLibrary.tsx`

**Implementation Time:** 2-3 days

---

## 📊 Progress Dashboard

### Phase 1: Model Management (Current)
- [x] Step 1: Model Scanner (COMPLETE)
- [ ] Step 2: Model Downloader (IN PROGRESS)
- [ ] Step 3: Enhanced Model Info
- [ ] Step 4: Model Conversion
- [ ] Step 5: Model Profiles
- [ ] Step 6: Model Marketplace

**Estimated Completion:** End of Week 2

---

### Phase 2: Healthcare Foundation
- [ ] Patient Card System (0%)
- [ ] Memory System (0%)
- [ ] Entity Extraction (0%)
- [ ] Auto-SOAP Notes (0%)
- [ ] Progress Tracking (0%)

**Estimated Completion:** End of Week 6

---

### Phase 3: Advanced Features
- [ ] Treatment Visualization (0%)
- [ ] Plugin System (0%)
- [ ] Multilingual Support (0%)
- [ ] Voice Accessibility (0%)
- [ ] Clinical Case Library (0%)

**Estimated Completion:** End of Week 12

---

## 🔍 Quick Lookup: "I need to implement X, which repo?"

| Feature | Primary Repo | Secondary Repo | Tertiary Repo |
|---------|--------------|----------------|---------------|
| Model downloads | gpt4all | ollama | - |
| Patient cards | Narratium.ai | character-card-spec-v2 | Character-Card |
| Memory system | Inner-Self | mem0 | MemGPT |
| Entity extraction | Auto-Cards | - | - |
| Auto-documentation | CharGen | Auto-Cards | Inner-Self |
| Treatment viz | Narratium.ai (React Flow) | - | - |
| Plugin system | Narratium.ai | script-pack-1 | STMP |
| Multilingual | Localized-Languages | - | - |
| Progress tracking | Discovery-Journal | - | - |
| Voice/TTS | kokoro | misaki | Coqui-TTS |
| Case library | Character-Card | Narratium.ai | - |
| Multi-agent | crewAI | autogen | MetaGPT |
| RAG/Vector DB | chromadb | mem0 | txtai |
| Prompts | awesome-chatgpt-prompts | Prompt-Engineering-Guide | - |
| Evaluation | lm-evaluation-harness | opencompass | - |
| Fine-tuning | litgpt | transformers | - |

---

## 📁 File Organization Plan

```
tauri-app/src-tauri/src/
├── main.rs (existing)
├── llm.rs (existing)
├── memory.rs (existing)
├── models.rs (existing - Step 1 complete)
├── downloader.rs (NEW - Step 2)
├── gguf_parser.rs (NEW - Step 3)
├── patient_card.rs (NEW - Phase 2)
├── patient_memory.rs (NEW - Phase 2)
├── clinical_extraction.rs (NEW - Phase 2)
├── agent/
│   ├── mod.rs
│   ├── planner.rs
│   ├── tools.rs
│   └── soap_generator.rs
├── plugins/
│   ├── mod.rs
│   ├── loader.rs
│   ├── api.rs
│   └── sandbox.rs
├── i18n/
│   ├── mod.rs
│   ├── medical.rs
│   └── languages.json
├── tts/
│   ├── mod.rs
│   ├── kokoro.rs
│   └── misaki.rs
└── case_library.rs

tauri-app/src/
├── components/
│   ├── PatientCard.tsx (NEW)
│   ├── ProgressTracker.tsx (NEW)
│   ├── CaseLibrary.tsx (NEW)
│   └── SoapEditor.tsx (NEW)
├── treatment-flow/ (NEW - React Flow app)
│   ├── FlowCanvas.tsx
│   ├── nodes/
│   └── edges/
└── ... (existing files)
```

---

## 🚀 Deployment Checklist

### Before Each Feature Release
- [ ] Check REPO_MAPPING.md for implementation details
- [ ] Review reference repo code
- [ ] Test with sample data
- [ ] Update HIPAA_COMPLIANCE.md if handling PHI
- [ ] Run security checklist
- [ ] Document in user-facing docs

### After Implementation
- [ ] Update IMPLEMENTATION_TRACKER.md progress
- [ ] Create demo video/screenshots
- [ ] Update README.md feature list
- [ ] Tag GitHub release

---

*Last Updated: 2026-01-17*  
*Next Review: After Phase 1 completion*
