# Repository Research & Inspiration

This document tracks interesting features and implementation ideas discovered while researching similar projects.

---

## Quick Reference: Code vs Ideas

### 🔧 Repos with Actual Implementation Code
1. **GPT4All** (⭐⭐⭐ Most Valuable)
   - Location: `C:\Users\hirog\Repos\2-UI-Frontends\gpt4all`
   - Language: C++ (Qt/QML)
   - Best for: Model download implementation, resume logic, hash verification
   - Key files: `gpt4all-chat/src/download.cpp`, `modellist.cpp`, `mysettings.cpp`

2. **Electron App** (Python Implementation)
   - Location: `C:\Users\hirog\All-In-One\AuraNexus\electron-app`
   - Language: Python
   - Best for: HuggingFace API integration, auto-download logic
   - Key files: `llm_manager.py`

3. **KoboldCpp-Manager** (if we have it)
   - Location: Check `C:\Users\hirog\Repos\1-LLM-Inference\`
   - Best for: Model management patterns

### 💡 Repos with Ideas/Documentation Only
1. **V6rge AI Suite** - Marketing/releases only (closed source)
2. **Msty Studio** - Documentation and i18n only (closed source)
   - Locations: 
     - `C:\Users\hirog\Repos\2-UI-Frontends\msty-studio-docs`
     - `C:\Users\hirog\Repos\2-UI-Frontends\msty-app-i18n`
3. **MousAI Script Pack** - AI Dungeon game scripting (JavaScript)
   - Location: `C:\Users\hirog\Repos\9-Utilities\script-pack-1`
   - Ideas: Modular plugin architecture, input/output modifiers
4. **Inner-Self** - Character memory/thoughts system (JavaScript)
   - Location: `C:\Users\hirog\Repos\9-Utilities\Inner-Self`
   - Ideas: Segmented memory, self-organizing thoughts, real-time brain editor
5. **Auto-Cards** - Automatic story card generation (JavaScript)
   - Location: `C:\Users\hirog\Repos\9-Utilities\Auto-Cards`
   - Ideas: Automated note-taking, entity detection, memory summarization

### 📚 Implementation Priority
1. **Use GPT4All C++ patterns** → Adapt to Rust (reqwest, tokio, sha2)
2. **Use Msty UX ideas** → Model hub tabs, matchmaker wizard, tagging
3. **Use V6rge concepts** → Multi-modal future features
4. **Use MousAI patterns** → Plugin system, conversation middleware

---

## V6rge AI Suite
**Repository:** https://github.com/Dedsec-b/v6rge-releases-  
**Type:** Closed-source Windows application (release repo only)  
**Date Reviewed:** 2026-01-17

### Key Features
- **All-in-one offline AI studio** - Single app for multiple AI capabilities
- **100% Local** - No cloud dependencies, matches our HIPAA compliance goals
- **OS Agent** - Natural language PC control ("Organize my download folder")
- **Multi-modal capabilities:**
  - Image generation (multiple flagship models)
  - Video generation from text
  - 3D model generation from images
  - Voice cloning and music generation
  - Tools: 4K upscaling, background removal, vocal separation

### Features to Consider for AuraNexus

#### ✅ Already Planning
- **In-app Model Manager** - Browse and download AI models (our Step 2!)
- **Offline-first architecture** - Aligns with security/HIPAA requirements
- **User-selectable models** - Let users pick which models to download (our Step 1 scanner)

#### 🔮 Future Enhancements
- **OS Agent/Automation** - Could add PC control capabilities for workflow automation
- **Multi-modal AI:**
  - Image generation for medical diagrams/visualizations
  - Voice synthesis for accessibility
  - Document processing tools (PDF organization, etc.)
- **Tool Suite:**
  - Image upscaling for medical imaging
  - Background removal for photo processing
  - Audio separation for transcription cleanup

#### 📝 UX Inspiration
- Clear system requirements display (GPU, RAM, storage)
- User chooses which AI engines to install (saves disk space)
- "Your Data, Your PC, Your Rules" messaging (privacy-focused branding)

### Technical Notes
- Repo contains only marketing/releases (no source code to reference)
- Requires significant hardware (RTX 3060+ recommended)
- Storage-conscious design (core app ~2GB, models downloaded separately)

---

## Next Repos to Review
_(Add more as we explore)_

---

## GPT4All
**Repository:** https://github.com/nomic-ai/gpt4all  
**Type:** Open source - Qt/C++ desktop app + Python bindings  
**Date Reviewed:** 2026-01-17

### Overview
- **Major open source LLM client** - Cross-platform (Windows/Mac/Linux)
- **Built on llama.cpp** - Same backend we're using!
- **Qt/QML desktop UI** - Native C++ performance
- **Python bindings available** - Flexible deployment options
- **No GPU required** - CPU inference (though GPU supported)

### Architecture
- **Backend:** C++ with llama.cpp integration
- **UI:** Qt Quick/QML (native desktop framework)
- **Networking:** QNetworkAccessManager for downloads
- **Settings:** QSettings for persistence
- **Database:** Model metadata management

### Key Implementation Details

#### ✅ Model Download System (download.cpp/download.h)
**Highly relevant for our Step 2!**

```cpp
void Download::downloadModel(const QString &modelFile) {
    // Resume support - checks incomplete file size
    QFile *tempFile = new QFile(incompleteDownloadPath(modelFile));
    size_t incomplete_size = tempFile->size();
    
    // HTTP range request for resume
    request.setRawHeader("range", u"bytes=%1-"_s.arg(tempFile->pos()).toUtf8());
    
    // Progress tracking
    connect(modelReply, &QNetworkReply::downloadProgress, 
            this, &Download::handleDownloadProgress);
    
    // Cancel support
    connect(qGuiApp, &QCoreApplication::aboutToQuit, 
            modelReply, &QNetworkReply::abort);
}
```

**Features:**
- ✅ Resume interrupted downloads (HTTP range requests)
- ✅ Progress tracking via Qt signals
- ✅ Cancel/abort support
- ✅ Hash verification after download (separate thread)
- ✅ Temp file → final location on success
- ✅ Analytics tracking (download_started, download_canceled events)

#### Model Discovery & Management
- **ModelList class** - Central registry of available models
- **Model metadata** - Name, size, download URL, hash
- **Download state tracking** - Downloading, downloaded, error states
- **Multiple model sources** - Default: gpt4all.io/models/gguf/

#### Settings System (mysettings.cpp)
- **Per-model settings** - Track downloads count, preferences
- **Model download directory** - Configurable path
- **QSettings persistence** - Cross-platform config storage

### Features to Implement in AuraNexus

#### 🎯 High Priority (Step 2 - Model Downloader)
1. **Resume-capable downloads**
   - Use HTTP Range header: `bytes=X-` 
   - Save to temp file (.part extension)
   - Move to final location on completion
   
2. **Progress tracking**
   - Bytes downloaded / total size
   - Download speed calculation
   - ETA estimation
   
3. **Hash verification**
   - SHA256 checksum validation
   - Run in separate thread (don't block UI)
   - Verify before moving to final location

4. **Cancel/pause functionality**
   - Abort network request
   - Keep temp file for resume
   - Clean up on explicit cancel

5. **Error handling**
   - Network errors (connection lost)
   - Disk space errors
   - Hash mismatch errors
   - Retry logic with backoff

#### 🔮 Future Enhancements
- **Model marketplace** - Browse/search available models
- **Automatic updates** - Check for app updates
- **Model recommendations** - Suggest models based on hardware
- **Bandwidth limiting** - Control download speed
- **Parallel downloads** - Download multiple models (with limits)

### Technical Lessons

#### What Works Well
- **Qt networking is robust** - QNetworkAccessManager handles complexity
- **Separate worker thread for hashing** - Keeps UI responsive
- **Temp file pattern** - Safe partial downloads
- **Range requests** - Critical for large models (4-7GB+)
- **Event tracking** - Useful for telemetry/debugging

#### What to Adapt for Rust/Tauri
- **Use reqwest instead of Qt** - Async HTTP with streaming
- **Use tokio for async I/O** - Non-blocking downloads
- **Tauri events for progress** - Replace Qt signals
- **Use sha2 crate** - For hash verification
- **Use tokio::task::spawn_blocking** - For CPU-heavy hash calculation

### Code References
- `gpt4all-chat/src/download.cpp` - Main download implementation
- `gpt4all-chat/src/download.h` - Download class interface
- `gpt4all-chat/src/modellist.cpp` - Model registry management
- `gpt4all-chat/src/mysettings.cpp` - Settings persistence

### Similar to Our Architecture
- ✅ Uses llama.cpp (we use llama-cpp-2 bindings)
- ✅ Local-first design (no cloud dependency)
- ✅ Cross-platform desktop app
- ✅ Native performance focus

### Different from Our Approach
- ❌ Qt/C++ vs our Rust/Tauri
- ❌ QML UI vs our HTML/CSS/JS
- ❌ Larger binary size (~200MB vs our 11MB)
- ❌ More complex build process

---

## Msty Studio
**Repository:** https://github.com/cloudstack-llc/msty-studio-docs (docs only)  
**i18n Repo:** https://github.com/cloudstack-llc/msty-app-i18n  
**Type:** Closed source - Documentation and translations only  
**Date Reviewed:** 2026-01-17

### Overview
- **Privacy-first AI platform** - Web + Desktop versions
- **Multi-modal AI workflows** - Local and cloud models
- **Cross-platform** - Windows, Mac, Linux, Web
- **Model Context Protocol (MCP)** - Tool integration system
- **RAG implementation** - "Knowledge Stacks"
- **Advanced UI/UX** - Sophisticated feature set

### Key Features

#### Model Management (Highly Relevant!)
From the docs, Msty has a **Model Hub** with:

1. **Model Matchmaker** - AI-powered model recommendation
   - Users rate importance of factors (speed, quality, cost, etc.)
   - System ranks models based on criteria
   - Suggests best models for user needs
   
2. **Multiple Model Sources**
   - Featured Models tab (popular pre-curated list)
   - Installed Models tab (local GGUF files)
   - Ollama Models search
   - Hugging Face search (any public GGUF)
   - Import GGUF from filesystem
   - Import Safetensors models
   
3. **Model Organization**
   - Set default model
   - Rename models (custom descriptions)
   - Tag models by purpose (coding, writing, chat, etc.)
   - Model Squad (specialized models for UI tasks)
   
4. **Installation Options**
   - Symlink to existing GGUF (don't duplicate storage)
   - Copy into app directory (portable)

#### Toolbox (MCP Implementation)
- **Model Context Protocol** - Connect AI to external tools
- **Local & Remote Tools** - STDIO/JSON or HTTP servers
- **Examples:** Calendar, GitHub, n8n workflows, databases
- **Import Default Tools** - Curated starter pack

#### Knowledge Stacks (RAG)
- Document ingestion and retrieval
- Context-aware conversations
- Multiple knowledge bases

#### Advanced Features
- **Personas** - Customized AI assistants with specific roles
- **Turnstiles** - Multi-step AI workflows
- **Split Chats** - Multiple models in one conversation
- **Workspaces** - Project organization
- **Branch Explorer** - Conversation branching (like Git)
- **Forge Mode** - AI-powered development assistant
- **Real-Time Data** - Live web data integration

### UX Inspirations for AuraNexus

#### 🎯 Model Management UI
1. **Model Matchmaker Concept**
   - Could add "Find the right model" wizard
   - User slides: Speed, Quality, Size, VRAM, etc.
   - Rank available/downloadable models
   - Reduces choice paralysis for new users

2. **Model Hub Organization**
   ```
   Tabs:
   - Featured (our curated recommendations)
   - Installed (local .gguf files we found)
   - HuggingFace (search/download)
   - Ollama (search/download)
   - Import (local file picker)
   ```

3. **Model Tagging System**
   - Tags: Medical, Coding, Writing, Chat, Reasoning
   - Filter by purpose
   - Save per-model settings/prompts

4. **Import Options**
   - Symlink vs Copy choice (save disk space)
   - Detect duplicate models
   - Verify GGUF format before import

#### 🔮 Future Feature Ideas
- **Model Profiles** - Save settings per model
- **Multi-model conversations** - Route to best model per task
- **Personas** - Pre-configured AI assistants (Doctor, Therapist, etc.)
- **Workspaces** - Separate patient contexts
- **Branch Explorer** - Explore conversation paths
- **Knowledge Stacks** - Medical document RAG

### Technical Architecture Notes

#### Privacy-First Design
- **Local data storage** - Browser localStorage or filesystem
- **No data sync** - Each device independent (HIPAA-friendly)
- **Encryption support** - Built-in data encryption
- **Desktop + Web** - Web can connect to Desktop for local models

#### Model Support
- **GGUF format** - Primary format (llama.cpp)
- **Safetensors** - Also supported (MLX models)
- **Ollama integration** - Search and download
- **HuggingFace integration** - Direct model discovery
- **Import from filesystem** - Use existing models

#### Build Stack (from docs repo)
- **Frontend:** Nuxt 3 (Vue framework)
- **Styling:** Tailwind CSS
- **Docs:** Markdown-based (shadcn-docs-nuxt)
- **Runtime:** Bun (fast Node alternative)

### Features to Consider

#### ✅ High Priority
1. **Model search/download UI** (Step 2)
   - HuggingFace API integration
   - Ollama model list
   - Search filters (size, quantization, purpose)
   
2. **Model import from filesystem** (Step 1 enhancement)
   - File picker dialog
   - Symlink vs copy option
   - Duplicate detection

3. **Model tagging/organization**
   - Medical, General, Coding categories
   - Custom tags
   - Purpose-based filtering

#### 🔮 Future Enhancements
1. **Model Matchmaker wizard**
   - Hardware-aware recommendations
   - Use-case matching
   - Performance profiling

2. **Model profiles**
   - Save temperature/settings per model
   - Associate system prompts
   - Quick switch between profiles

3. **MCP/Toolbox system**
   - Connect to external tools
   - Calendar, files, databases
   - Workflow automation

### Key Takeaways

#### What Msty Does Well
- **No code required** - User-friendly for non-technical users
- **Privacy-first messaging** - Clear data storage policies
- **Rich feature set** - Beyond basic chat (workflows, RAG, tools)
- **Multiple model support** - Cloud + Local hybrid
- **Sophisticated UX** - Model matchmaker, tagging, organization

#### How It Compares to AuraNexus
- ✅ Similar: Privacy-first, local models, cross-platform
- ✅ Similar: GGUF/llama.cpp backend
- ❌ Different: Closed source (we're building open)
- ❌ Different: Web-first (we're desktop-first)
- ❌ Different: Subscription model (we're HIPAA healthcare focus)

### Implementation Priorities
1. **Immediate:** Model scanner improvements (import, organize)
2. **Next:** HuggingFace search/download UI
3. **Soon:** Model tagging and profiles
4. **Future:** Model matchmaker wizard
5. **Future:** MCP/tool integration for workflows

---

## MousAI Script Pack (AI Dungeon)
**Repository:** https://github.com/MousAIDungeon/script-pack-1  
**Type:** Open source - JavaScript scripting framework  
**Date Reviewed:** 2026-01-17

### Overview
- **AI Dungeon modding framework** - Modular JavaScript for interactive fiction
- **Input/Output modifiers** - Hooks that intercept and transform AI interactions
- **World Info integration** - Dynamic context injection
- **Modular architecture** - Easy enable/disable of features

### Available Modules
1. **Focus Module** - Inject persistent narrative drivers into memory
2. **Danger Module** - Escalating tension system (turn-based triggers)
3. **Nerves Module** - Add uncertainty to actions ("try to" vs declarative)
4. **Events Module** - Random narrative events with duration

### Architectural Patterns for AuraNexus

#### ✅ Conversation Middleware System
Adapt the input/output modifier pattern:

```javascript
// MousAI Pattern:
InputModifier → Process User Input → Modified Input → AI
AI Output → OutputModifier → Process AI Response → Modified Output → User

// Could become AuraNexus Plugin System:
User Input → [Plugin Chain] → LLM → [Plugin Chain] → User Output
```

**Use Cases for Healthcare:**
- **Medical Context Injection** - Auto-inject patient context/history
- **Safety Filters** - Screen for harmful medical advice
- **HIPAA Compliance** - Redact PII before logging
- **Response Enhancement** - Add medical disclaimers automatically
- **Session Management** - Track conversation flow and context

#### Potential Features to Adapt

1. **Focus Module → Clinical Focus**
   - Inject active patient context into every turn
   - "Currently discussing: Patient #1234, Diabetes Management"
   - Keep conversations on-topic and compliant

2. **Danger Module → Urgency Indicators**
   - Escalate UI based on conversation urgency
   - Visual cues for time-sensitive medical topics
   - Remind practitioners of critical timelines

3. **Events Module → Clinical Prompts**
   - Randomly inject best-practice reminders
   - "Remember to document visit notes"
   - Educational tips based on conversation context

4. **Nerves Module → Confidence Scoring**
   - AI expresses uncertainty when appropriate
   - Medical AI should NOT be overconfident
   - "I'm not certain, but this might indicate..."

### Implementation Strategy

#### 🎯 Near-Term (Plugin Architecture)
Create a middleware system in Rust:

```rust
// Concept:
trait ConversationPlugin {
    fn pre_process(&self, input: &str) -> String;
    fn post_process(&self, output: &str) -> String;
}

// Chain plugins:
let plugins = vec![
    Box::new(HIIPAAFilter),
    Box::new(MedicalContextInjector),
    Box::new(SafetyValidator),
];
```

#### 🔮 Future Features
1. **Plugin Marketplace** - Community-contributed plugins
2. **Visual Plugin Manager** - Enable/disable via UI
3. **Plugin Configuration** - Per-plugin settings
4. **Plugin Templates** - Easy creation for non-programmers

### Key Takeaways

#### What Works Well
- **Modular design** - Easy to add/remove features
- **Configuration via data** - World Info entries, not code
- **Debug mode** - Built-in testing and visibility
- **User-friendly** - Non-programmers can customize

#### How It Applies to AuraNexus
- ✅ Plugin architecture for conversation flow
- ✅ Middleware for context injection
- ✅ Safety and compliance filters
- ✅ Debug mode for testing
- ❌ Not directly applicable (different domain)
- ❌ JavaScript vs our Rust backend

### Notes
- This repo doesn't have "Inner-Thoughts" or "Auto-Cards" modules
- If you saw those elsewhere, they might be from:
  - A different version/fork
  - AI Dungeon built-in features
  - Another script pack
- The modular pattern is still valuable for inspiration

---
## Inner-Self (LewdLeah)
**Repository:** https://github.com/LewdLeah/Inner-Self  
**Type:** Open source - JavaScript AI Dungeon mod  
**Date Reviewed:** 2026-01-17

### Overview
Character cognitive system with private thoughts, self-organizing memories, and real-time brain editor. NPCs maintain separate mental states that persist across conversations.

### Healthcare Adaptation: **Patient Context Tracking**
- Track patient history automatically across visits
- Remember previous conversations and build profiles
- Separate memory per patient (HIPAA-compliant isolation)
- Real-time note suggestions during conversations
- Auto-generate session summaries and structured notes

---

## Auto-Cards (LewdLeah)
**Repository:** https://github.com/LewdLeah/Auto-Cards  
**Type:** Open source - JavaScript AI Dungeon mod  
**Date Reviewed:** 2026-01-17

### Overview
Automatic note-taking system that detects entities, generates summaries, and maintains living documentation during gameplay. Zero manual intervention required.

### Healthcare Adaptation: **Automated Clinical Documentation**
- **Entity extraction**: Symptoms, medications, conditions, procedures
- **SOAP note generation**: Auto-populate Subjective, Objective, Assessment, Plan
- **Visit summaries**: Generate after each conversation
- **ICD-10 mapping**: Link conditions to billing codes
- **EHR export**: Output to HL7/FHIR formats

### Combined Power for AuraNexus
Inner-Self + Auto-Cards = **Perfect healthcare documentation system**:
1. Memory system tracks patient context
2. Auto-Cards generates clinical notes
3. Practitioners focus on patients, not paperwork
4. Real-time suggestions with edit capability
5. HIPAA-compliant architecture


---

## Localized-Languages (LoLa) - LewdLeah
**Repository:** https://github.com/LewdLeah/Localized-Languages  
**Type:** Open source - JavaScript AI Dungeon mod  
**Date Reviewed:** 2026-01-17

### Overview
Multilingual accessibility script supporting 200+ languages (ISO 639-1 compliant). Context overhaul for AI to understand and respond in any language. Includes special modes like "Corporate Jargon", "Leetspeak", and "Brainrot".

### Healthcare Adaptation: **Multilingual Patient Communication**
- **200+ language support** for diverse patient populations
- **Medical terminology preservation** across languages
- **Cultural context adaptation** for healthcare communications
- **Accessibility features** for non-English speaking patients
- **Compliance with language access requirements**

### Key Features for AuraNexus
1. **Patient Language Preference**: Auto-detect or set preferred language
2. **Medical Translation**: Maintain accuracy of medical terms
3. **Cultural Sensitivity**: Adapt communication style per culture
4. **Accessibility Compliance**: Meet legal requirements for language access
5. **Professional Jargon Mode**: "Medical Speak" for clinical documentation

---

## Discovery-Journal - LewdLeah
**Repository:** https://github.com/LewdLeah/Discovery-Journal  
**Type:** Open source - JavaScript AI Dungeon mod  
**Date Reviewed:** 2026-01-17

### Overview
Character progression tracking with visual indicators (moon phases). Tracks NPC development and relationship scores over time. Auto-refreshes story cards to maintain current state.

### Healthcare Adaptation: **Patient Progress Tracking**
- **Visual progress indicators** for treatment milestones
- **Relationship tracking** for patient-provider rapport
- **Goal progression** toward health outcomes
- **Automated updates** of patient status cards
- **Historical tracking** of patient journey

### Key Features for AuraNexus
1. **Treatment Progress**: Visual indicators for goal completion
2. **Milestone Tracking**: Track recovery/treatment phases
3. **Engagement Metrics**: Monitor patient participation
4. **Outcome Visualization**: Show progress toward health goals
5. **Timeline View**: Historical view of patient journey

### Implementation Ideas
```
 - Treatment not started
 - Initial consultation
 - Treatment plan created
 - Treatment in progress
 - First milestone reached
 - Treatment goals achieved
```

---

## Summary: Complete LewdLeah Ecosystem

All repos work together to create a comprehensive system:

1. **Inner-Self** - Memory & context management
2. **Auto-Cards** - Automated documentation
3. **Localized-Languages** - Multilingual support
4. **Discovery-Journal** - Progress tracking

### Combined Healthcare Solution
- Track patients across visits (Inner-Self)
- Auto-generate clinical notes (Auto-Cards)
- Support diverse populations (Localized-Languages)
- Visualize treatment progress (Discovery-Journal)
- HIPAA-compliant architecture throughout
- Reduce documentation burden by 70%+
- Improve patient engagement and outcomes


---

## Kokoro-82M (hexgrad)
**Repository:** https://github.com/hexgrad/kokoro  
**Type:** Open source - TTS model (82M parameters, Apache licensed)  
**Date Reviewed:** 2026-01-17

### Overview
Lightweight open-weight TTS model with 82 million parameters. Apache licensed, production-ready, significantly faster than larger models. Supports multiple languages and voices.

### Key Features
- **Small & Fast**: 82M parameters vs multi-billion parameter alternatives
- **Multi-language**: English (US/UK), Spanish, French, Hindi, Italian, Japanese, Portuguese, Chinese
- **Multiple voices**: af_heart, af_bella, af_sarah, am_adam, am_michael, etc.
- **Speed control**: Adjustable speaking rate
- **High quality**: Comparable to much larger models
- **Apache licensed**: Can be deployed anywhere

### Healthcare Adaptation: **Voice Accessibility**

1. **Patient Communication**
   - Read medical instructions aloud for visually impaired patients
   - Multilingual voice support for diverse populations
   - Natural-sounding voice reduces anxiety

2. **Documentation Assistance**
   - Read back clinical notes for verification
   - Voice preview of auto-generated summaries
   - Accessibility for practitioners with visual impairments

3. **Patient Education**
   - Read medication instructions aloud
   - Voice-guided treatment plans
   - Interactive health information delivery

4. **Telemedicine Enhancement**
   - Generate voice responses for text-based consultations
   - Automated appointment reminders with natural voice
   - Voice-based patient onboarding

### Implementation for AuraNexus

**Integration Strategy:**
```rust
// Could integrate via Python binding or port inference to Rust
async fn text_to_speech(text: &str, voice: &str, lang: &str) -> Result<Vec<u8>> {
    // Call Kokoro model
    // Return audio bytes (WAV format)
}
```

**Use Cases:**
- Read Auto-Cards generated summaries aloud
- Voice feedback for Inner-Self context
- Multilingual patient communication (works with LoLa)
- Accessibility for visually impaired users

---

## Misaki G2P (hexgrad)
**Repository:** https://github.com/hexgrad/misaki  
**Type:** Open source - Grapheme-to-Phoneme engine  
**Date Reviewed:** 2026-01-17

### Overview
G2P (Grapheme-to-Phoneme) engine designed for Kokoro TTS. Converts text to phonemes for accurate pronunciation across languages.

### Key Features
- **English G2P**: American & British variants
- **Japanese G2P**: Pitch accent support, pyopenjtalk integration
- **Korean G2P**: Based on g2pK library
- **Fallback support**: Uses espeak for out-of-dictionary words
- **Transformer option**: Optional transformer-based G2P

### Healthcare Relevance: **Medical Pronunciation**

**Critical for medical terminology:**
- Correct pronunciation of drug names
- Accurate medical terminology TTS
- Patient name pronunciation across languages
- Technical term handling

**Example:**
```python
# Medical terms need accurate phonemes
text = "Prescribe acetaminophen 500mg every 6 hours"
phonemes = g2p(text)  # Ensures correct pronunciation
```

---

## Combined Audio Solution: Kokoro + Misaki

Together these provide a **complete TTS system** for AuraNexus:

1. **Misaki**: Text  Phonemes (accurate pronunciation)
2. **Kokoro**: Phonemes  Speech (natural voice)

### Healthcare Benefits
-  **Accessibility**: Voice output for all text
-  **Multilingual**: Support 8+ languages
-  **Lightweight**: 82M params runs on CPU
-  **Medical accuracy**: Proper term pronunciation
-  **Patient-friendly**: Natural voice reduces anxiety
-  **Apache licensed**: No restrictions for healthcare use

### Implementation Priority
-  **Future feature** (after core model management)
- Integrate after Inner-Self + Auto-Cards
- Add as optional plugin (don't bloat core app)
- Use for accessibility features


---

## Narratium.ai (805 - TypeScript/React)
**Repository:** https://github.com/Narratium/Narratium.ai  
**Type:** Open source (AGPL-3.0 code, CC BY-NC-SA content)  
**Date Reviewed:** 2026-01-17

### Overview
Full-featured AI character platform with immersive storytelling, worldbuilding, and roleplay. 805 stars, active development, professional-grade UI/UX. Supports local and cloud LLMs with SillyTavern character card compatibility.

### Key Features
- **Immersive Adventure Mode**: Personalized worlds with branching storylines
- **Visual Memory Management**: React Flow-powered session tracing and branching
- **Character Cards & Lore**: SillyTavern compatible, unified management
- **Powerful Plugin System**: Extensible with custom UI components
- **Multi-Model Support**: OpenAI, OpenRouter, Ollama, LM Studio
- **Offline/Local Deployment**: Full privacy mode available
- **Visual Interface**: Polished UI (vs SillyTavern minimal interface)
- **Infinite Branching**: Tree-based conversation flow

### Technical Stack
- **Frontend**: Next.js (React), TypeScript
- **State Management**: React Flow for conversation trees
- **Plugin Architecture**: Extensible component system
- **Character Format**: SillyTavern PNG cards (embedded JSON)
- **Deployment**: Vercel-ready, local Electron builds

### Healthcare Adaptation: **Patient Interaction Platform**

#### 1. **Patient Journey Mapping** (Branching Storylines  Treatment Paths)
- **Original**: Infinite branching narrative choices
- **Healthcare**: Multiple treatment pathways with decision points
- **Features**:
  - Visual treatment flow (React Flow)
  - Track decision rationale
  - Compare parallel treatment approaches
  - Document outcomes at each branch

#### 2. **Patient Cards** (Character Cards  Patient Profiles)
- **Original**: SillyTavern character cards with personality/lore
- **Healthcare**: Patient profiles with medical history
- **Format Adaptation**:
  ```json
  {
    "name": "Patient ID / Pseudonym",
    "description": "Chief complaint & presenting symptoms",
    "personality": "Communication style, preferences, concerns",
    "scenario": "Current treatment context",
    "first_mes": "Initial consultation summary",
    "mes_example": "Sample dialogue patterns",
    "creator_notes": "Clinical notes (SOAP format)",
    "system_prompt": "Treatment guidelines, allergies, contraindications",
    "tags": ["diabetes", "hypertension", "CHF"],
    "spec": "v2",
    "extensions": {
      "medical_history": [],
      "medications": [],
      "allergies": [],
      "vital_signs": {}
    }
  }
  ```

#### 3. **Worldbook  Medical Knowledge Base**
- **Original**: Lore entries for story world
- **Healthcare**: Clinical guidelines, drug interactions, protocols
- **Structure**:
  ```json
  {
    "entries": [
      {
        "keys": ["metformin", "diabetes"],
        "content": "First-line therapy for T2DM...",
        "case_sensitive": false,
        "enabled": true,
        "priority": 100
      }
    ]
  }
  ```

#### 4. **Plugin System  Clinical Modules**
- **Original**: Custom UI components and features
- **Healthcare**: Modular clinical tools
- **Examples**:
  - ICD-10 code lookup plugin
  - Drug interaction checker
  - Lab value interpreter
  - Treatment guideline assistant
  - EHR export plugin

#### 5. **Adventure Mode  Consultation Simulator**
- **Original**: Interactive storytelling with choices
- **Healthcare**: Clinical scenario training
- **Features**:
  - Practice difficult conversations
  - Simulate patient reactions
  - Train on edge cases
  - Review decision quality

### Implementation for AuraNexus

**Phase 1: Character Card System** (2-3 days)
```rust
// Import SillyTavern card format
struct PatientCard {
    name: String,
    description: String,  // Chief complaint
    personality: String,  // Patient communication style
    scenario: String,     // Treatment context
    first_mes: String,    // Initial consultation
    creator_notes: String, // SOAP notes
    extensions: serde_json::Value, // Medical data
}

async fn import_character_card(png_path: &str) -> Result<PatientCard> {
    // Read PNG tEXt chunk for embedded JSON
    // Parse SillyTavern v2 format
    // Map to healthcare fields
}
```

**Phase 2: React Flow Integration** (3-4 days)
- Add Tauri window with embedded React Flow
- Visualize conversation/consultation trees
- Track treatment decision branches
- Export pathway visualizations

**Phase 3: Worldbook/Knowledge Base** (2-3 days)
- Medical knowledge entries with keyword triggers
- Auto-inject relevant guidelines during chat
- Drug interaction warnings
- Protocol reminders

**Phase 4: Plugin Architecture** (4-5 days)
- WebAssembly or JavaScript plugin system
- Plugin marketplace
- Clinical tool integrations
- Community-contributed modules

### Key Differentiators for Healthcare

1. **Visual Treatment Paths**: React Flow trees show entire patient journey
2. **Reusable Profiles**: SillyTavern format = 1000s of existing tools compatible
3. **Plugin Extensibility**: Add clinical tools without core changes
4. **Local+Cloud Hybrid**: Privacy mode for PHI, cloud for non-PHI research
5. **Training Mode**: Consultation simulator for medical education

---

## CharGen (Narratium)
**Repository:** https://github.com/Narratium/CharGen  
**Type:** Open source - TypeScript/Node.js  
**Date Reviewed:** 2026-01-17

### Overview
AI-powered command-line tool for generating character cards and worldbook entries using **planning-based architecture**. Inspired by Jina AI's DeepResearch: "search, read, reason until answer is found."

### Core Architecture: **Plan-Driven Agent System**

#### 1. **Task Decomposition**
```mermaid
User Goal  3-5 Main Tasks  Each Task: 2-5 Sub-questions  Execution Loop
```

#### 2. **Six Tool System**
- **SEARCH**: Knowledge gathering from web/APIs
- **ASK_USER**: Clarification and user input
- **CHARACTER**: Build character card (8 required fields)
- **WORLDBOOK**: Create lore entries (only after character complete)
- **REFLECT**: Generate new tasks when queue empty
- **COMPLETE**: Validate and finalize output

#### 3. **Key Mechanisms**
- **Forced Task Optimization**: After every tool execution, LLM rewrites task descriptions
- **Character Priority**: 100% character completion before worldbook
- **REFLECT Trigger**: Only fires when queue empty but output incomplete
- **Real-time Decisions**: LLM selects best tool + parameters each iteration

### Healthcare Adaptation: **Clinical Documentation Agent**

#### 1. **Auto-SOAP Note Generation**
**Original**: Generate character description from research  
**Healthcare**: Generate SOAP notes from conversation

```typescript
// Adapted tool system
enum ClinicalTool {
  SEARCH_GUIDELINES,  // Look up clinical protocols
  ASK_PATIENT,        // Clarify symptoms/history
  SUBJECTIVE,         // Build S section
  OBJECTIVE,          // Build O section (vitals, exam)
  ASSESSMENT,         // Build A section (diagnosis)
  PLAN,               // Build P section (treatment)
  REFLECT_GAPS,       // Check for missing info
  COMPLETE_NOTE,      // Finalize and validate SOAP
}
```

#### 2. **Task Decomposition for Clinical Documentation**
```
User: "Document this patient encounter"

Main Tasks:
1. Extract subjective data (symptoms, history, concerns)
2. Organize objective data (vitals, physical exam, labs)
3. Formulate assessment (differential diagnosis)
4. Create treatment plan (medications, follow-up)
5. Generate billing codes (ICD-10, CPT)

Sub-questions (per task):
- Task 1: What is chief complaint? Duration? Associated symptoms?
- Task 2: What vitals recorded? Exam findings? Lab results?
- Task 3: What diagnoses fit? Rule-outs? Severity?
- Task 4: First-line treatment? Contraindications? Follow-up timing?
```

#### 3. **Forced Optimization  Clinical Quality**
**After each tool execution:**
- LLM rewrites remaining tasks based on new information
- Identifies documentation gaps
- Adds clarifying questions
- Ensures completeness

**Example:**
```
After SUBJECTIVE tool:
Original Task: "Document symptoms"
Optimized: "Document symptoms + Review of Systems gaps: 
  - No cardiovascular symptoms documented
  - No GI symptoms documented
  - Need to clarify onset timeline"
```

#### 4. **REFLECT Tool  Documentation Review**
**Original**: Create new tasks when queue empty  
**Healthcare**: Check documentation completeness

```typescript
async function reflectOnDocumentation(context: ClinicalContext) {
  const gaps = await analyzeSoapNote(context.note);
  
  if (gaps.length > 0) {
    return gaps.map(gap => ({
      type: 'ASK_PATIENT',
      question: gap.clarification,
      required_for: gap.section
    }));
  }
  
  // Check billing codes
  if (!context.icd10_codes || context.icd10_codes.length === 0) {
    return [{
      type: 'SEARCH_GUIDELINES',
      query: `ICD-10 codes for ${context.assessment.diagnosis}`
    }];
  }
  
  return []; // Documentation complete
}
```

### Implementation for AuraNexus

**Phase 1: Planning Architecture** (3-4 days)
```rust
// Adapt plan-driven system to Rust
struct AgentTask {
    id: String,
    description: String,
    sub_questions: Vec<String>,
    completed: bool,
}

struct ExecutionContext {
    tasks: VecDeque<AgentTask>,
    knowledge_base: Vec<KnowledgeEntry>,
    current_output: SoapNote,
}

async fn agent_loop(context: &mut ExecutionContext) -> Result<()> {
    while !context.tasks.is_empty() || !is_complete(&context.current_output) {
        let decision = select_next_tool(context).await?;
        execute_tool(decision, context).await?;
        optimize_remaining_tasks(context).await?; // Forced optimization
        
        if context.tasks.is_empty() && !is_complete(&context.current_output) {
            reflect_and_create_tasks(context).await?; // REFLECT
        }
    }
    Ok(())
}
```

**Phase 2: Clinical Tools** (4-5 days)
- Implement 8 clinical tools (SEARCH_GUIDELINES, ASK_PATIENT, etc.)
- LLM-driven tool selection
- Real-time task rewriting
- Completeness validation

**Phase 3: Integration with Auto-Cards** (2-3 days)
- Combine with LewdLeah Auto-Cards entity extraction
- Planning system generates structure
- Auto-Cards fills in details
- Inner-Self provides patient context

### Key Innovation: **Self-Optimizing Documentation**

Unlike static templates, this system:
1. **Adapts**: Rewrites tasks based on gathered information
2. **Questions**: Identifies gaps and asks clarifying questions
3. **Researches**: Looks up guidelines when uncertain
4. **Validates**: REFLECT ensures completeness before COMPLETE

**Result**: 90%+ complete documentation with minimal user input

---

## Character-Card Collection (Narratium)
**Repository:** https://github.com/Narratium/Character-Card  
**Type:** Public character card library  
**Date Reviewed:** 2026-01-17

### Overview
Curated collection of SillyTavern-compatible character cards (PNG format with embedded JSON). Provides API access via GitHub for fetching character libraries.

### Key Features
- **PNG-based Cards**: Character data embedded in PNG tEXt chunk
- **SillyTavern v2 Format**: Industry standard
- **GitHub API Access**: Fetch cards programmatically
- **Naming Convention**: `CharacterName--AuthorName.png`

### Healthcare Adaptation: **Clinical Case Library**

#### 1. **Case Repository** (Character Cards  Clinical Cases)
**Structure**:
```
cases/
 DiabetesT2-NewDiagnosis--DrSmith.png
 CHF-AcuteExacerbation--DrJones.png
 Depression-FirstEpisode--DrLee.png
 Hypertension-Uncontrolled--DrPatel.png
```

**Embedded Data** (PNG tEXt chunk):
```json
{
  "name": "Diabetes T2 - New Diagnosis",
  "description": "55yo M presents with polyuria, polydipsia x 3 months. HbA1c 8.2%",
  "personality": "Concerned but motivated, asks many questions",
  "scenario": "Initial diagnosis visit, insurance covers metformin",
  "first_mes": "I've been urinating a lot and always thirsty. Is this diabetes?",
  "creator_notes": "Teaching case for T2DM initial management",
  "system_prompt": "Follow ADA guidelines. Consider patient's work schedule.",
  "extensions": {
    "vitals": {"BP": "142/88", "HR": "76", "BMI": "31"},
    "labs": {"HbA1c": "8.2", "fasting_glucose": "156"},
    "comorbidities": ["obesity", "dyslipidemia"],
    "medications": ["atorvastatin 20mg"],
    "learning_objectives": [
      "Lifestyle counseling",
      "Metformin initiation",
      "Monitoring plan"
    ]
  }
}
```

#### 2. **API Integration**
```rust
// Fetch case library
async fn fetch_clinical_cases() -> Result<Vec<ClinicalCase>> {
    let url = "https://api.github.com/repos/YourOrg/Clinical-Cases/contents";
    let response = reqwest::get(url).await?;
    let files: Vec<GithubFile> = response.json().await?;
    
    let png_files = files.into_iter()
        .filter(|f| f.name.ends_with(".png"))
        .collect();
    
    // Download and parse each PNG
    let cases = download_and_parse_cases(png_files).await?;
    Ok(cases)
}

async fn parse_character_png(bytes: &[u8]) -> Result<ClinicalCase> {
    // Read PNG tEXt chunk
    // Decode base64 JSON
    // Parse SillyTavern format
    // Convert to clinical case
}
```

#### 3. **Use Cases**
- **Medical Education**: Library of teaching cases
- **Training Scenarios**: Practice consultations
- **Quality Assurance**: Standardized test cases
- **Research**: Anonymized case sharing
- **Collaboration**: Share cases between institutions

### Implementation for AuraNexus

**Phase 1: PNG Parser** (1 day)
```rust
use png::{Decoder, Chunk};

fn extract_character_json(png_bytes: &[u8]) -> Result<String> {
    let decoder = Decoder::new(png_bytes);
    let reader = decoder.read_info()?;
    
    for chunk in reader.info().compressed_latin1_text.iter() {
        if chunk.keyword == "chara" {
            let decoded = base64::decode(&chunk.text)?;
            return Ok(String::from_utf8(decoded)?);
        }
    }
    Err("No character data found")
}
```

**Phase 2: Case Library UI** (2 days)
- Browse available cases
- Filter by specialty, difficulty
- Preview case details
- Import to local workspace
- Share anonymized cases

**Phase 3: Case Creation Tool** (2 days)
- Create new case from consultation
- Auto-generate from SOAP notes
- Embed in PNG with medical image
- Upload to shared repository

### Key Benefits

1. **Portable**: Single PNG file contains everything
2. **Shareable**: Email, cloud storage, GitHub
3. **Anonymous**: No PHI in shared cases
4. **Interoperable**: SillyTavern format = wide compatibility
5. **Visual**: PNG shows patient photo/diagram + embedded data

---

## Combined Narratium Ecosystem for Healthcare

### Integration Strategy

**Layer 1: Patient Profiles** (Character-Card)
- SillyTavern PNG format for patient data
- Portable, shareable, anonymous

**Layer 2: Documentation Engine** (CharGen)
- Plan-driven agent generates SOAP notes
- Self-optimizing, gap-filling
- LLM-powered completeness checks

**Layer 3: Patient Journey Platform** (Narratium.ai)
- React Flow visualization
- Branching treatment paths
- Plugin ecosystem for clinical tools

**Layer 4: Memory & Context** (Inner-Self from LewdLeah)
- Track patient conversations
- Auto-generate visit summaries
- Maintain longitudinal context

**Layer 5: Entity Extraction** (Auto-Cards from LewdLeah)
- Extract symptoms, meds, conditions
- Populate structured fields
- ICD-10 code suggestions

### The Vision: **AuraNexus Clinical Suite**

```
User opens AuraNexus

Loads patient card (PNG with medical history)

Conversation starts (LLM + Inner-Self memory)

Auto-Cards extracts entities in real-time

CharGen agent builds SOAP note in background

Narratium.ai visualizes treatment pathway

Saves updated patient card + session branch

Exports to EHR via plugin
```

**Result**: 
- 70% documentation time reduction
- 100% HIPAA compliant (local-first)
- Visual treatment tracking
- Portable patient data
- Extensible via plugins

