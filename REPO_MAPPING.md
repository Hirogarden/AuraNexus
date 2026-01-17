# Repository Feature Mapping for AuraNexus
**Date Created:** 2026-01-17  
**Purpose:** Map cloned repositories to specific AuraNexus features and implementation priorities

---

## 📋 Quick Reference: Priority Mapping

### 🔴 HIGH PRIORITY (Implement First)
| Repo | Feature | Category |
|------|---------|----------|
| gpt4all | Model downloading/management | Core Infrastructure |
| llama.cpp | LLM inference backend | Core Infrastructure ✅ (In Use) |
| Narratium.ai | Patient cards, plugin system, React Flow | Healthcare Platform |
| Inner-Self | Patient memory/context system | Healthcare |
| Auto-Cards | Clinical documentation automation | Healthcare |
| CharGen | Planning-driven agent (SOAP notes) | Healthcare |
| character-card-spec-v2 | Patient profile format standard | Healthcare |

### 🟡 MEDIUM PRIORITY (Phase 2)
| Repo | Feature | Category |
|------|---------|----------|
| Localized-Languages | 200+ language medical terminology | Accessibility |
| Discovery-Journal | Treatment milestone tracking | Healthcare |
| khoj | Personal knowledge base | Productivity |
| mem0 | Persistent memory layer | Core Infrastructure |
| MemGPT | Long-term memory management | Core Infrastructure |
| langchain | LLM orchestration patterns | Integration |
| Coqui-TTS / Kokoro | Voice accessibility | Accessibility |

### 🟢 LOW PRIORITY (Future/Nice-to-Have)
| Repo | Feature | Category |
|------|---------|----------|
| stable-diffusion-webui | Image generation | Creative Tools |
| bark | Audio generation | Creative Tools |
| crewAI | Multi-agent coordination | Advanced Features |
| autogen | Agent framework | Advanced Features |

---

## 🏗️ Category 1: LLM Inference (Core - Already Implemented)

### ✅ Currently Using
| Repo | Path | Purpose | Status |
|------|------|---------|--------|
| llama.cpp | 1-LLM-Inference/llama.cpp | CPU-only inference via llama-cpp-2 crate | ✅ Active |

### 🔍 Reference Only
| Repo | Path | Relevance | Notes |
|------|------|-----------|-------|
| gpt4all | 1-LLM-Inference/gpt4all | **Download system reference** | C++ code for resumable downloads, hash verification |
| llamafile | 1-LLM-Inference/llamafile | Single-file distribution | Inspiration for packaging |
| ollama | 1-LLM-Inference/ollama | Model management UX | Go-based, reference patterns only |
| koboldcpp | 1-LLM-Inference/koboldcpp | GGUF + UI | May have useful UI patterns |
| LocalAI | 1-LLM-Inference/LocalAI | Multi-backend orchestration | Overly complex for our needs |

### ❌ Not Applicable
- **ctransformers**: Python only, no Rust bindings
- **exllamav2**: GPU-only, incompatible with CPU focus
- **TensorRT-LLM**: NVIDIA-specific, requires proprietary SDK
- **vllm**: GPU-only, server-focused
- **mlc-llm**: Too complex, mobile focus
- **text-generation-webui**: Python web UI, duplicate functionality
- **KoboldAI-Client**: Legacy, superseded by koboldcpp

---

## 🧠 Category 2: Memory & RAG Systems

### 🔴 HIGH PRIORITY
| Repo | Path | AuraNexus Feature | Implementation Plan |
|------|------|-------------------|---------------------|
| **Inner-Self** | 9-Utilities/Inner-Self | **Patient conversation memory** | Adapt segmented memory (short/long/core) for patient context isolation. See REPO_INSPIRATION.md |
| **mem0** | 3-Memory-RAG/mem0 | Persistent memory layer | Check if simpler than Inner-Self for basic persistence |
| **MemGPT** | 3-Memory-RAG/MemGPT | Long-term conversation memory | If Inner-Self insufficient, use MemGPT's hierarchical memory |

### 🟡 MEDIUM PRIORITY
| Repo | Path | Feature | Notes |
|------|------|---------|-------|
| chromadb | 3-Memory-RAG/chromadb | Vector DB for medical knowledge | Local embedding storage for drug interactions, guidelines |
| pgvector | 3-Memory-RAG/pgvector | Postgres vector extension | If we need SQL + vectors (EHR integration) |
| txtai | 3-Memory-RAG/txtai | Lightweight embeddings | Pure Python, simpler than chromadb |

### � REFERENCE VALUE (Translate/Adapt Patterns)
| Repo | Path | What to Learn | Mode Application |
|------|------|---------------|------------------|
| **langchain** | 3-Memory-RAG/langchain | Agent loops, prompt templates, chain patterns | All modes - architecture patterns |
| **llama_index** | 3-Memory-RAG/llama_index | Document chunking, metadata extraction | Productivity - document analysis |
| **haystack** | 3-Memory-RAG/haystack | Pipeline architecture, component system | All modes - modular design |
| **Verba** | 3-Memory-RAG/Verba | RAG UI/UX patterns | Productivity - knowledge base interface |
| **ragflow** | 3-Memory-RAG/ragflow | Visual workflow builder | Productivity - visual programming |
| **ragas** | 3-Memory-RAG/ragas | Evaluation metrics (faithfulness, relevance) | All modes - quality measurement |
| **gpt-researcher** | 3-Memory-RAG/gpt-researcher | Research automation, source synthesis | Productivity/Learning - research assistant |
| **khoj** | 3-Memory-RAG/khoj | Personal knowledge graph, incremental indexing | Productivity - note-taking integration |

### 🟢 CLOUD PATTERNS (Local Adaptation Ideas)
| Repo | Path | Learn Cloud Pattern, Implement Locally |
|------|------|---------------------------------------|
| semantic-kernel | 3-Memory-RAG/ | Plugin system, memory management |
| qdrant | 3-Memory-RAG/ | Vector search API design (Rust reference!) |
| weaviate | 3-Memory-RAG/ | Schema design, hybrid search |

---

## 🏥 Category 3: Healthcare-Specific Features

### 🔴 CRITICAL - CORE DIFFERENTIATORS
| Repo | Path | AuraNexus Feature | Implementation Priority |
|------|------|-------------------|------------------------|
| **Narratium.ai** | 9-Utilities/Narratium.ai | - SillyTavern patient cards<br>- React Flow treatment visualization<br>- Plugin architecture<br>- Branching conversation paths | **Phase 1**: Character card import/export<br>**Phase 2**: React Flow integration<br>**Phase 3**: Plugin system |
| **CharGen** | 9-Utilities/CharGen | **Planning-driven documentation agent**<br>- Auto-SOAP note generation<br>- Task decomposition<br>- Self-optimizing completeness checks | **Phase 1**: Port architecture to Rust<br>**Phase 2**: Clinical tool system<br>**Phase 3**: Integration with Auto-Cards |
| **Auto-Cards** | 9-Utilities/Auto-Cards | **Clinical entity extraction**<br>- Symptom/medication/condition detection<br>- ICD-10 code suggestions<br>- SOAP note population | **Phase 1**: Entity extraction engine<br>**Phase 2**: Medical NER model<br>**Phase 3**: EHR export |
| **Inner-Self** | 9-Utilities/Inner-Self | **Patient context memory**<br>- Segmented memories per patient<br>- Auto-generated visit summaries<br>- Context isolation | **Phase 1**: Memory segmentation<br>**Phase 2**: Per-patient isolation<br>**Phase 3**: Auto-summarization |

### 🟡 ENHANCING FEATURES
| Repo | Path | Feature | Use Case |
|------|------|---------|----------|
| **Localized-Languages** | 9-Utilities/Localized-Languages | 200+ language support | Multilingual patient communication (HIPAA language access) |
| **Discovery-Journal** | 9-Utilities/Discovery-Journal | Visual progress indicators (moon phases) | Treatment milestone tracking, patient journey visualization |
| **character-card-spec-v2** | 6-SillyTavern-Ecosystem/character-card-spec-v2 | SillyTavern v2 format spec | Patient profile interchange format |
| **Character-Card** | 9-Utilities/Character-Card | PNG-based card library | Clinical case repository (teaching cases, standardized scenarios) |

---

## 🎭 Category 4: SillyTavern Ecosystem (Character Cards)

### 🔴 ESSENTIAL
| Repo | Path | Feature | Integration Point |
|------|------|---------|-------------------|
| character-card-spec-v2 | 6-SillyTavern-Ecosystem/ | **Format specification** | Patient card structure definition |
| Character-Card | 9-Utilities/ | **Card library API** | Clinical case library via GitHub API |

### 🟡 USEFUL EXTENSIONS
| Repo | Path | Feature | Potential Use |
|------|------|---------|---------------|
| SillyTavern | 6-SillyTavern-Ecosystem/ | Reference UI implementation | UI patterns for card management |
| SillyTavern-extras | 6-SillyTavern-Ecosystem/ | TTS, image gen, embeddings | Voice features, image attachment to cards |
| Extension-ChromaDB | 6-SillyTavern-Ecosystem/ | Vector DB integration | Medical knowledge base pattern |

### 🟢 INFORMATIONAL
| Repo | Path | Notes |
|------|------|-------|
| SillyTavern-Docs | 6-SillyTavern-Ecosystem/ | Documentation reference |
| SillyTavern-Content | 6-SillyTavern-Ecosystem/ | Example character cards |
| SillyTavern-Launcher | 6-SillyTavern-Ecosystem/ | Desktop packaging patterns |
| SillyTavern-Fandom-Scraper | 6-SillyTavern-Ecosystem/ | Data collection patterns |
| SillyTavern-WebSearch-Selenium | 6-SillyTavern-Ecosystem/ | Web search integration |

### ❌ NOT APPLICABLE
- **SillyTavern-YouTube-Videos-Server**: Entertainment only
- **Extension-VRM**: Avatar features (not healthcare priority)
- **Extension-RVC**: Voice cloning (ethical concerns in medical context)
- **SillyTavern-EdgeTTS-Plugin**: Use Coqui/Kokoro instead (better control)

---

## 🔊 Category 5: Voice & Audio (Accessibility)

### 🟡 MEDIUM PRIORITY
| Repo | Path | Feature | Healthcare Application |
|------|------|---------|------------------------|
| Coqui-TTS | 6-SillyTavern-Ecosystem/Coqui-TTS | Open-source TTS | Read clinical notes aloud, patient education |
| kokoro | 7-Voice-Audio/kokoro | Lightweight 82M TTS model | Fast, multilingual, Apache licensed |
| misaki | 7-Voice-Audio/misaki | G2P for medical terms | Accurate pronunciation of drug names |

### 🟢 REFERENCE ONLY
| Repo | Path | Notes |
|------|------|-------|
| bark | 5-Storytelling/bark | Audio generation | Overly complex for basic TTS needs |
| VITS-fast-fine-tuning | 6-SillyTavern-Ecosystem/ | Custom voice training | Future: personalized patient interaction voices |
| GPT-SoVITS | 6-SillyTavern-Ecosystem/ | Voice cloning | Ethical concerns in medical context |
| xtts-streaming-server | 6-SillyTavern-Ecosystem/ | Streaming TTS | Performance optimization reference |

### ❌ NOT APPLICABLE (Visual/Avatar)
- **avatarify-python**: Face animation (not healthcare priority)
- **OpenSeeFace**: Face tracking
- **face-alignment**: Face detection
- **mediapipe**: Computer vision
- **VirtualMotionCapture**: VR motion capture
- **three-vrm**: 3D avatar rendering
- **UniVRM**: VRM format handling
- **vrm-specification**: Avatar spec
- **Extension-VRM**: SillyTavern avatar extension
- **rpm-unity-sdk-core**: ReadyPlayerMe avatars

---

## 🤖 Category 6: Multi-Agent Systems

### 🟡 MEDIUM PRIORITY (Phase 3+)
| Repo | Path | Potential Feature | Consideration |
|------|------|-------------------|---------------|
| crewAI | 4-Multi-Agent/crewAI | Multi-specialist consultation | Simulate specialist opinions (cardiology, endocrinology) |
| autogen | 4-Multi-Agent/autogen | Agent coordination | Microsoft's framework - check patterns |
| MetaGPT | 4-Multi-Agent/MetaGPT | Software team simulation | Could adapt for care team coordination |

### � REFERENCE VALUE (Agent Patterns)
| Repo | Path | What to Learn | Mode Application |
|------|------|---------------|------------------|
| **autogen** | 4-Multi-Agent/ | Conversational agents, role-playing | Creative - brainstorming with AI personas |
| **MetaGPT** | 4-Multi-Agent/ | Software team roles, task breakdown | Productivity - project planning assistant |
| **dify** | 4-Multi-Agent/ | Workflow builder UI, plugin system | All modes - visual workflow design |
| **langgraph** | 4-Multi-Agent/ | Graph-based state machines | All modes - complex conversation flows |
| **ix** | 4-Multi-Agent/ | Visual agent programming | Productivity - no-code automation |
| **camel-ai** | 4-Multi-Agent/ | Agent-to-agent communication protocols | All modes - multi-perspective analysis |
| **agentops** | 4-Multi-Agent/ | Observability, debugging, logging | Development - agent debugging tools |

### 🟢 REFERENCE ONLY
| Repo | Path | Pattern to Learn |
|------|------|------------------|
| superagi | 4-Multi-Agent/ | Autonomous task planning |
| babyagi | 4-Multi-Agent/ | Simple task loop (outdated but clean) |
| agent-studio | 4-Multi-Agent/ | Agent testing patterns |
| cagent | 4-Multi-Agent/ | CLI interface for agents |

### ❌ NOT APPLICABLE
- **agentverse**: Multi-agent metaverse (entertainment simulation)
- **compose-for-agents**: Docker orchestration (infrastructure)
WRITING MODE (HIGH VALUE)
| Repo | Path | Feature | Creative Application |
|------|------|---------|---------------------|
| **AIDungeon** | 5-Storytelling/ | Interactive narrative engine, world state tracking | Story generation with persistent world memory |
| **ink** | 5-Storytelling/ | Narrative scripting language (choices, branches) | Branching story DSL, choice-driven narratives |
| **twine** | 5-Storytelling/ | Visual story graph editor | Story structure visualization |
| **Clover-Edition** | 5-Storytelling/ | NovelAI fork with advanced prompting | Creative writing prompt engineering |
| **awesome-chatgpt-prompts** | 5-Storytelling/ | 150+ persona prompts | Character creation, role-play scenarios |
| **AIDscripts** | 5-Storytelling/ | Scripting system for dynamic content | Scriptable story events |

### 🟡 PRODUCTIVITY MODE (DOCUMENT/RESEARCH)
| Repo | Path | Feature | Productivity Application |
|------|------|---------|-------------------------|
| **localGPT** | 5-Storytelling/ | Private document Q&A | Personal knowledge base chat |
| **gpt-researcher** | 3-Memory-RAG/ | Research automation, web synthesis | Research assistant, report generation |

### 🔵 REFERENCE VALUE (Prompting & Scripting)
| Repo | Path | What to Learn |
|------|------|---------------|
| script-pack-1 | 5-Storytelling/ | JavaScript plugin patterns for MousAI |
| STMP | 5-Storytelling/ | Plugin manager architecture |
| Prompt-Engineering-Guide | 9-Utilities/ | Advanced prompting techniques (chain-of-thought, few-shot) |
| promptbase | 9-Utilities/ | Marketplace patterns, prompt versioning |
| Promptify | 9-Utilities/ | Structured prompt generation with variables |
| storypromptgen | 5-Storytelling/ | Random prompt generation algorithms |

### 🟢 REFERENCE ONLY
| Repo | Path | Notes |
|------|------|-------|
| ifdb | 5-Storytelling/ | Interactive fiction metadata standards |
| novelai-research-tool | 5-Storytelling/ | Prompt optimization patterns (avoid reverse engineering) |
| OLDungeon | 5-Storytelling/ | Legacy reference for AI Dungeon mechanics |
- **storypromptgen**: Story prompt generator
- **ifdb**: Interactive fiction database
- **twine**: Interactive fiction tool
- **AIDscripts**: AI Dungeon scripts (outdated)
- **localGPT**: Local document Q&A (duplicate RAG functionality)

---

## 🛠️ Category 8: Utilities & Tools

### 🔴 ESSENTIAL REFERENCES
| Repo | Path | Feature | Use Case |
|------|------|---------|----------|
| **transformers** | 9-Utilities/transformers | Hugging Face model library | Model metadata, conversion utilities |
| **datasets** | 9-Utilities/datasets | Data loading/processing | Medical dataset handling |

### 🟡 USEFUL TOOLS
| Repo | Path | Feature | Application |
|------|------|---------|-------------|
| litgpt | 9-Utilities/ | Lightweight training/fine-tuning | If we need model customization |
| lm-evaluation-harness | 9-Utilities/ | Model benchmarking | Test LLM clinical accuracy |
| opencompass | 9-Utilities/ | LLM evaluation framework | Compare models for medical use |
| ollama-python | 9-Utilities/ | Ollama Python client | Reference for model management API |
| fasteval | 9-Utilities/ | Fast model evaluation | Performance testing |

### 🟢 INFORMATIONAL
| Repo | Path | Notes |
|------|------|-------|
| stanford_alpaca | 9-Utilities/ | Instruction tuning dataset |
| pytorch | 9-Utilities/ | Deep learning framework (too large, reference only) |
| onnx | 9-Utilities/ | Model interchange format |
| browserllama | 9-Utilities/ | Browser-based LLM inference |
| zentk | 9-Utilities/ | Zero-shot learning toolkit |
| KoboldSharp | 9-Utilities/ | C# Kobold client |
| koboldswap | 9-Utilities/ | Model swapping utility |
| kobocr | 9-Utilities/ | OCR for e-readers |

### ❌ NOT APPLICABLE
- **Open-Assistant**: Conversational AI project (archived, outdated)
- **llama.cpp** (duplicate): Same as 1-LLM-Inference version

---

## 🖼️ Category 9: Image Generation (Future/Low Priority)

### 🟢 FUTURE FEATURES
| Repo | Path | Potential Use | Priority |
|------|------|---------------|----------|
| stable-diffusion-webui | 6-SillyTavern-Ecosystem/ | Medical diagram generation | Low - privacy concerns with image AI |

**Status:** ❌ Not implementing image generation in Phase 1-3
- **Reason 1**: HIPAA concerns with patient images
- **Reason 2**: Not core to documentation workflow
- **Reason 3**: Resource-intensive (GPU required)
- **Future consideration**: Medical diagram generation for education (non-PHI)

---

## 📊 Implementation Roadmap

### ✅ Phase 0: Foundation (COMPLETE)
- [x] llama.cpp integration (CPU inference)
- [x] Basic chat UI
- [x] Model scanner (Step 1/6)

### 🔴 Phase 1: Model Management (CURRENT - Week 1-2)
**Priority Repos:**
- gpt4all → Download implementation reference (C++)
- ollama → Model management UX patterns (Go)
- transformers → HuggingFace API integration

**Deliverables:**
- Step 2: Model downloader (resumable, hash verification)
- Step 3: Enhanced model info (GGUF metadata parsing)
- Step 4: Model conversion tools (HF → GGUF)
- Step 5: Model profiles/presets
- Step 6: Model marketplace integration

### 🟡 Phase 2: Healthcare Foundation (Week 3-6)
**Priority Repos:**
1. **Narratium.ai** → Patient card system (SillyTavern format)
2. **character-card-spec-v2** → Format specification
3. **Inner-Self** → Patient memory isolation
4. **Auto-Cards** → Entity extraction engine
5. **CharGen** → Planning-driven documentation agent

**Deliverables:**
- Import/export patient cards (PNG with embedded JSON)
- Per-patient conversation memory
- Real-time entity extraction (symptoms, meds, conditions)
- Auto-SOAP note generation
- Treatment milestone tracking

### 🟢 Phase 3: Advanced Features (Week 7-12)
**Priority Repos:**
1. **Narratium.ai** → React Flow visualization + Plugin system
2. **Localized-Languages** → Multilingual support
3. **Discovery-Journal** → Progress indicators
4. **Coqui-TTS** / **kokoro** → Voice accessibility
5. **Character-Card** → Clinical case library

**Deliverables:**
- Visual treatment pathway mapping
- Plugin marketplace
- 200+ language support for patient communication
- Text-to-speech for clinical notes
- Shared case repository

### 🔵 Phase 4: Multi-Agent & Automation (Week 13+)
**Priority Repos:**
1. **crewAI** / **autogen** → Multi-specialist consultation
2. **khoj** → Personal knowledge management
3. **mem0** / **MemGPT** → Enhanced long-term memory

**Deliverables:**
- Simulated specialist opinions
- Knowledge base integration
- Advanced memory systems
- EHR integration plugins

---

## 📈 Metrics: Repository Relevance Score

### 🔴 Critical (10/10) - Implement Now
- gpt4all
- Narratium.ai
- Inner-Self
- Auto-Cards
- CharGen
- character-card-spec-v2

### 🟡 High Value (7-9/10) - Phase 2-3
- Localized-Languages (9/10)
- Discovery-Journal (8/10)
- Character-Card (8/10)
- mem0 (7/10)
- MemGPT (7/10)
- Coqui-TTS (7/10)
- chromadb (7/10)

### 🟢 Moderate Value (4-6/10) - Phase 4+
- crewAI (6/10)
- autogen (6/10)
- khoj (5/10)
- AIDungeon (5/10)
- litgpt (4/10)

### ⚫ Low Value (1-3/10) - Reference Only
- Most multi-agent frameworks (3/10)
- Most vector DBs beyond chromadb (3/10)
- Entertainment-focused tools (2/10)
- Deprecated/archived projects (1/10)

### ❌ No Value (0/10) - Ignore
- Image generation (privacy concerns)
- Avatar/VR systems (not healthcare-relevant)
- Hacking/penetration tools
- Duplicate functionality

---

## 🎯 Next Steps

### Immediate Actions (This Week)
1. ✅ Model scanner complete (Step 1)
2. 🔄 Study GPT4All download.cpp for Step 2 implementation
3. 🔄 Read Narratium.ai character card parsing code
4. 🔄 Analyze Inner-Self memory architecture

### Planning Tasks (Next Week)
1. Create detailed specs for patient card format (based on SillyTavern v2)
2. Design memory isolation architecture (per-patient contexts)
3. Prototype entity extraction pipeline (Auto-Cards patterns)
4. Sketch React Flow treatment pathway UI

### Research Tasks (Ongoing)
1. Review more repos in each category for hidden gems
2. Check for Rust-native alternatives to Python tools
3. Identify licensing concerns for commercial deployment
4. Evaluate HIPAA compliance for each integration

---

## 📚 Documentation Cross-References

- **REPO_INSPIRATION.md** - Detailed analysis of top repos (GPT4All, Narratium, LewdLeah, hexgrad)
- **HIPAA_COMPLIANCE.md** - Security requirements for PHI handling
- **SECURITY_CHECKLIST.md** - Feature-by-feature compliance checks
- **PROJECT_STRUCTURE.md** - Current codebase architecture
- **DEVELOPMENT_WORKFLOW.md** - Development process and standards
- **HIERARCHICAL_MEMORY_GUIDE.md** - Memory system design (will integrate Inner-Self)

---

## 🔄 Last Updated
**Date:** 2026-01-17  
**Status:** Initial mapping complete - 200+ repos catalogued  
**Next Review:** After Phase 1 completion (model management)

---

*This document will be updated as we progress through implementation phases and discover new relevant features in existing repos.*
